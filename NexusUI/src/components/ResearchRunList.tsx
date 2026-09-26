'use client';
import Link from 'next/link';
import { ArrowRight, Zap } from 'lucide-react';
import { useResearch } from './ResearchStore';
import { StatusBadge } from './Feedback';
import { formatDate, MODES, type RunSummary } from '@/data/research';
export default function ResearchRunList({ runs }: { runs?: RunSummary[] }) {
  const research = useResearch();
  const visible = runs ?? research.runs;
  if (!visible.length)
    return (
      <div className="runs-empty">
        <Zap size={22} />
        <h3>No runs yet</h3>
        <p>Choose sources and ask your first question.</p>
      </div>
    );
  return (
    <div className="run-list">
      {visible.map((run) => (
        <Link className="run-card" key={run.id} href={`/research/${research.id}/runs/${run.id}`}>
          <Zap size={17} color="#60a5fa" />
          <div>
            <h3>{run.question}</h3>
            <p>
              <StatusBadge status={run.status} outcome={run.outcome} />
              <span>{MODES[run.mode]}</span>
              <time>{formatDate(run.created_at)}</time>
            </p>
          </div>
          <ArrowRight size={16} />
        </Link>
      ))}
    </div>
  );
}
