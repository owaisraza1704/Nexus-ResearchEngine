'use client';

import type { ReactNode } from 'react';
import { FlaskConical } from 'lucide-react';
import { DEMO_RESEARCH_ID } from '@/data/research';
import { useResearch } from './ResearchStore';

export default function ResearchPreview({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const research = useResearch();

  if (research.id !== DEMO_RESEARCH_ID) {
    return (
      <section className="research-empty">
        <FlaskConical size={28} />
        <h1>{title}</h1>
        <p>No {title.toLowerCase()} data for this research yet.</p>
        <p className="muted">
          This screen is a UI preview. Live research services are not connected.
        </p>
      </section>
    );
  }

  return (
    <>
      <div className="preview-notice">
        Illustrative {title.toLowerCase()} for this demo research · not live
        backend data
      </div>
      {children}
    </>
  );
}
