'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useResearch } from '@/components/ResearchStore';
import ResearchDiagram from '@/components/ResearchDiagram';
import { ErrorNotice, Loading } from '@/components/Feedback';
import { EvidenceDetail } from '@/components/ResultContent';
import { useApi } from '@/lib/api';
import { hasResult, type Result } from '@/data/research';

export default function ResearchGraph() {
  const research = useResearch();
  const runs = research.runs.filter((run) => hasResult(run.status));
  const [runId, setRunId] = useState('');
  const [nodeId, setNodeId] = useState('');
  const selected = runId || runs[0]?.id;
  const { data: result, error } = useApi<Result>(
    selected ? '/v1/research/jobs/' + selected + '/result' : null,
  );
  const evidence = result?.evidence.find((item) => item.evidence_id === nodeId);
  const claim = result?.claims.find((item) => item.claim_id === nodeId);
  const source = result?.source_coverage.find((item) => item.source_id === nodeId);
  return (
    <div className="workspace-scroll">
      <section className="product-page">
        <p className="eyebrow">Follow the evidence</p>
        <h1>Research graph</h1>
        <p className="muted">
          Document snapshots → retrieved passages → claims. These are saved provenance links, not an
          inferred global knowledge graph.
        </p>
        {!runs.length ? (
          <div className="runs-empty">
            <h2>No graph yet</h2>
            <p>Complete research to explore its sources and findings.</p>
          </div>
        ) : (
          <>
            <select
              className="ui-input"
              aria-label="Graph run"
              value={selected}
              onChange={(e) => {
                setRunId(e.target.value);
                setNodeId('');
              }}
            >
              {runs.map((run) => (
                <option key={run.id} value={run.id}>
                  {run.question}
                </option>
              ))}
            </select>
            <ErrorNotice error={error} />
            {!result && !error && <Loading />}
            {result && (
              <>
                <ResearchDiagram
                  items={[
                    ...result.source_coverage.map((item) => ({
                      id: item.source_id,
                      label: item.display_name,
                      detail: 'Source · v' + item.document_version,
                    })),
                    ...result.evidence.map((item) => ({
                      id: item.evidence_id,
                      label: '[' + item.label + ']',
                      detail: item.excerpt.slice(0, 85),
                      state: 'succeeded',
                    })),
                    ...result.claims.map((item) => ({
                      id: item.claim_id,
                      label: item.text.slice(0, 85),
                      detail: item.support_status,
                      state: item.support_status,
                    })),
                  ]}
                  connections={[
                    ...result.evidence.map((item) => ({
                      source: item.source_id,
                      target: item.evidence_id,
                      label: 'contains',
                    })),
                    ...result.claims.flatMap((item) =>
                      item.relationships.map((link) => ({
                        source: link.evidence_id,
                        target: item.claim_id,
                        label: link.relationship,
                      })),
                    ),
                  ]}
                  onSelect={setNodeId}
                />
                {evidence && <EvidenceDetail item={evidence} researchId={research.id} />}
                {claim && (
                  <article className="panel">
                    <h2>{claim.text}</h2>
                    <p className="muted">
                      Support assessment: {claim.support_status} · evidence{' '}
                      {claim.evidence.join(', ')}
                    </p>
                  </article>
                )}
                {source && (
                  <article className="panel">
                    <h2>{source.display_name}</h2>
                    <Link
                      href={`/research/${research.id}/sources/${source.source_id}?document=${source.document_id}`}
                    >
                      Inspect source snapshot →
                    </Link>
                  </article>
                )}
              </>
            )}
          </>
        )}
      </section>
    </div>
  );
}
