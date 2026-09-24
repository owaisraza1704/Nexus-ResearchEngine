'use client';
import type { ReactNode } from 'react';
import Link from 'next/link';
import Layout from './Layout';
import { CurrentResearchContext } from './ResearchStore';
import { ErrorNotice, Loading } from './Feedback';
import { useApi } from '@/lib/api';
import type { Research } from '@/data/research';
export default function ResearchScope({
  researchId,
  children,
}: {
  researchId: string;
  children: ReactNode;
}) {
  const {
    data: research,
    error,
    isLoading,
    mutate,
  } = useApi<Research>('/v1/projects/' + researchId, 3000);
  if (!research) {
    return (
      <main className="research-empty research-not-found">
        {isLoading ? (
          <Loading text="Opening research…" />
        ) : (
          <>
            <h1>{error?.status === 404 ? 'Research not found' : 'Research is unavailable'}</h1>
            <ErrorNotice error={error} />
            <button className="ui-button" onClick={() => mutate()}>
              Try again
            </button>
            <Link className="ui-button" href="/research">
              Back to all research
            </Link>
          </>
        )}
      </main>
    );
  }
  return (
    <CurrentResearchContext.Provider value={research}>
      <Layout key={research.id}>
        <ErrorNotice
          error={
            error &&
            new Error(
              'Connection interrupted. Showing the last saved workspace; reconnect to see new progress.',
            )
          }
        />
        {children}
      </Layout>
    </CurrentResearchContext.Provider>
  );
}
