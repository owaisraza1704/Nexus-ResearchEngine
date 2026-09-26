'use client';
import { useState } from 'react';
import { useResearch } from '@/components/ResearchStore';
import { ErrorNotice, Loading, StatusBadge } from '@/components/Feedback';
import ResultContent from '@/components/ResultContent';
import { useApi } from '@/lib/api';
import { hasResult, formatDate, type Result } from '@/data/research';

export default function Reports() {
  const research = useResearch();
  const runs = research.runs.filter((run) => hasResult(run.status));
  const [runId, setRunId] = useState('');
  const selected = runId || runs[0]?.id;
  const { data: result, error } = useApi<Result>(
    selected ? '/v1/research/jobs/' + selected + '/result' : null,
  );
  return (
    <div className="workspace-scroll">
      <section className="product-page">
        <p className="eyebrow">A lasting record</p>
        <h1>Research reports</h1>
        <p className="muted">Reopen saved findings and export the exact evidence-backed result.</p>
        {!runs.length ? (
          <div className="runs-empty">
            <h2>No reports yet</h2>
            <p>A validated result is saved here when research completes.</p>
          </div>
        ) : (
          <>
            <label className="field-label" htmlFor="report-run">
              Select a report
            </label>
            <select
              id="report-run"
              className="ui-input"
              value={selected}
              onChange={(e) => setRunId(e.target.value)}
            >
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.question} · {formatDate(run.created_at)}
                </option>
              ))}
            </select>
            <ErrorNotice error={error} />
            {!result && !error && <Loading />}
            {result && (
              <article className="report-document" key={result.job_id}>
                <StatusBadge status={result.status} outcome={result.outcome} />
                <h2>{result.question}</h2>
                <ResultContent result={result} />
              </article>
            )}
          </>
        )}
      </section>
    </div>
  );
}
