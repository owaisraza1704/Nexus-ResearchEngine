'use client';
import { useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { api, useApi } from '@/lib/api';
import { useResearch, useResearchStore } from './ResearchStore';
import { ErrorNotice, Loading } from './Feedback';
import type { SystemInfo } from '@/data/research';

export default function SourceUpload() {
  const research = useResearch();
  const refresh = useResearchStore((state) => state.refresh);
  const { data: system } = useApi<SystemInfo>('/v1/system', 10000);
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState<unknown>(null);

  async function upload(files: FileList | File[]) {
    if (busy || !files.length) return;
    setBusy(true);
    setError(null);
    setMessage('');
    let count = 0;
    try {
      for (const file of Array.from(files)) {
        if (!/\.(pdf|docx)$/i.test(file.name)) throw new Error('Choose PDF or DOCX documents.');
        if (system && file.size > system.max_upload_bytes)
          throw new Error(file.name + ' exceeds the upload limit.');
        const form = new FormData();
        form.append('file', file);
        await api('/v1/projects/' + research.id + '/sources/uploads', {
          method: 'POST',
          body: form,
        });
        count++;
      }
      setMessage(count + ' document(s) accepted. Parsing and embedding continue in the worker.');
    } catch (failure) {
      setError(failure);
      if (count) setMessage(count + ' document(s) were accepted before this error.');
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
      await refresh();
    }
  }

  return (
    <div className="upload-section">
      <input
        ref={input}
        type="file"
        accept=".pdf,.docx"
        multiple
        aria-label="Upload documents"
        className="visually-hidden"
        onChange={(event) => event.target.files && upload(event.target.files)}
        disabled={busy}
      />
      <button
        type="button"
        className="upload-zone"
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          upload(event.dataTransfer.files);
        }}
      >
        {busy ? (
          <Loading text="Uploading…" />
        ) : (
          <>
            <Upload size={19} />
            <span>Drop PDF or DOCX files here, or click to upload</span>
          </>
        )}
      </button>
      <p className="draft-notice">
        Uploading approves processing by your configured Azure services.{' '}
        {system && `Up to ${Math.round(system.max_upload_bytes / 1048576)} MB per file.`}
      </p>
      {system?.worker_count === 0 && (
        <p className="warning-notice">
          Worker offline. Uploads will wait safely in the queue until it starts.
        </p>
      )}
      {message && (
        <p className="muted" role="status">
          {message}
        </p>
      )}
      <ErrorNotice error={error} />
    </div>
  );
}
