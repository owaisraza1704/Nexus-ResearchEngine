'use client';

import Link from 'next/link';
import { ArrowRight, CheckCircle2, MessagesSquare } from 'lucide-react';
import { useResearch } from './ResearchStore';

export default function ResearchRunList() {
  const research = useResearch();

  if (research.runs.length === 0) {
    return (
      <div className="runs-empty">
        <MessagesSquare size={23} />
        <h3>No runs yet</h3>
        <p>Questions and results from this research will appear here.</p>
      </div>
    );
  }

  return (
    <div className="run-list">
      {research.runs.map((run) => (
        <Link
          className="run-card"
          key={run.id}
          href={`/research/${research.id}/runs/${run.id}`}
        >
          <CheckCircle2 size={17} className="run-completed" />
          <div>
            <h3>{run.question}</h3>
            <p>
              <span className="status-pill">Sample result</span>
              <span>{run.date}</span>
            </p>
          </div>
          <ArrowRight size={16} />
        </Link>
      ))}
    </div>
  );
}
