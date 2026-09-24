export const MODES = {
  agentic: 'Agentic Research',
  answer: 'Grounded Answer',
  comparison: 'Compare Sources',
  synthesis: 'Multi-Document Synthesis',
  evidence: 'Evidence Only',
} as const;
export type JobMode = keyof typeof MODES;
export type JobStatus =
  | 'created'
  | 'planning'
  | 'planned'
  | 'running'
  | 'cancel_requested'
  | 'cancelled'
  | 'failed'
  | 'completed'
  | 'completed_with_gaps';
export const isTerminal = (status: string) =>
  ['completed', 'completed_with_gaps', 'failed', 'cancelled'].includes(status);
export const hasResult = (status: string) => ['completed', 'completed_with_gaps'].includes(status);
export const readable = (value: string) => value.replace(/_/g, ' ');
export const formatDate = (value: string) =>
  new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
export type ResearchSource = {
  id: string;
  name: string;
  type: 'PDF' | 'DOCX' | 'WEB';
  kind: string;
  pages: number | null;
  chunks: number;
  status: 'registered' | 'processing' | 'ready' | 'failed';
  document_id: string | null;
  version: number | null;
  created_at: string;
  error_code: string | null;
  error_detail: string | null;
  attempts: number;
};
export type ResearchDraft = {
  question: string;
  mode: JobMode;
  top_k: number;
  source_ids: string[];
  web_urls: string[];
};
export type RunSummary = {
  id: string;
  question: string;
  mode: JobMode;
  status: JobStatus;
  created_at: string;
  completed_at: string | null;
};
export type Research = {
  id: string;
  title: string;
  description: string;
  updated_at: string;
  sources: ResearchSource[];
  draft: ResearchDraft;
  runs: RunSummary[];
};
export type Job = {
  job_id: string;
  workspace_id: string;
  run_id: string;
  question: string;
  mode: JobMode;
  status: JobStatus;
  progress: Record<string, number>;
  budget: Record<string, number>;
  policy: { allow_web: boolean; allowed_domains: string[]; web_urls: string[] };
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error: { code: string; message: string } | null;
};
export type Task = {
  task_id: string;
  key: string;
  type: string;
  state: string;
  optional: boolean;
  input: {
    question: string | null;
    source_ids: string[];
    url_index: number | null;
  };
  depends_on: string[];
  output_ref: Record<string, unknown>;
  candidate_count: number;
  attempt_count: number;
  max_attempts: number;
  worker_id: string | null;
  error_code: string | null;
  started_at: string | null;
  completed_at: string | null;
  attempts: {
    attempt_number: number;
    status: string;
    error_code: string | null;
    worker_id: string | null;
    started_at: string;
    completed_at: string | null;
    usage: Record<string, number>;
  }[];
};
export type EvidenceItem = {
  evidence_id: string;
  label: string;
  source_id: string;
  document_id: string;
  document_version: number;
  chunk_id: string;
  excerpt: string;
  display_text: string;
  locator: Record<string, unknown>;
};
export type Claim = {
  claim_id: string;
  text: string;
  claim_type: string;
  support_status: string;
  evidence: string[];
  relationships: {
    evidence_id: string;
    label: string;
    relationship: string;
    explanation: string | null;
  }[];
};
export type Result = {
  job_id: string;
  workspace_id: string;
  run_id: string;
  result_id: string;
  status: JobStatus;
  outcome: 'completed' | 'insufficient_context';
  mode: JobMode;
  question: string;
  summary: string;
  limitation: string | null;
  claims: Claim[];
  evidence: EvidenceItem[];
  citations: {
    citation_id: string;
    label: string;
    evidence_id: string;
    display_text: string;
    locator: Record<string, unknown>;
  }[];
  source_coverage: {
    source_id: string;
    document_id: string;
    document_version: number;
    display_name: string;
    status: string;
    retrieved_chunk_count: number;
    selected_chunk_count: number;
    evidence_count: number;
    context_limited: boolean;
    detail: string | null;
  }[];
  gaps: { gap_id: string; text: string; reason: string }[];
  contradictions: {
    claim_id: string;
    text: string;
    status: string;
    supporting_evidence: string[];
    contradicting_evidence: string[];
  }[];
  task_failures: { task_key: string; error_code: string }[];
  external_sources: {
    source_id: string;
    document_id: string;
    url: string;
    canonical_url: string;
    title: string;
    retrieved_at: string;
    content_sha256: string;
  }[];
  model: string | null;
  prompt_version: string;
  budget: Record<string, number>;
  usage: {
    duration_ms: number;
    retrieval_ms: number;
    synthesis_ms: number;
    input_tokens: number | null;
    output_tokens: number | null;
    embedding_tokens: number | null;
  };
  review: {
    groundedness: number;
    relevance: number;
    citation_quality: number;
    notes: string;
    reviewed_at: string;
  } | null;
};
export type SystemInfo = {
  deployment: string;
  worker_count: number;
  azure_configured: boolean;
  model: string | null;
  embedding_deployment: string | null;
  embedding_dimensions: number;
  supported_formats: string[];
  max_upload_bytes: number;
  max_sources: number;
  max_top_k: number;
  max_web_sources: number;
  limits: Record<string, number>;
  privacy: string;
};
export type SourceDetail = {
  source_id: string;
  display_name: string;
  original_filename: string;
  status: string;
  content_sha256: string;
  current_document_id: string | null;
  error_code: string | null;
  error_detail: string | null;
  document: {
    document_id: string;
    version: number;
    status: string;
    parser_name: string;
    parser_version: string;
    page_count: number | null;
    chunk_count: number;
    normalized_text_sha256: string | null;
  } | null;
  normalized_text: string | null;
  blocks: unknown[];
};
export type Chunk = {
  chunk_id: string;
  sequence: number;
  text: string;
  text_sha256: string;
  char_count: number;
  locator: Record<string, unknown>;
};
