'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import Layout from './Layout';
import { CurrentResearchContext, useResearchStore } from './ResearchStore';

export default function ResearchScope({
  researchId,
  children,
}: {
  researchId: string;
  children: ReactNode;
}) {
  const research = useResearchStore((state) =>
    state.researches.find((item) => item.id === researchId),
  );

  if (!research) {
    return (
      <main className="research-empty research-not-found">
        <h1>Research not found</h1>
        <p>This research is not saved in this browser.</p>
        <Link className="ui-button ui-button-primary" href="/research">
          Back to all research
        </Link>
      </main>
    );
  }

  return (
    <CurrentResearchContext.Provider value={research}>
      <Layout key={research.id}>{children}</Layout>
    </CurrentResearchContext.Provider>
  );
}
