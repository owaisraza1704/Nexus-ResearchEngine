'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, BookOpen } from 'lucide-react';
import ResearchLibraryHeader from '@/components/ResearchLibraryHeader';
import { useResearchStore } from '@/components/ResearchStore';

export default function NewResearch() {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const createResearch = useResearchStore((state) => state.createResearch);
  const router = useRouter();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return;
    const id = createResearch(title.trim(), description.trim());
    router.push(`/research/${id}`);
  }

  return (
    <div className="research-library-page">
      <ResearchLibraryHeader />
      <main className="new-research-main">
        <Link className="back-to-library" href="/research">
          <ArrowLeft size={15} /> All research
        </Link>
        <div className="research-card-icon">
          <BookOpen size={23} />
        </div>
        <h1>Make room for a new question.</h1>
        <p className="muted">
          Give your research a name. Its sources, drafts, and runs will stay
          together in one workspace.
        </p>
        <form onSubmit={handleSubmit} className="new-research-form">
          <label htmlFor="research-title">Research name</label>
          <input
            id="research-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
            maxLength={120}
            placeholder="e.g. The future of retrieval"
          />
          <label htmlFor="research-description">
            What are you exploring? <span>Optional</span>
          </label>
          <textarea
            id="research-description"
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={400}
            placeholder="A little context for your research…"
          />
          <div className="new-research-actions">
            <Link className="ui-button" href="/research">
              Cancel
            </Link>
            <button
              className="ui-button ui-button-primary"
              type="submit"
              disabled={!title.trim()}
            >
              Create research <ArrowRight size={16} />
            </button>
          </div>
        </form>
        <p className="draft-notice">
          Creates a local workspace in this browser. No account or backend
          request is involved.
        </p>
      </main>
    </div>
  );
}
