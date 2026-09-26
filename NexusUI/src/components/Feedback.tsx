'use client';
import { AlertCircle, LoaderCircle } from 'lucide-react';
import { hasResult, statusLabel, type ResultOutcome } from '@/data/research';
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="error-notice" role="alert">
      <AlertCircle size={16} />
      <span>{error instanceof Error ? error.message : String(error)}</span>
    </div>
  );
}
export function Loading({ text = 'Loading…' }: { text?: string }) {
  return (
    <div className="loading-inline" role="status">
      <LoaderCircle size={16} className="spin" />
      {text}
    </div>
  );
}
export function StatusBadge({
  status,
  outcome,
}: {
  status: string;
  outcome?: ResultOutcome | null;
}) {
  const state = hasResult(status) && outcome === 'insufficient_context' ? outcome : status;
  return <span className={'state-badge state-' + state}>{statusLabel(status, outcome)}</span>;
}
