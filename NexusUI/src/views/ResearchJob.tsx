'use client';
import { useState } from 'react';
import { useApi, api } from '@/lib/api';
import { ErrorNotice, Loading, StatusBadge } from '@/components/Feedback';
import ResearchDiagram from '@/components/ResearchDiagram';
import {
  formatDate,
  isTerminal,
  readable,
  statusLabel,
  type Job,
  type Task,
} from '@/data/research';

type JobEvent = {
  sequence: number;
  event_type: string;
  task_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};
export default function ResearchJob({ job, onChange }: { job: Job; onChange: () => void }) {
  const interval = isTerminal(job.status) ? 0 : 2000;
  const { data, error } = useApi<{ tasks: Task[] }>(
    `/v1/research/jobs/${job.job_id}/tasks`,
    interval,
  );
  const { data: plan } = useApi<{
    status: string;
    rejection_code?: string;
    planner_provider?: string;
    schema_version?: string;
  }>(`/v1/research/jobs/${job.job_id}/plan`, interval);
  const [cursor, setCursor] = useState(0);
  const { data: eventData, error: eventError } = useApi<{
    events: JobEvent[];
    next_cursor: number;
    has_more: boolean;
  }>(`/v1/research/jobs/${job.job_id}/events?after=${cursor}&limit=100`, interval);
  const [selected, setSelected] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<unknown>(null);
  const task = data?.tasks.find((item) => item.key === selected);
  const done =
    job.progress.succeeded_tasks +
    job.progress.failed_tasks +
    job.progress.cancelled_tasks +
    job.progress.skipped_tasks;
  const total = job.progress.total_tasks;
  async function cancel() {
    setCancelling(true);
    setCancelError(null);
    try {
      await api(`/v1/research/jobs/${job.job_id}/cancel`, { method: 'POST' });
      onChange();
    } catch (failure) {
      setCancelError(failure);
    } finally {
      setCancelling(false);
    }
  }
  return (
    <section className="job-monitor">
      <div className="page-heading">
        <div>
          <h2>Execution</h2>
          <p className="muted">
            {total ? `${done} of ${total} tasks settled` : 'Waiting for a validated plan'} ·{' '}
            {statusLabel(job.status, job.outcome)}
            {' · '}
            {job.retrieval_strategy === 'hybrid' ? 'Hybrid retrieval' : 'Vector retrieval'}
          </p>
        </div>
        {!isTerminal(job.status) && (
          <button
            className="ui-button danger-button"
            disabled={cancelling || job.status === 'cancel_requested'}
            onClick={cancel}
          >
            {job.status === 'cancel_requested' ? 'Cancelling…' : 'Cancel run'}
          </button>
        )}
      </div>
      <progress
        className="job-progress"
        aria-label="Research progress"
        value={done}
        max={total || 1}
      />
      {job.status === 'completed_with_gaps' && (
        <p className="warning-notice">
          {job.outcome === 'insufficient_context'
            ? 'Execution finished, but the retrieved evidence was insufficient to answer the question. Open Result → Gaps to review what is missing.'
            : 'Execution finished and produced a result with recorded limitations. Open Result → Gaps to review the unanswered points.'}
        </p>
      )}
      {!isTerminal(job.status) && (
        <p className="draft-notice">
          You may close this page. The backend worker owns this job. Cancellation stops new tasks
          and discards in-flight outputs at the next checkpoint.
        </p>
      )}
      <ErrorNotice error={cancelError || error} />
      <div className="metric-grid">
        <div className="metric">
          <span>Plan</span>
          <strong className="metric-text">{plan?.status ?? 'pending'}</strong>
        </div>
        <div className="metric">
          <span>Provider calls</span>
          <strong>
            {job.budget.used_provider_calls}
            <small> / {job.budget.max_provider_calls}</small>
          </strong>
        </div>
        <div className="metric">
          <span>Input tokens reported</span>
          <strong>{job.budget.used_input_tokens.toLocaleString()}</strong>
        </div>
        <div className="metric">
          <span>Output tokens reported</span>
          <strong>{job.budget.used_output_tokens.toLocaleString()}</strong>
        </div>
      </div>
      {(job.budget.reserved_input_tokens > 0 || job.budget.reserved_output_tokens > 0) && (
        <p className="warning-notice">
          Reserved or unconfirmed usage: {job.budget.reserved_input_tokens} input /{' '}
          {job.budget.reserved_output_tokens} output tokens. Interrupted requests may still be
          billed.
        </p>
      )}
      {plan?.status === 'rejected' && (
        <p className="error-notice">
          The planner response was rejected before any task was executed: {plan.rejection_code}.
        </p>
      )}
      {data?.tasks.length ? (
        <>
          <ResearchDiagram
            items={data.tasks.map((item) => ({
              id: item.key,
              label: readable(item.key),
              detail: readable(item.state),
              state: item.state,
            }))}
            connections={data.tasks.flatMap((item) =>
              item.depends_on.map((parent) => ({
                source: parent,
                target: item.key,
              })),
            )}
            onSelect={setSelected}
          />
          <div className="task-list">
            {data.tasks.map((item) => (
              <button
                className={'task-row ' + (selected === item.key ? 'is-selected' : '')}
                key={item.task_id}
                onClick={() => setSelected(item.key)}
              >
                <div>
                  <strong>{readable(item.key)}</strong>
                  <span>
                    {readable(item.type)}
                    {item.optional ? ' · optional source' : ''}
                  </span>
                </div>
                <StatusBadge status={item.state} />
                <span>
                  {item.attempt_count}/{item.max_attempts} attempts
                </span>
              </button>
            ))}
          </div>
          {task && (
            <section className="panel task-detail">
              <div className="page-heading">
                <h3>{readable(task.key)}</h3>
                <button className="ui-button" onClick={() => setSelected(null)}>
                  Close details
                </button>
              </div>
              {task.input.question && <p>{task.input.question}</p>}
              {task.input.url_index !== null && (
                <p className="break-word">{job.policy.web_urls[task.input.url_index]}</p>
              )}
              <p className="muted">
                Dependencies: {task.depends_on.join(', ') || 'none'} · Candidates:{' '}
                {task.candidate_count}
              </p>
              {task.error_code && <p className="error-text">{task.error_code}</p>}
              {task.attempts.map((attempt) => (
                <div className="attempt-row" key={attempt.attempt_number}>
                  <strong>Attempt {attempt.attempt_number}</strong>
                  <StatusBadge status={attempt.status} />
                  <span>{formatDate(attempt.started_at)}</span>
                  <span>{attempt.error_code}</span>
                  <span className="muted">{attempt.worker_id}</span>
                </div>
              ))}
            </section>
          )}
        </>
      ) : (
        !isTerminal(job.status) && (
          <Loading
            text={
              job.status === 'planning'
                ? 'Planning bounded research tasks…'
                : 'Job queued for the local worker…'
            }
          />
        )
      )}
      <details className="panel event-log">
        <summary>Event history</summary>
        <ErrorNotice error={eventError} />
        <ol>
          {eventData?.events.map((event) => (
            <li key={event.sequence}>
              <span className="event-sequence">#{event.sequence}</span>
              <time>{formatDate(event.created_at)}</time>
              <strong>{readable(event.event_type)}</strong>
              <span className="muted">
                {String(event.payload.task_key ?? event.payload.error_code ?? '')}
              </span>
            </li>
          ))}
        </ol>
        <div className="toolbar">
          {cursor > 0 && (
            <button className="ui-button" onClick={() => setCursor(0)}>
              First events
            </button>
          )}
          {eventData?.has_more && (
            <button className="ui-button" onClick={() => setCursor(eventData.next_cursor)}>
              Next events
            </button>
          )}
        </div>
      </details>
    </section>
  );
}
