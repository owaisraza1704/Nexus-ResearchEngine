'use client';
import { useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, FileText, Plus, Save, X } from 'lucide-react';
import { useResearch, useResearchStore } from '@/components/ResearchStore';
import ResearchRunList from '@/components/ResearchRunList';
import SourceUpload from '@/components/SourceUpload';
import { ErrorNotice } from '@/components/Feedback';
import { api, useApi } from '@/lib/api';
import {
  MODES,
  type Job,
  type JobMode,
  type ResearchDraft,
  type SystemInfo,
} from '@/data/research';

const DESCRIPTIONS: Record<JobMode, string> = {
  agentic:
    'A bounded planner breaks your question into retrieval tasks, then combines and validates the evidence.',
  answer: 'Answer from exactly one selected source, with citations.',
  comparison:
    'Compare at least two selected sources and surface agreements, differences, and gaps.',
  synthesis: 'Combine at least two selected sources into a cited synthesis.',
  evidence: 'Retrieve passages only. No generated answer or automatic relevance judgment.',
};
export default function ResearchHome() {
  const research = useResearch();
  const { updateDraft, refresh } = useResearchStore((state) => state);
  const { data: system } = useApi<SystemInfo>('/v1/system', 10000);
  const [draft, setDraft] = useState<ResearchDraft>(research.draft);
  const [webText, setWebText] = useState(research.draft.web_urls.join('\n'));
  const [approveWeb, setApproveWeb] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const submission = useRef<{ fingerprint: string; key: string } | null>(null);
  const router = useRouter();
  const sources = research.sources.filter((source) => draft.source_ids.includes(source.id));
  const urls = webText
    .split('\n')
    .map((value) => value.trim())
    .filter(Boolean);
  const sourceCount = sources.length + urls.length;
  const wrongCount =
    !sourceCount ||
    sourceCount > (system?.max_sources ?? 5) ||
    (draft.mode === 'answer' && sourceCount !== 1) ||
    (['comparison', 'synthesis'].includes(draft.mode) && sourceCount < 2);
  const unready = sources.some((source) => source.status !== 'ready');
  const canRun =
    !!draft.question.trim() && !wrongCount && !unready && (!urls.length || approveWeb) && !busy;

  function change(changes: Partial<ResearchDraft>) {
    setDraft((current) => ({ ...current, ...changes }));
    setDirty(true);
    setSaved(false);
  }
  async function save() {
    setBusy(true);
    setError(null);
    try {
      await updateDraft(research.id, { ...draft, web_urls: urls });
      setDirty(false);
      setSaved(true);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  async function run() {
    if (!canRun) return;
    setBusy(true);
    setError(null);
    try {
      const domains = Array.from(
        new Set(
          urls.map((value) => {
            const url = new URL(value);
            if (url.protocol !== 'https:') throw new Error('Approved web sources must use HTTPS.');
            return url.hostname.toLowerCase();
          }),
        ),
      );
      const payload = {
        workspace_id: research.id,
        question: draft.question.trim(),
        mode: draft.mode,
        source_ids: draft.source_ids,
        top_k_per_source: draft.top_k,
        retrieval_strategy: draft.retrieval_strategy,
        policy: {
          allow_web: urls.length > 0 && approveWeb,
          web_urls: urls,
          allowed_domains: domains,
        },
      };
      const fingerprint = JSON.stringify(payload);
      if (submission.current?.fingerprint !== fingerprint)
        submission.current = { fingerprint, key: crypto.randomUUID() };
      await updateDraft(research.id, { ...draft, web_urls: urls });
      const job = await api<Job>('/v1/research/jobs', {
        method: 'POST',
        body: JSON.stringify({
          ...payload,
          idempotency_key: submission.current.key,
        }),
      });
      await refresh();
      router.push(`/research/${research.id}/runs/${job.job_id}`);
    } catch (failure) {
      setError(failure);
      setBusy(false);
    }
  }

  return (
    <div className="workspace-scroll">
      <div className="research-composer-page">
        <div className="workspace-intro">
          <p className="eyebrow">Research workspace</p>
          <h1>
            Turn questions into
            <br />
            <span>evidence-grounded research.</span>
          </h1>
          <p className="muted">
            {research.description || 'A dedicated space for your questions, sources, and findings.'}
          </p>
        </div>
        <section className="research-composer" aria-label="Research question composer">
          <div className="composer-question">
            <label className="eyebrow" htmlFor="research-question">
              Research question
            </label>
            <textarea
              id="research-question"
              rows={4}
              maxLength={4000}
              value={draft.question}
              onChange={(e) => change({ question: e.target.value })}
              placeholder="What do you want to understand?"
            />
          </div>
          <div className="composer-sources">
            <p className="eyebrow">Sources · {sources.length} selected</p>
            <div className="source-chips">
              {sources.map((source) => (
                <div className="source-chip" key={source.id}>
                  <FileText size={13} />
                  <span>{source.name}</span>
                  <small>{source.type}</small>
                  <button
                    aria-label={`Remove ${source.name}`}
                    onClick={() =>
                      change({
                        source_ids: draft.source_ids.filter((id) => id !== source.id),
                      })
                    }
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
              <Link className="source-picker-link" href={`/research/${research.id}/sources`}>
                <Plus size={13} /> Select sources
              </Link>
            </div>
            <SourceUpload />
          </div>
          <div className="composer-sources">
            <details>
              <summary>
                Include approved web pages <span className="muted">— optional</span>
              </summary>
              <p className="muted">
                Provide specific public HTML or text pages. Nexus will fetch only these URLs and
                their approved domains; it does not browse or search the wider web.
              </p>
              <label className="eyebrow" htmlFor="web-urls">
                HTTPS URLs · one per line · maximum {system?.max_web_sources ?? 3}
              </label>
              <textarea
                id="web-urls"
                className="ui-input"
                rows={3}
                placeholder="https://example.org/research"
                value={webText}
                onChange={(e) => {
                  setWebText(e.target.value);
                  setDirty(true);
                  setSaved(false);
                  setApproveWeb(false);
                }}
              />
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={approveWeb}
                  onChange={(e) => setApproveWeb(e.target.checked)}
                />{' '}
                I approve fetching these pages and sending their extracted text to Azure.
              </label>
            </details>
          </div>
          <div className="composer-controls">
            <div className="composer-modes" role="group" aria-label="Research mode">
              {Object.entries(MODES).map(([mode, label]) => (
                <button
                  key={mode}
                  aria-pressed={draft.mode === mode}
                  onClick={() => change({ mode: mode as JobMode })}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="composer-submit">
              <label htmlFor="retrieval-strategy">Retrieval</label>
              <select
                id="retrieval-strategy"
                value={draft.retrieval_strategy}
                onChange={(e) =>
                  change({
                    retrieval_strategy: e.target.value as ResearchDraft['retrieval_strategy'],
                  })
                }
              >
                <option value="hybrid">Hybrid · keywords + vectors</option>
                <option value="vector">Vector only</option>
              </select>
              <label htmlFor="top-k">Passages / source</label>
              <select
                id="top-k"
                value={draft.top_k}
                onChange={(e) => change({ top_k: Number(e.target.value) })}
              >
                {[1, 2, 4, 8, 12, 16, 20].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
              <button className="ui-button ui-button-primary" disabled={!canRun} onClick={run}>
                {busy ? 'Saving…' : 'Run Research'}
                <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </section>
        <p className="muted mode-description">{DESCRIPTIONS[draft.mode]}</p>
        {wrongCount && (
          <p className="draft-notice">
            Select{' '}
            {draft.mode === 'answer'
              ? 'exactly one source'
              : ['comparison', 'synthesis'].includes(draft.mode)
                ? 'at least two sources'
                : 'at least one source'}
            ; up to {system?.max_sources ?? 5} total sources per run.
          </p>
        )}
        {unready && (
          <p className="warning-notice">
            A selected source is still processing or has failed. Wait for it or change your
            selection.
          </p>
        )}
        {system?.worker_count === 0 && (
          <p className="warning-notice">
            Worker not responding. New runs stay saved until delivery resumes.
          </p>
        )}
        <div className="draft-actions">
          <button className="ui-button" onClick={save} disabled={busy || !dirty}>
            <Save size={14} /> Save draft
          </button>
          <span className="draft-notice">
            {saved
              ? 'Draft saved to your local database.'
              : dirty
                ? 'Unsaved draft changes. Save before leaving this page.'
                : 'Draft saved locally. Accepted jobs continue if you close this tab.'}
          </span>
        </div>
        <ErrorNotice error={error} />
        <section className="recent-runs">
          <div className="section-heading">
            <h2>Runs in this research</h2>
            <Link href={`/research/${research.id}/runs`}>
              View all runs
              <ArrowRight size={13} />
            </Link>
          </div>
          <ResearchRunList runs={research.runs.slice(0, 5)} />
        </section>
      </div>
    </div>
  );
}
