'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import ResearchRunList from '@/components/ResearchRunList';
import { useResearch } from '@/components/ResearchStore';
import { DEMO_RESEARCH_ID } from '@/data/research';

export default function ResearchRuns() {
  const research = useResearch();
  return (
    <div className="workspace-scroll">
      <div className="research-composer-page">
        <p className="eyebrow">{research.title}</p>
        <h1 className="workspace-page-title">Research runs</h1>
        <p className="muted">
          Each question is a run. All runs here belong to this research.
        </p>
        <ResearchRunList />
        {research.id === DEMO_RESEARCH_ID && (
          <Link
            className="workflow-preview-link"
            href={`/research/${research.id}/workflow`}
          >
            Explore the future workflow preview <ArrowRight size={14} />
          </Link>
        )}
      </div>
    </div>
  );
}
