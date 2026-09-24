'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useResearch } from '@/components/ResearchStore';
import { EvidenceDetail } from '@/components/ResultContent';
import { ErrorNotice, Loading } from '@/components/Feedback';
import { useApi } from '@/lib/api';
import { hasResult, type Result } from '@/data/research';

export default function Evidence() {
  const research = useResearch();
  const runs = research.runs.filter((run) => hasResult(run.status));
  const [runId, setRunId] = useState('');
  const selected = runId || runs[0]?.id;
  const [query, setQuery] = useState('');
  const { data: result, error } = useApi<Result>(
    selected ? '/v1/research/jobs/' + selected + '/result' : null,
  );
  return (
    <div className="workspace-scroll">
      <section className="product-page">
        <p className="eyebrow">Trace every finding</p>
        <h1>Evidence explorer</h1>
        <p className="muted">
          Saved passages from this research, scoped to the run that retrieved them.
        </p>
        {!runs.length ? (
          <div className="runs-empty">
            <h2>No evidence yet</h2>
            <p>Complete a research or evidence-only run to inspect passages here.</p>
          </div>
        ) : (
          <>
            <div className="toolbar">
              <select
                className="ui-input"
                aria-label="Evidence run"
                value={selected}
                onChange={(e) => setRunId(e.target.value)}
              >
                {runs.map((run) => (
                  <option key={run.id} value={run.id}>
                    {run.question}
                  </option>
                ))}
              </select>
              <input
                className="ui-input"
                aria-label="Search evidence"
                value={query}
                placeholder="Search passages…"
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <ErrorNotice error={error} />
            {!result && !error && <Loading />}
            {result && (
              <>
                <Link
                  className="back-to-library"
                  href={`/research/${research.id}/runs/${result.job_id}`}
                >
                  Open full result →
                </Link>
                {result.mode === 'evidence' && (
                  <p className="warning-notice">
                    Retrieval candidates only; relevance has not been assessed.
                  </p>
                )}
                <div className="stack">
                  {result.evidence
                    .filter((item) =>
                      (item.excerpt + item.display_text)
                        .toLowerCase()
                        .includes(query.toLowerCase()),
                    )
                    .map((item) => (
                      <EvidenceDetail key={item.evidence_id} item={item} researchId={research.id} />
                    ))}
                </div>
                {!result.evidence.length && (
                  <p className="muted">This run did not retain any relevant passages.</p>
                )}
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}
