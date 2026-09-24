import Link from 'next/link';
import { ArrowUpRight } from 'lucide-react';

export default function ResearchLibraryHeader() {
  return (
    <header className="library-header">
      <Link href="/" className="nexus-brand" aria-label="Nexus home">
        <span className="nexus-mark">N</span>NEXUS
      </Link>
      <Link href="/research" className="library-header-current">
        Research library
      </Link>
      <div className="library-header-end">
        <span className="local-badge">Your local research library</span>
        <Link href="/" className="library-home-link">
          About Nexus <ArrowUpRight size={14} />
        </Link>
      </div>
    </header>
  );
}
