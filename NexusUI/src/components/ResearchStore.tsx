'use client';
import { createContext, useContext, type ReactNode } from 'react';
import { useSWRConfig } from 'swr';
import { api, useApi } from '@/lib/api';
import type { Research, ResearchDraft } from '@/data/research';
type ResearchState = {
  researches: Research[];
  loading: boolean;
  error: Error | undefined;
  refresh: () => Promise<unknown>;
  createResearch: (title: string, description: string) => Promise<string>;
  updateDraft: (researchId: string, draft: ResearchDraft) => Promise<void>;
};
const ResearchStoreContext = createContext<ResearchState | null>(null);
export const CurrentResearchContext = createContext<Research | null>(null);
export function ResearchStoreProvider({ children }: { children: ReactNode }) {
  const { data, error, isLoading, mutate } = useApi<{ projects: Research[] }>(
    '/v1/projects?limit=100',
    5000,
  );
  const { mutate: updateCache } = useSWRConfig();
  const state: ResearchState = {
    researches: data?.projects ?? [],
    loading: isLoading,
    error,
    refresh: () => updateCache((key) => typeof key === 'string' && key.startsWith('/v1/projects')),
    createResearch: async (title, description) => {
      const project = await api<Research>('/v1/projects', {
        method: 'POST',
        body: JSON.stringify({ title, description }),
      });
      await updateCache('/v1/projects/' + project.id, project, false);
      await mutate();
      return project.id;
    },
    updateDraft: async (researchId, draft) => {
      const path = '/v1/projects/' + researchId;
      await updateCache<Research | undefined>(
        path,
        api<Research>(path, { method: 'PATCH', body: JSON.stringify({ draft }) }),
        {
          optimisticData: (current) => current && { ...current, draft },
          rollbackOnError: true,
          revalidate: false,
        },
      );
      await mutate();
    },
  };
  return <ResearchStoreContext.Provider value={state}>{children}</ResearchStoreContext.Provider>;
}
export function useResearchStore<T>(selector: (state: ResearchState) => T) {
  const state = useContext(ResearchStoreContext);
  if (!state) throw new Error('ResearchStoreProvider is required.');
  return selector(state);
}
export function useResearch() {
  const research = useContext(CurrentResearchContext);
  if (!research) throw new Error('A research workspace is required.');
  return research;
}
