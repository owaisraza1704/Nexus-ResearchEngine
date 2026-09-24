import ResearchGraph from '@/views/ResearchGraph';
import ResearchPreview from '@/components/ResearchPreview';

export default function GraphPage() {
  return (
    <ResearchPreview title="Research graph">
      <ResearchGraph />
    </ResearchPreview>
  );
}
