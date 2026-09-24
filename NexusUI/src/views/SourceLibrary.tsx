'use client';
import { useState } from 'react';
import Link from 'next/link';
import { FileText, Plus } from 'lucide-react';
import { useResearch, useResearchStore } from '@/components/ResearchStore';
import SourceUpload from '@/components/SourceUpload';
import { ErrorNotice, Loading, StatusBadge } from '@/components/Feedback';
import { api, useApi } from '@/lib/api';
import { formatDate } from '@/data/research';

type ExistingSource = {
  source_id: string;
  display_name: string;
  status: string;
  chunk_count: number;
};
export default function SourceLibrary() {
  const research = useResearch();
  const { refresh, updateDraft } = useResearchStore((state) => state);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [showExisting, setShowExisting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const {
    data: existing,
    error: existingError,
    isLoading,
  } = useApi<{ sources: ExistingSource[] }>(showExisting ? '/v1/sources?limit=100' : null);
  const visible = research.sources.filter(
    (source) =>
      source.name.toLowerCase().includes(query.toLowerCase()) &&
      (status === 'all' || source.status === status),
  );

  async function selectSource(id: string, selected: boolean) {
    setBusy(true);
    setError(null);
    try {
      await updateDraft(research.id, {
        ...research.draft,
        source_ids: selected
          ? [...research.draft.source_ids, id]
          : research.draft.source_ids.filter((value) => value !== id),
      });
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  async function sourceAction(id: string, retry = false) {
    setBusy(true);
    setError(null);
    try {
      await api('/v1/projects/' + research.id + '/sources/' + id + (retry ? '/retry' : ''), {
        method: 'POST',
      });
      await refresh();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="workspace-scroll">
      <section className="product-page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Research materials</p>
            <h1>Source library</h1>
          </div>
          <Link className="ui-button" href={`/research/${research.id}`}>
            Research with selected sources
          </Link>
        </div>
        <p className="muted">
          Only sources selected in this workspace are available to its next run. Existing runs keep
          their original document versions.
        </p>
        <div className="metric-grid">
          <div className="metric">
            <span>Sources</span>
            <strong>{research.sources.length}</strong>
          </div>
          <div className="metric">
            <span>Ready</span>
            <strong>{research.sources.filter((s) => s.status === 'ready').length}</strong>
          </div>
          <div className="metric">
            <span>Selected</span>
            <strong>{research.draft.source_ids.length}</strong>
          </div>
          <div className="metric">
            <span>Indexed passages</span>
            <strong>{research.sources.reduce((sum, s) => sum + s.chunks, 0)}</strong>
          </div>
        </div>
        <SourceUpload />
        <div className="toolbar">
          <input
            className="ui-input"
            aria-label="Search sources"
            placeholder="Search sources…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            className="ui-input"
            aria-label="Source status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {['all', 'ready', 'processing', 'failed'].map((value) => (
              <option key={value} value={value}>
                {value === 'all' ? 'All statuses' : value}
              </option>
            ))}
          </select>
          <button className="ui-button" onClick={() => setShowExisting(!showExisting)}>
            <Plus size={15} /> Add existing source
          </button>
        </div>
        <ErrorNotice error={error} />
        {showExisting && (
          <section className="panel">
            <h2>Attach from your local library</h2>
            <p className="muted">
              Attaching a source explicitly makes it available to this research.
            </p>
            <ErrorNotice error={existingError} />
            {isLoading && <Loading />}
            <div className="stack">
              {existing?.sources
                .filter(
                  (source) => !research.sources.some((current) => current.id === source.source_id),
                )
                .map((source) => (
                  <div className="source-row" key={source.source_id}>
                    <span>{source.display_name}</span>
                    <StatusBadge status={source.status} />
                    <button
                      className="ui-button"
                      disabled={busy}
                      onClick={() => sourceAction(source.source_id)}
                    >
                      Attach
                    </button>
                  </div>
                ))}
            </div>
            {existing &&
              existing.sources.every((source) =>
                research.sources.some((current) => current.id === source.source_id),
              ) && <p className="muted">No other sources to attach.</p>}
          </section>
        )}
        <div className="stack">
          {visible.map((source) => (
            <article className="panel source-row" key={source.id}>
              <input
                type="checkbox"
                aria-label={`Select ${source.name}`}
                checked={research.draft.source_ids.includes(source.id)}
                disabled={busy || source.status !== 'ready'}
                onChange={(e) => selectSource(source.id, e.target.checked)}
              />
              <FileText size={20} color="#60a5fa" />
              <div className="source-row-content">
                <Link href={`/research/${research.id}/sources/${source.id}`}>{source.name}</Link>
                <p>
                  {source.type} ·{' '}
                  {source.pages == null ? 'No fixed page count' : source.pages + ' pages'} ·{' '}
                  {source.chunks} passages · {formatDate(source.created_at)}
                </p>
                {source.error_detail && <p className="error-text">{source.error_detail}</p>}
              </div>
              <StatusBadge status={source.status} />
              {source.status === 'failed' && source.kind === 'upload' && (
                <button
                  className="ui-button"
                  disabled={busy}
                  onClick={() => sourceAction(source.id, true)}
                >
                  Retry
                </button>
              )}
            </article>
          ))}
        </div>
        {!visible.length && (
          <div className="runs-empty">
            <h2>{research.sources.length ? 'No matching sources' : 'Your research starts here'}</h2>
            <p>Upload a document or attach one from your library.</p>
          </div>
        )}
      </section>
    </div>
  );
}
