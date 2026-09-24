import type { ReactNode } from 'react';
import ResearchScope from '@/components/ResearchScope';

export default async function WorkspaceLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ researchId: string }>;
}) {
  const { researchId } = await params;
  return <ResearchScope researchId={researchId}>{children}</ResearchScope>;
}
