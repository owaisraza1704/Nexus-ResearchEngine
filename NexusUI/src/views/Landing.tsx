import Link from 'next/link';
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  FileText,
  GitBranch,
  Layers,
  Quote,
  Search,
} from 'lucide-react';
import { DEMO_RESEARCH_ID } from '@/data/research';

export default function Landing() {
  return (
    <div className="landing">
      <header className="landing-header">
        <Link className="nexus-brand" href="/" aria-label="Nexus home">
          <span className="nexus-mark">N</span>NEXUS
        </Link>
        <nav aria-label="Main navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#features">Features</a>
          <a href="#philosophy">Our philosophy</a>
        </nav>
        <Link
          className="ui-button ui-button-primary landing-nav-cta"
          href="/research"
        >
          Open research <ArrowUpRight size={14} />
        </Link>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-hero-copy">
            <div className="landing-kicker">
              <span /> An evidence-first research workspace
            </div>
            <h1>
              Research as a<br />
              <em>connected story,</em>
              <br />
              not a collection
              <br />
              of answers.
            </h1>
            <p className="landing-description">
              Bring your sources, questions, and discoveries into one place.
              Follow the evidence. Build understanding that stays connected.
            </p>
            <div className="landing-hero-actions">
              <Link className="ui-button ui-button-primary" href="/research">
                Start researching <ArrowRight size={16} />
              </Link>
              <Link
                className="ui-button"
                href={`/research/${DEMO_RESEARCH_ID}`}
              >
                Explore demo
              </Link>
            </div>
            <p className="landing-hero-note">
              Start with a question. Keep the bigger picture.
            </p>
          </div>

          <div
            className="landing-preview"
            aria-label="Illustration of sources connected to evidence and an answer"
          >
            <div className="preview-floating preview-context">
              <span className="preview-floating-label">Research context</span>
              <strong>
                <span className="preview-blue-dot" /> Transformer architectures
              </strong>
              <span>One question. Connected sources.</span>
            </div>
            <div className="preview-window">
              <div className="preview-window-heading">
                <span>RESEARCH WORKSPACE</span>
                <span className="preview-example">Example</span>
              </div>
              <h2>How do attention mechanisms differ?</h2>
              <div className="preview-progress">
                <span />
                <span />
                <span />
              </div>
              <div className="preview-source-label">
                <FileText size={12} /> YOUR SOURCES
              </div>
              <div className="preview-documents">
                <div>
                  <FileText size={22} />
                  <strong>Architecture</strong>
                  <span>Research paper</span>
                </div>
                <div>
                  <FileText size={22} />
                  <strong>Attention</strong>
                  <span>Technical notes</span>
                </div>
                <div>
                  <FileText size={22} />
                  <strong>Transformers</strong>
                  <span>Literature review</span>
                </div>
              </div>
              <div className="preview-connectors" aria-hidden="true">
                <i />
                <i />
                <i />
              </div>
              <div className="preview-evidence">
                <div className="preview-evidence-title">
                  <Search size={13} />
                  <span>Relevant evidence</span>
                  <CheckCircle2 size={14} />
                </div>
                <p>
                  “Bidirectional attention considers the full context of a
                  sequence…” <span>[C1]</span>
                </p>
                <div className="preview-evidence-footer">
                  <span>architecture.pdf</span>
                  <span>Page 7 · Chunk 018</span>
                </div>
              </div>
              <div className="preview-answer-connector" aria-hidden="true" />
              <div className="preview-answer">
                <span>
                  <Quote size={13} /> A GROUNDED ANSWER
                </span>
                <p>
                  Different architectures, different ways of attending to
                  context. Every insight linked to its source.
                </p>
              </div>
            </div>
            <div className="preview-floating preview-trace">
              <div className="preview-trace-icon">
                <GitBranch size={18} />
              </div>
              <div>
                <strong>Follow the evidence</strong>
                <span>From an answer back to its source</span>
              </div>
            </div>
          </div>
        </section>

        <section className="landing-process" id="how-it-works">
          <div className="landing-section-intro">
            <p className="eyebrow">A clearer way to research</p>
            <h2>From a question to understanding.</h2>
            <p>A focused workspace for the work between asking and knowing.</p>
          </div>
          <div className="landing-steps">
            <article>
              <span className="landing-step-number">01</span>
              <BookOpen size={23} />
              <h3>Start a research</h3>
              <p>
                Give your question a dedicated space. Keep each investigation
                focused, with its own context.
              </p>
            </article>
            <article>
              <span className="landing-step-number">02</span>
              <Layers size={23} />
              <h3>Bring the evidence together</h3>
              <p>
                Gather the documents that matter. Explore the passages and ideas
                behind your research.
              </p>
            </article>
            <article>
              <span className="landing-step-number">03</span>
              <GitBranch size={23} />
              <h3>Connect the dots</h3>
              <p>
                Build toward grounded answers, traceable citations, and findings
                you can return to.
              </p>
            </article>
          </div>
        </section>

        <section className="landing-features" id="features">
          <div>
            <p className="eyebrow">Built around your thinking</p>
            <h2>
              The whole investigation.
              <br />
              <em>Not just the last answer.</em>
            </h2>
            <p>
              Nexus is designed to keep the context of research intact—from your
              first source to your next question.
            </p>
            <Link href="/research">
              Find your research space <ArrowRight size={15} />
            </Link>
          </div>
          <ul>
            <li>
              <Check size={17} />
              <div>
                <h3>A home for every research</h3>
                <p>
                  Separate workspaces. Focused questions. Everything in its
                  place.
                </p>
              </div>
            </li>
            <li>
              <Check size={17} />
              <div>
                <h3>Evidence you can inspect</h3>
                <p>
                  A clear path from a finding to the passage that supports it.
                </p>
              </div>
            </li>
            <li>
              <Check size={17} />
              <div>
                <h3>Context worth keeping</h3>
                <p>
                  Return to your questions and build on what you have explored.
                </p>
              </div>
            </li>
          </ul>
        </section>

        <section className="landing-philosophy" id="philosophy">
          <p className="eyebrow">Our philosophy</p>
          <h2>
            A good answer is a beginning.
            <br />
            <em>Understanding is the goal.</em>
          </h2>
          <p>
            Research should help you see why—not just tell you what. We believe
            in connected context, visible evidence, and room to ask the next
            question.
          </p>
          <Link className="ui-button ui-button-primary" href="/research">
            Start your next research <ArrowRight size={16} />
          </Link>
        </section>
      </main>

      <footer className="landing-footer">
        <Link href="/" className="nexus-brand">
          <span className="nexus-mark">N</span>NEXUS
        </Link>
        <span>Connected research. Grounded understanding.</span>
        <Link href="/research">
          Explore the workspace <ArrowUpRight size={14} />
        </Link>
      </footer>
    </div>
  );
}
