'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  BookOpen,
  FileText,
  FolderOpen,
  LayoutGrid,
  List,
  Plus,
  Search,
} from 'lucide-react';
import ResearchLibraryHeader from '@/components/ResearchLibraryHeader';
import { useResearchStore } from '@/components/ResearchStore';

export default function ResearchLibrary() {
  const researches = useResearchStore((state) => state.researches);
  const [query, setQuery] = useState('');
  const [view, setView] = useState<'grid' | 'list'>('grid');
  const filtered = researches
    .filter((research) =>
      `${research.title} ${research.description}`
        .toLowerCase()
        .includes(query.toLowerCase()),
    )
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));

  return (
    <div className="research-library-page">
      <ResearchLibraryHeader />
      <main className="library-main">
        <div className="library-intro">
          <div>
            <p className="eyebrow">Your research, connected</p>
            <h1>A space for every question.</h1>
            <p>
              Keep your sources, questions, and findings together. Pick up where
              you left off.
            </p>
          </div>
          <Link className="ui-button ui-button-primary" href="/research/new">
            <Plus size={17} /> New Research
          </Link>
        </div>
        <div className="library-toolbar">
          <h2>
            All research <span>{researches.length}</span>
          </h2>
          <div className="library-tools">
            <label className="research-search">
              <Search size={16} />
              <input
                aria-label="Search research"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search research…"
              />
            </label>
            <div
              className="view-switch"
              role="group"
              aria-label="Research view"
            >
              <button
                aria-label="Grid view"
                aria-pressed={view === 'grid'}
                onClick={() => setView('grid')}
              >
                <LayoutGrid size={16} />
              </button>
              <button
                aria-label="List view"
                aria-pressed={view === 'list'}
                onClick={() => setView('list')}
              >
                <List size={17} />
              </button>
            </div>
          </div>
        </div>
        <div
          className={`research-cards ${
            view === 'list' ? 'research-cards-list' : ''
          }`}
        >
          {filtered.map((research) => (
            <article className="research-card" key={research.id}>
              <div className="research-card-top">
                <div className="research-card-icon">
                  <BookOpen size={21} />
                </div>
                <span
                  className={`status-pill ${
                    research.runs.length ? '' : 'status-draft'
                  }`}
                >
                  {research.runs.length ? 'Sample results' : 'Draft'}
                </span>
              </div>
              <div className="research-card-description">
                <h3>
                  <Link href={`/research/${research.id}`}>
                    {research.title}
                  </Link>
                </h3>
                <p>
                  {research.description ||
                    'Your next research starts with a question.'}
                </p>
              </div>
              <div className="research-card-meta">
                <span>
                  <FileText size={13} />
                  {research.sources.length}{' '}
                  {research.sources.length === 1 ? 'source' : 'sources'}
                </span>
                <span>
                  {research.runs.length}{' '}
                  {research.runs.length === 1 ? 'run' : 'runs'}
                </span>
              </div>
              <div className="research-card-footer">
                <span>
                  Updated{' '}
                  {new Intl.DateTimeFormat('en', {
                    month: 'short',
                    day: 'numeric',
                    timeZone: 'UTC',
                  }).format(new Date(research.updatedAt))}
                </span>
                <Link
                  href={`/research/${research.id}`}
                  aria-label={`Open ${research.title}`}
                >
                  Open research <ArrowRight size={15} />
                </Link>
              </div>
            </article>
          ))}
          {!query && (
            <Link className="new-research-card" href="/research/new">
              <span>
                <Plus size={23} />
              </span>
              <h3>Start something new</h3>
              <p>A fresh space for your next question.</p>
            </Link>
          )}
        </div>
        {filtered.length === 0 && (
          <div className="research-empty">
            <FolderOpen size={28} />
            <h2>No matching research</h2>
            <p>Try another title or start a new research.</p>
          </div>
        )}
        <p className="library-footnote">
          Your changes stay in this browser. The example researches are here to
          explore the interface.
        </p>
      </main>
    </div>
  );
}
