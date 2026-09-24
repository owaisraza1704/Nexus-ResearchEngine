import type { ReactNode } from 'react';
import { ResearchStoreProvider } from '@/components/ResearchStore';

export default function ResearchLayout({ children }: { children: ReactNode }) {
  return <ResearchStoreProvider>{children}</ResearchStoreProvider>;
}
