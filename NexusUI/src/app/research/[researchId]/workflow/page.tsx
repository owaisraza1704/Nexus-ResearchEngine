import { redirect } from 'next/navigation';
export default async function WorkflowPage({
  params,
}: {
  params: Promise<{ researchId: string }>;
}) {
  const { researchId } = await params;
  redirect(`/research/${researchId}/runs`);
}
