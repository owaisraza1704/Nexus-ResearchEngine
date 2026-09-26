'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useApi } from '@/lib/api';
import { useResearch } from '@/components/ResearchStore';
import { ErrorNotice, Loading, StatusBadge } from '@/components/Feedback';
import ResultContent from '@/components/ResultContent';
import ResearchJob from './ResearchJob';
import { MODES, hasResult, type Job, type Result } from '@/data/research';

export default function ResearchResult() {
  const { runId } = useParams<{ runId: string }>();
  const research = useResearch();
  const { data: job, error, mutate } = useApi<Job>(`/v1/research/jobs/${runId}`, 2000);
  const completed = !!job && hasResult(job.status);
  const { data: result, error: resultError } = useApi<Result>(
    completed && job.workspace_id === research.id ? `/v1/research/jobs/${runId}/result` : null,
  );
  const [view, setView] = useState('result');
  if (!job)
    return (
      <section className="research-empty">
        <ErrorNotice error={error} />
        {!error && <Loading text="Opening research run…" />}
        <Link className="ui-button" href={`/research/${research.id}/runs`}>
          All runs
        </Link>
      </section>
    );
  if (job.workspace_id !== research.id)
    return (
      <section className="research-empty">
        <h1>Run not found in this research</h1>
        <Link className="ui-button" href={`/research/${research.id}/runs`}>
          All runs
        </Link>
      </section>
    );
  return (
    <div className="workspace-scroll">
      <section className="product-page run-page">
        <Link className="back-to-library" href={`/research/${research.id}/runs`}>
          ← Research runs
        </Link>
        <div className="page-heading">
          <p className="eyebrow">{MODES[job.mode]}</p>
          <StatusBadge status={job.status} outcome={job.outcome} />
        </div>
        <h1>{job.question}</h1>
        <p className="run-identity">Run {job.job_id}</p>
        <ErrorNotice error={error || resultError} />
        {job.error && <ErrorNotice error={job.error.code + ': ' + job.error.message} />}
        {job.status === 'cancelled' && (
          <p className="warning-notice">
            This run was cancelled. No unfinished draft answer is presented as a result.
          </p>
        )}
        {completed && (
          <div className="tabs" role="tablist" aria-label="Run details">
            <button role="tab" aria-selected={view === 'result'} onClick={() => setView('result')}>
              Result
            </button>
            <button
              role="tab"
              aria-selected={view === 'execution'}
              onClick={() => setView('execution')}
            >
              Plan & execution
            </button>
          </div>
        )}
        {completed && view === 'result' ? (
          result ? (
            <ResultContent result={result} />
          ) : (
            <Loading text="Loading validated result…" />
          )
        ) : (
          <ResearchJob job={job} onChange={() => mutate()} />
        )}
      </section>
    </div>
  );
}
