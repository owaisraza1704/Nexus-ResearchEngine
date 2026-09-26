'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useResearch } from '@/components/ResearchStore';
import { ErrorNotice, Loading, StatusBadge } from '@/components/Feedback';
import { api, useApi } from '@/lib/api';
import { hasResult, readable, type Result, type ResultOutcome } from '@/data/research';

type EvaluationData = {
  job_count: number;
  statuses: Record<string, number>;
  rejected_plans: number;
  provider_calls: number;
  input_tokens: number;
  output_tokens: number;
  unknown_usage_calls: number;
  review_count: number;
  human_scores: Record<string, number | null>;
  runs: {
    job_id: string;
    question: string;
    status: string;
    outcome: ResultOutcome | null;
    mode: string;
    duration_ms: number | null;
    provider_calls: number;
    reviewed: boolean;
  }[];
  note: string;
};
const DIMENSIONS = ['groundedness', 'relevance', 'citation_quality'] as const;
function ReviewForm({ result, onSaved }: { result: Result; onSaved: () => void }) {
  const [scores, setScores] = useState<Record<string, string>>({
    groundedness: result.review?.groundedness.toString() ?? '',
    relevance: result.review?.relevance.toString() ?? '',
    citation_quality: result.review?.citation_quality.toString() ?? '',
  });
  const [notes, setNotes] = useState(result.review?.notes ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api('/v1/research/jobs/' + result.job_id + '/review', {
        method: 'PUT',
        body: JSON.stringify({
          ...Object.fromEntries(
            DIMENSIONS.map((dimension) => [dimension, Number(scores[dimension])]),
          ),
          notes,
        }),
      });
      setSaved(true);
      onSaved();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="panel review-form" onSubmit={save}>
      <h2>Your assessment</h2>
      <p className="muted">
        Read the result and its cited passages first. 1 = poor, 3 = mixed, 5 = strong. These scores
        are yours, not automatic quality guarantees.
      </p>
      <Link
        className="ui-button"
        href={`/research/${result.workspace_id}/runs/${result.job_id}`}
        target="_blank"
      >
        Review result and evidence ↗
      </Link>
      <div className="review-dimensions">
        {DIMENSIONS.map((dimension) => (
          <label key={dimension} className="field-label">
            {readable(dimension)}
            <select
              className="ui-input"
              required
              value={scores[dimension]}
              onChange={(e) => {
                setScores({ ...scores, [dimension]: e.target.value });
                setSaved(false);
              }}
            >
              <option value="">Choose a score</option>
              {[1, 2, 3, 4, 5].map((score) => (
                <option key={score}>{score}</option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <label className="field-label" htmlFor="review-notes">
        Review notes
      </label>
      <textarea
        className="ui-input"
        id="review-notes"
        maxLength={4000}
        rows={3}
        value={notes}
        onChange={(e) => {
          setNotes(e.target.value);
          setSaved(false);
        }}
      />
      <ErrorNotice error={error} />
      <button className="ui-button ui-button-primary" disabled={busy}>
        {busy ? 'Saving…' : 'Save review'}
      </button>
      {saved && (
        <p className="muted" role="status">
          Review saved.
        </p>
      )}
    </form>
  );
}

export default function Evaluation() {
  const research = useResearch();
  const { data, error, mutate } = useApi<EvaluationData>(
    '/v1/projects/' + research.id + '/evaluation',
    5000,
  );
  const runs = research.runs.filter((run) => hasResult(run.status));
  const [runId, setRunId] = useState('');
  const selected = runId || runs[0]?.id;
  const {
    data: result,
    error: resultError,
    mutate: updateResult,
  } = useApi<Result>(selected ? '/v1/research/jobs/' + selected + '/result' : null);
  return (
    <div className="workspace-scroll">
      <section className="product-page">
        <p className="eyebrow">Measure, inspect, improve</p>
        <h1>Evaluation</h1>
        <p className="muted">
          Execution reliability and your assessment of completed research. No placeholder scores.
        </p>
        <ErrorNotice error={error || resultError} />
        {!data && !error && <Loading />}
        {data && (
          <>
            <div className="metric-grid">
              <div className="metric">
                <span>Runs</span>
                <strong>{data.job_count}</strong>
              </div>
              <div className="metric">
                <span>Results / insufficient evidence</span>
                <strong>
                  {data.runs.filter((run) => run.outcome === 'completed').length}
                  <small>
                    {' / '}
                    {data.runs.filter((run) => run.outcome === 'insufficient_context').length}
                  </small>
                </strong>
              </div>
              <div className="metric">
                <span>Failed / rejected plans</span>
                <strong>
                  {data.statuses.failed || 0}
                  <small> / {data.rejected_plans}</small>
                </strong>
              </div>
              <div className="metric">
                <span>Provider calls</span>
                <strong>{data.provider_calls}</strong>
              </div>
            </div>
            <p className="muted">
              {data.input_tokens.toLocaleString()} input tokens ·{' '}
              {data.output_tokens.toLocaleString()} output tokens reported ·{' '}
              {data.unknown_usage_calls} calls with unknown or in-flight usage
            </p>
            <section className="panel">
              <h2>Human review averages</h2>
              <p className="muted">{data.review_count} reviewed results · ratings out of 5</p>
              <div className="review-dimensions">
                {DIMENSIONS.map((dimension) => (
                  <div className="metric" key={dimension}>
                    <span>{readable(dimension)}</span>
                    <strong>{data.human_scores[dimension] ?? '—'}</strong>
                  </div>
                ))}
              </div>
            </section>
            <p className="warning-notice">
              {data.note} The repository's labeled retrieval and research evaluations remain
              available from the command line.
            </p>
          </>
        )}
        {runs.length > 0 && (
          <>
            <label className="field-label" htmlFor="review-run">
              Result to review
            </label>
            <select
              id="review-run"
              className="ui-input"
              value={selected}
              onChange={(e) => setRunId(e.target.value)}
            >
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.question}
                </option>
              ))}
            </select>
            {result && (
              <ReviewForm
                key={result.job_id}
                result={result}
                onSaved={() => {
                  mutate();
                  updateResult();
                }}
              />
            )}
          </>
        )}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Question</th>
                <th>Status</th>
                <th>Duration</th>
                <th>Provider calls</th>
                <th>Reviewed</th>
              </tr>
            </thead>
            <tbody>
              {data?.runs.map((run) => (
                <tr key={run.job_id}>
                  <td>
                    <Link href={`/research/${research.id}/runs/${run.job_id}`}>{run.question}</Link>
                  </td>
                  <td>
                    <StatusBadge status={run.status} outcome={run.outcome} />
                  </td>
                  <td>
                    {run.duration_ms == null ? '—' : (run.duration_ms / 1000).toFixed(1) + 's'}
                  </td>
                  <td>{run.provider_calls}</td>
                  <td>{run.reviewed ? 'Yes' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
