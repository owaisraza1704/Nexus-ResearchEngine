'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { createStore } from 'zustand/vanilla';
import { useStore } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  INITIAL_RESEARCHES,
  type Research,
  type ResearchDraft,
} from '@/data/research';

type ResearchState = {
  researches: Research[];
  createResearch: (title: string, description: string) => string;
  updateDraft: (researchId: string, changes: Partial<ResearchDraft>) => void;
};

function createResearchStore() {
  return createStore<ResearchState>()(
    persist(
      (set) => ({
        researches: INITIAL_RESEARCHES,
        createResearch: (title, description) => {
          const id = crypto.randomUUID();
          const research: Research = {
            id,
            title,
            description,
            updatedAt: new Date().toISOString(),
            sources: [],
            runs: [],
            draft: {
              question: '',
              mode: 'Grounded Answer',
              topK: 8,
              sourceIds: [],
            },
          };
          set((state) => ({ researches: [research, ...state.researches] }));
          return id;
        },
        updateDraft: (researchId, changes) =>
          set((state) => ({
            researches: state.researches.map((research) =>
              research.id === researchId
                ? {
                    ...research,
                    draft: { ...research.draft, ...changes },
                    updatedAt: new Date().toISOString(),
                  }
                : research,
            ),
          })),
      }),
      {
        name: 'nexus-research-ui',
        partialize: (state) => ({ researches: state.researches }),
        // Read browser storage only after hydration so the initial HTML is stable.
        skipHydration: true,
      },
    ),
  );
}

const ResearchStoreContext = createContext<ReturnType<
  typeof createResearchStore
> | null>(null);
export const CurrentResearchContext = createContext<Research | null>(null);

export function ResearchStoreProvider({ children }: { children: ReactNode }) {
  const [store] = useState(createResearchStore);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    Promise.resolve(store.persist.rehydrate()).then(() => setReady(true));
  }, [store]);

  return (
    <ResearchStoreContext.Provider value={store}>
      {ready ? (
        children
      ) : (
        <div className="research-loading" role="status">
          Opening your research library…
        </div>
      )}
    </ResearchStoreContext.Provider>
  );
}

export function useResearchStore<T>(selector: (state: ResearchState) => T) {
  const store = useContext(ResearchStoreContext);
  if (!store) throw new Error('ResearchStoreProvider is required.');
  return useStore(store, selector);
}

export function useResearch() {
  const research = useContext(CurrentResearchContext);
  if (!research) throw new Error('A research workspace is required.');
  return research;
}
