'use client';
import { useState } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import { ArrowUpRight, Download, X } from 'lucide-react';
import { API_BASE } from '@/lib/api';
import { StatusBadge } from './Feedback';
import { readable, type EvidenceItem, type Result } from '@/data/research';

export function EvidenceDetail({ item, researchId }: { item: EvidenceItem; researchId: string }) {
  return (
    <section className="panel evidence-detail" id={'evidence-' + item.label}>
      <p className="eyebrow">
        [{item.label}] · document version {item.document_version}
      </p>
      <h3>{item.display_text}</h3>
      <blockquote>{item.excerpt}</blockquote>
      <Link
        className="ui-button"
        href={`/research/${researchId}/sources/${item.source_id}?document=${item.document_id}&chunk=${item.chunk_id}`}
      >
        Open exact passage
        <ArrowUpRight size={14} />
      </Link>
      <details>
        <summary>Saved provenance</summary>
        <dl>
          <dt>Source</dt>
          <dd>{item.source_id}</dd>
          <dt>Document</dt>
          <dd>{item.document_id}</dd>
          <dt>Chunk</dt>
          <dd>{item.chunk_id}</dd>
        </dl>
        <pre>{JSON.stringify(item.locator, null, 2)}</pre>
      </details>
    </section>
  );
}

function CitedMarkdown({ content, onCite }: { content: string; onCite: (label: string) => void }) {
  const linked = content.replace(/\[(E\d+)\](?!\()/g, '[$1](#evidence-$1)');
  return (
    <div className="markdown">
      <ReactMarkdown
        components={{
          a: ({ href, children }) =>
            href?.startsWith('#evidence-') ? (
              <button className="citation-button" onClick={() => onCite(href.slice(10))}>
                [{children}]
              </button>
            ) : (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            ),
          img: ({ alt }) => <span>{alt}</span>,
        }}
      >
        {linked}
      </ReactMarkdown>
    </div>
  );
}

export default function ResultContent({ result }: { result: Result }) {
  const [tab, setTab] = useState('answer');
  const [citation, setCitation] = useState<string | null>(null);
  const active = result.evidence.find((item) => item.label === citation);
  return (
    <section className="result-content">
      <div className="page-heading">
        <div>
          <h2>{result.mode === 'evidence' ? 'Retrieved evidence' : 'Research findings'}</h2>
          <p className="muted">
            {result.citations.length} citations · {result.claims.length} claims ·{' '}
            {(result.usage.duration_ms / 1000).toFixed(1)} seconds
          </p>
        </div>
        <div className="toolbar">
          <a
            className="ui-button"
            href={`${API_BASE}/v1/research/jobs/${result.job_id}/export?format=markdown`}
          >
            <Download size={14} /> Markdown
          </a>
          <a
            className="ui-button"
            href={`${API_BASE}/v1/research/jobs/${result.job_id}/export?format=json`}
          >
            JSON
          </a>
        </div>
      </div>
      {result.outcome === 'insufficient_context' && (
        <p className="warning-notice">
          Insufficient evidence for an answer. This is a recorded limitation, not a successful
          factual answer.
        </p>
      )}
      {result.mode === 'evidence' && (
        <p className="warning-notice">
          These are retrieval candidates. They have not been judged relevant or used to generate
          claims.
        </p>
      )}
      <div className="tabs" role="tablist" aria-label="Result views">
        {[
          ['answer', result.mode === 'evidence' ? 'Overview' : 'Answer & claims'],
          ['evidence', 'Evidence (' + result.evidence.length + ')'],
          ['sources', 'Source coverage'],
          ['gaps', 'Gaps (' + result.gaps.length + ')'],
        ].map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>
      <div className={active ? 'result-with-citation' : ''}>
        <div role="tabpanel">
          {tab === 'answer' && (
            <>
              <CitedMarkdown content={result.summary} onCite={setCitation} />
              {result.limitation && result.limitation !== result.summary && (
                <p className="warning-notice">{result.limitation}</p>
              )}
              <div className="stack">
                {result.claims.map((claim) => (
                  <article className="panel claim-card" key={claim.claim_id}>
                    <StatusBadge status={claim.support_status} />
                    <CitedMarkdown content={claim.text} onCite={setCitation} />
                    <div className="claim-links">
                      {claim.relationships.map((link) => (
                        <div key={link.evidence_id}>
                          <button
                            className="citation-button"
                            onClick={() => setCitation(link.label)}
                          >
                            [{link.label}]
                          </button>
                          <span>{link.relationship}</span>
                          {link.explanation && <p className="muted">{link.explanation}</p>}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
              <p className="draft-notice">
                Citations are checked against the saved source snapshots. Claim support labels are
                model judgments; review the passages before relying on a conclusion.
              </p>
            </>
          )}
          {tab === 'evidence' && (
            <div className="stack">
              {result.evidence.map((item) => (
                <EvidenceDetail
                  key={item.evidence_id}
                  item={item}
                  researchId={result.workspace_id}
                />
              ))}
              {!result.evidence.length && (
                <p className="muted">No evidence was retained for this result.</p>
              )}
            </div>
          )}
          {tab === 'sources' && (
            <div className="stack">
              {result.source_coverage.map((source) => (
                <article className="panel" key={source.source_id}>
                  <div className="page-heading">
                    <Link
                      href={`/research/${result.workspace_id}/sources/${source.source_id}?document=${source.document_id}`}
                    >
                      {source.display_name}
                    </Link>
                    <StatusBadge status={source.status} />
                  </div>
                  <p className="muted">
                    Version {source.document_version} · {source.retrieved_chunk_count} retrieved ·{' '}
                    {source.selected_chunk_count} selected · {source.evidence_count} relevant
                    passages
                  </p>
                  {source.detail && <p className="muted">{source.detail}</p>}
                </article>
              ))}
              {result.external_sources.map((source) => (
                <article className="panel" key={source.source_id}>
                  <p className="eyebrow">Approved web snapshot</p>
                  <a href={source.canonical_url} target="_blank" rel="noopener noreferrer">
                    {source.title}
                  </a>
                  <p className="muted break-word">{source.url}</p>
                  <p className="muted">Fetched {source.retrieved_at}</p>
                </article>
              ))}
            </div>
          )}
          {tab === 'gaps' && (
            <div className="stack">
              {result.gaps.length ? (
                result.gaps.map((gap) => (
                  <article className="panel gap-card" key={gap.gap_id}>
                    <p className="eyebrow">{readable(gap.reason)}</p>
                    <p>{gap.text}</p>
                  </article>
                ))
              ) : (
                <p className="muted">
                  No explicit gaps were recorded. This does not guarantee that the sources are
                  exhaustive.
                </p>
              )}
              {result.contradictions.map((item) => (
                <article className="panel gap-card" key={item.claim_id}>
                  <p className="eyebrow">Candidate contradiction · needs review</p>
                  <p>{item.text}</p>
                  <p className="muted">
                    Supports: {item.supporting_evidence.join(', ')} · Contradicts:{' '}
                    {item.contradicting_evidence.join(', ')}
                  </p>
                </article>
              ))}
            </div>
          )}
        </div>
        {active && (
          <aside className="citation-inspector">
            <button
              className="ui-button"
              aria-label="Close citation"
              onClick={() => setCitation(null)}
            >
              <X size={14} /> Close citation
            </button>
            <EvidenceDetail item={active} researchId={result.workspace_id} />
          </aside>
        )}
      </div>
    </section>
  );
}
