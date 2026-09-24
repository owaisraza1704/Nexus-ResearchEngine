'use client';
import { useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Download } from 'lucide-react';
import { API_BASE, useApi } from '@/lib/api';
import { useResearch } from '@/components/ResearchStore';
import { ErrorNotice, Loading, StatusBadge } from '@/components/Feedback';
import type { Chunk, SourceDetail } from '@/data/research';

export default function DocumentInspector() {
  const { sourceId } = useParams<{ sourceId: string }>();
  const search = useSearchParams();
  const research = useResearch();
  const document = search.get('document');
  const focusedId = search.get('chunk');
  const base = `/v1/projects/${research.id}/sources/${sourceId}`;
  const { data: source, error } = useApi<SourceDetail>(
    base + (document ? '?document_id=' + document : ''),
    5000,
  );
  const documentId = document || source?.document?.document_id;
  const [offset, setOffset] = useState(0);
  const [tab, setTab] = useState('chunks');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Chunk | null>(null);
  const { data, error: chunksError } = useApi<{
    chunks: Chunk[];
    total: number;
    document_version: number;
  }>(documentId ? base + `/chunks?document_id=${documentId}&offset=${offset}&limit=50` : null);
  const { data: focus, error: focusError } = useApi<Chunk>(
    focusedId && documentId ? base + `/chunks/${focusedId}?document_id=${documentId}` : null,
  );
  const active = selected || focus;
  const sourceKind = research.sources.find((item) => item.id === sourceId)?.kind;
  const pdf = source?.original_filename.toLowerCase().endsWith('.pdf');
  if (!source)
    return (
      <section className="research-empty">
        <ErrorNotice error={error} />
        {!error && <Loading text="Opening source…" />}
      </section>
    );
  const chunks =
    data?.chunks.filter((chunk) => chunk.text.toLowerCase().includes(query.toLowerCase())) ?? [];
  return (
    <div className="workspace-scroll">
      <section className="product-page">
        <Link className="back-to-library" href={`/research/${research.id}/sources`}>
          ← Source library
        </Link>
        <div className="page-heading">
          <h1>{source.display_name}</h1>
          <StatusBadge status={source.status} />
        </div>
        <ErrorNotice error={error || chunksError || focusError} />
        {source.error_detail && <ErrorNotice error={source.error_detail} />}
        {!source.document ? (
          <div className="runs-empty">
            <h2>{source.status === 'failed' ? 'Parsing failed' : 'Processing document'}</h2>
            <p>
              {source.status === 'failed'
                ? 'Return to the source library to retry this upload.'
                : 'The worker is parsing and indexing this document. This view updates automatically.'}
            </p>
          </div>
        ) : (
          <>
            <div className="metadata-bar">
              <span>Version {source.document.version}</span>
              <span>
                {source.document.parser_name} {source.document.parser_version}
              </span>
              <span>
                {source.document.page_count == null
                  ? 'No fixed page count'
                  : source.document.page_count + ' pages'}
              </span>
              <span>{source.document.chunk_count} passages</span>
              <a
                href={API_BASE + base + '/file'}
                className="ui-button"
                target="_blank"
                rel="noopener noreferrer"
              >
                <Download size={14} />
                {sourceKind === 'web' ? 'Extracted text' : 'Original file'}
              </a>
            </div>
            {document && document !== source.current_document_id && (
              <p className="warning-notice">
                Viewing the historical document version pinned by this citation.
              </p>
            )}
            <div className="tabs" role="tablist" aria-label="Document views">
              {[
                ['chunks', 'Passages'],
                ['content', 'Parsed content'],
                ...(pdf ? [['original', 'Original PDF']] : []),
              ].map(([id, label]) => (
                <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>
                  {label}
                </button>
              ))}
            </div>
            {tab === 'chunks' && (
              <div className="inspector-layout">
                <div>
                  <input
                    className="ui-input"
                    aria-label="Search displayed passages"
                    placeholder="Search this page of passages…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  <div className="stack">
                    {chunks.map((chunk) => (
                      <button
                        className={
                          'panel chunk-card ' +
                          (active?.chunk_id === chunk.chunk_id ? 'is-selected' : '')
                        }
                        key={chunk.chunk_id}
                        onClick={() => setSelected(chunk)}
                      >
                        <span className="eyebrow">
                          Passage {chunk.sequence + 1} · {chunk.char_count} characters
                        </span>
                        <p>{chunk.text}</p>
                      </button>
                    ))}
                  </div>
                  {!data && <Loading text="Loading passages…" />}
                  {data && !chunks.length && (
                    <p className="muted">No matching passages on this page.</p>
                  )}
                  {data && (
                    <div className="toolbar pagination">
                      <button
                        className="ui-button"
                        disabled={offset === 0}
                        onClick={() => setOffset(Math.max(0, offset - 50))}
                      >
                        Previous
                      </button>
                      <span>
                        {offset + 1}–{Math.min(offset + 50, data.total)} of {data.total}
                      </span>
                      <button
                        className="ui-button"
                        disabled={offset + 50 >= data.total}
                        onClick={() => setOffset(offset + 50)}
                      >
                        Next
                      </button>
                    </div>
                  )}
                </div>
                <aside className="panel passage-inspector">
                  {active ? (
                    <>
                      <h2>Exact passage</h2>
                      <p className="eyebrow">Passage {active.sequence + 1}</p>
                      <blockquote>{active.text}</blockquote>
                      <dl>
                        <dt>Chunk ID</dt>
                        <dd>{active.chunk_id}</dd>
                        <dt>Text SHA-256</dt>
                        <dd>{active.text_sha256}</dd>
                      </dl>
                      <h3>Locator</h3>
                      <pre>{JSON.stringify(active.locator, null, 2)}</pre>
                    </>
                  ) : (
                    <p className="muted">Select a passage to inspect its text and provenance.</p>
                  )}
                </aside>
              </div>
            )}
            {tab === 'content' && (
              <article className="panel normalized-text">{source.normalized_text}</article>
            )}
            {tab === 'original' && (
              <iframe
                className="pdf-preview"
                title={source.display_name + ' original PDF'}
                src={API_BASE + base + '/file'}
              />
            )}
            <details className="panel">
              <summary>Document identity</summary>
              <dl>
                <dt>Source ID</dt>
                <dd>{source.source_id}</dd>
                <dt>Snapshot ID</dt>
                <dd>{source.document.document_id}</dd>
                <dt>Content SHA-256</dt>
                <dd>{source.content_sha256}</dd>
                <dt>Normalized text SHA-256</dt>
                <dd>
                  {source.document.normalized_text_sha256 || 'Unavailable for this legacy snapshot'}
                </dd>
              </dl>
            </details>
          </>
        )}
      </section>
    </div>
  );
}
