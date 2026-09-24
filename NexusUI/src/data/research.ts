export type ResearchSource = {
  id: string;
  name: string;
  type: 'PDF' | 'DOCX';
  pages: number;
  chunks: number;
  status: 'READY' | 'PROCESSING' | 'FAILED';
  version: string;
  date: string;
};

export type ResearchDraft = {
  question: string;
  mode: 'Grounded Answer' | 'Multi-Document' | 'Evidence Only';
  topK: number;
  sourceIds: string[];
};

export type Research = {
  id: string;
  title: string;
  description: string;
  updatedAt: string;
  sources: ResearchSource[];
  draft: ResearchDraft;
  runs: {
    id: string;
    question: string;
    date: string;
  }[];
};

export const DEMO_RESEARCH_ID = 'transformer-architectures';

// These are interface examples, not records fetched from the research API.
export const INITIAL_RESEARCHES: Research[] = [
  {
    id: DEMO_RESEARCH_ID,
    title: 'Transformer architectures',
    description:
      'Understand attention mechanisms, architectural trade-offs, and the evidence behind them.',
    updatedAt: '2026-09-24T14:30:00Z',
    sources: [
      {
        id: 'src-001',
        name: 'architecture.pdf',
        type: 'PDF',
        pages: 42,
        chunks: 128,
        status: 'READY',
        version: 'v1',
        date: '2026-09-22',
      },
      {
        id: 'src-002',
        name: 'research-paper.pdf',
        type: 'PDF',
        pages: 28,
        chunks: 84,
        status: 'READY',
        version: 'v1',
        date: '2026-09-21',
      },
      {
        id: 'src-003',
        name: 'design-notes.docx',
        type: 'DOCX',
        pages: 15,
        chunks: 47,
        status: 'READY',
        version: 'v2',
        date: '2026-09-20',
      },
      {
        id: 'src-004',
        name: 'retrieval-eval.pdf',
        type: 'PDF',
        pages: 61,
        chunks: 0,
        status: 'PROCESSING',
        version: 'v1',
        date: '2026-09-24',
      },
      {
        id: 'src-005',
        name: 'legacy-spec.docx',
        type: 'DOCX',
        pages: 8,
        chunks: 0,
        status: 'FAILED',
        version: 'v1',
        date: '2026-09-19',
      },
    ],
    draft: {
      question: '',
      mode: 'Grounded Answer',
      topK: 8,
      sourceIds: ['src-001', 'src-002'],
    },
    runs: [
      {
        id: 'run-001',
        question:
          'How does the transformer attention mechanism differ between encoder-only and decoder-only architectures?',
        date: '2026-09-24',
      },
    ],
  },
  {
    id: 'retrieval-strategies',
    title: 'Retrieval strategies',
    description:
      'Explore how dense, sparse, and hybrid retrieval find the right context for a question.',
    updatedAt: '2026-09-23T10:00:00Z',
    sources: [
      {
        id: 'src-retrieval',
        name: 'retrieval-notes.pdf',
        type: 'PDF',
        pages: 12,
        chunks: 36,
        status: 'READY',
        version: 'v1',
        date: '2026-09-23',
      },
    ],
    draft: {
      question: 'When does hybrid retrieval outperform dense retrieval?',
      mode: 'Grounded Answer',
      topK: 8,
      sourceIds: ['src-retrieval'],
    },
    runs: [],
  },
  {
    id: 'document-understanding',
    title: 'Document understanding',
    description:
      'A space to investigate parsing, document structure, and context-aware chunking.',
    updatedAt: '2026-09-22T09:00:00Z',
    sources: [],
    draft: { question: '', mode: 'Grounded Answer', topK: 8, sourceIds: [] },
    runs: [],
  },
];
