'use client';
import { useState, type FormEvent } from 'react';
import { useResearch, useResearchStore } from '@/components/ResearchStore';
import { ErrorNotice, Loading, StatusBadge } from '@/components/Feedback';
import { api, useApi } from '@/lib/api';
import { readable, type SystemInfo } from '@/data/research';

export default function Settings() {
  const research = useResearch();
  const refresh = useResearchStore((state) => state.refresh);
  const { data: system, error } = useApi<SystemInfo>('/v1/system', 10000);
  const [title, setTitle] = useState(research.title);
  const [description, setDescription] = useState(research.description);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setSaveError(null);
    try {
      await api('/v1/projects/' + research.id, {
        method: 'PATCH',
        body: JSON.stringify({ title, description }),
      });
      await refresh();
      setSaved(true);
    } catch (failure) {
      setSaveError(failure);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="workspace-scroll">
      <section className="product-page settings-page">
        <p className="eyebrow">Your local setup</p>
        <h1>Settings</h1>
        <form className="panel" onSubmit={save}>
          <h2>Research workspace</h2>
          <label className="field-label" htmlFor="workspace-name">
            Name
          </label>
          <input
            className="ui-input"
            id="workspace-name"
            required
            maxLength={120}
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setSaved(false);
            }}
          />
          <label className="field-label" htmlFor="workspace-description">
            Description
          </label>
          <textarea
            className="ui-input"
            id="workspace-description"
            maxLength={400}
            rows={3}
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              setSaved(false);
            }}
          />
          <ErrorNotice error={saveError} />
          <button className="ui-button ui-button-primary" disabled={busy || !title.trim()}>
            {busy ? 'Saving…' : 'Save workspace'}
          </button>
          {saved && (
            <p className="muted" role="status">
              Workspace saved.
            </p>
          )}
        </form>
        <ErrorNotice error={error} />
        {!system && !error && <Loading text="Checking local services…" />}
        {system && (
          <>
            <section className="panel">
              <div className="page-heading">
                <h2>Backend & worker</h2>
                <StatusBadge status={system.worker_count ? 'ready' : 'pending'} />
              </div>
              <p className="muted">
                {system.worker_count} active worker process(es). Work is stored in PostgreSQL and
                continues when the browser closes. Your machine and worker must remain running;
                interrupted work resumes after restart.
              </p>
              <dl>
                <dt>Deployment</dt>
                <dd>Local, single owner</dd>
                <dt>Azure configuration</dt>
                <dd>
                  {system.azure_configured
                    ? 'Configured'
                    : 'Incomplete — update the local .env file'}
                </dd>
                <dt>Generation deployment</dt>
                <dd>{system.model || 'Not configured'}</dd>
                <dt>Embedding deployment</dt>
                <dd>{system.embedding_deployment || 'Not configured'}</dd>
                <dt>Embedding dimensions</dt>
                <dd>{system.embedding_dimensions}</dd>
              </dl>
            </section>
            <section className="panel">
              <h2>Parsing & source policy</h2>
              <dl>
                <dt>Uploads</dt>
                <dd>
                  {system.supported_formats.join(', ')} ·{' '}
                  {Math.round(system.max_upload_bytes / 1048576)} MB per file
                </dd>
                <dt>Parser & chunker</dt>
                <dd>
                  Docling with structural chunking. OCR is off; image-only PDFs need a text layer.
                </dd>
                <dt>Sources per run</dt>
                <dd>{system.max_sources} maximum</dd>
                <dt>Approved web pages</dt>
                <dd>
                  Up to {system.max_web_sources} explicit public HTTPS URLs, disabled by default
                </dd>
              </dl>
              <p className="muted">{system.privacy}</p>
            </section>
            <section className="panel">
              <h2>Per-run limits</h2>
              <dl>
                {Object.entries(system.limits).map(([key, value]) => (
                  <div className="definition-row" key={key}>
                    <dt>{readable(key)}</dt>
                    <dd>{value.toLocaleString()}</dd>
                  </div>
                ))}
              </dl>
              <p className="muted">
                Runtime settings are read from your local .env file. Restart the API and worker
                after changing them. Secrets are never displayed here. Changing embedding
                deployments requires a compatible index.
              </p>
            </section>
          </>
        )}
      </section>
    </div>
  );
}
