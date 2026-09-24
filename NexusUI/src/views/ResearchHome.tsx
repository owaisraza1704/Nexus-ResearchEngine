'use client';

import Link from 'next/link';
import { ArrowRight, FileText, Plus, Upload, X } from 'lucide-react';
import { useResearch, useResearchStore } from '@/components/ResearchStore';
import ResearchRunList from '@/components/ResearchRunList';
import type { ResearchDraft } from '@/data/research';

const MODES: ResearchDraft['mode'][] = [
  'Grounded Answer',
  'Multi-Document',
  'Evidence Only',
];

export default function ResearchHome() {
  const research = useResearch();
  const updateDraft = useResearchStore((state) => state.updateDraft);
  const { draft } = research;
  const sources = research.sources.filter((source) =>
    draft.sourceIds.includes(source.id),
  );

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
            {research.description ||
              'A dedicated space for your questions, sources, and findings.'}
          </p>
        </div>

        <section
          className="research-composer"
          aria-label="Research question composer"
        >
          <div className="composer-question">
            <label className="eyebrow" htmlFor="research-question">
              Research question
            </label>
            <textarea
              id="research-question"
              value={draft.question}
              onChange={(event) =>
                updateDraft(research.id, { question: event.target.value })
              }
              placeholder="Ask Nexus anything... What do you want to research?"
              rows={4}
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
                      updateDraft(research.id, {
                        sourceIds: draft.sourceIds.filter(
                          (id) => id !== source.id,
                        ),
                      })
                    }
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
              <Link
                className="source-picker-link"
                href={`/research/${research.id}/sources`}
              >
                <Plus size={13} /> Select sources
              </Link>
            </div>
            <div className="upload-preview">
              <Upload size={14} /> PDF and DOCX uploads will be available when
              the backend is connected.
            </div>
          </div>
          <div className="composer-controls">
            <div
              className="composer-modes"
              role="group"
              aria-label="Research mode"
            >
              {MODES.map((mode) => (
                <button
                  key={mode}
                  aria-pressed={draft.mode === mode}
                  onClick={() => updateDraft(research.id, { mode })}
                >
                  {mode}
                </button>
              ))}
            </div>
            <div className="composer-submit">
              <label htmlFor="top-k">Top-K</label>
              <select
                id="top-k"
                value={draft.topK}
                onChange={(event) =>
                  updateDraft(research.id, { topK: Number(event.target.value) })
                }
              >
                {[4, 8, 12, 16, 24].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
              <button
                className="ui-button ui-button-primary"
                disabled
                title="Research generation is not connected to the backend yet."
              >
                Run Research <ArrowRight size={14} />
              </button>
            </div>
          </div>
        </section>
        <p className="draft-notice">
          Draft and source selection saved in this browser. Running research is
          not connected yet.
        </p>

        <section className="recent-runs">
          <div className="section-heading">
            <h2>Runs in this research</h2>
            <Link href={`/research/${research.id}/runs`}>
              View all runs <ArrowRight size={13} />
            </Link>
          </div>
          <ResearchRunList />
        </section>
      </div>
    </div>
  );
}
