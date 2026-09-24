'use client';
import { useState } from 'react';
import { useResearch } from '@/components/ResearchStore';
import ResearchRunList from '@/components/ResearchRunList';
export default function ResearchRuns() {
  const research = useResearch();
  const [filter, setFilter] = useState('');
  return (
    <div className="workspace-scroll">
      <section className="product-page">
        <p className="eyebrow">Research history</p>
        <h1>Research runs</h1>
        <p className="muted">Reopen results or follow work still running in the backend.</p>
        <input
          className="ui-input"
          aria-label="Search runs"
          placeholder="Search questions…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <ResearchRunList
          runs={research.runs.filter((run) =>
            run.question.toLowerCase().includes(filter.toLowerCase()),
          )}
        />
      </section>
    </div>
  );
}
