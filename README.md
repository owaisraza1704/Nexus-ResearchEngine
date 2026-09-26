# Nexus Research Engine

Research often starts with a question and ends up scattered across documents, browser tabs, and disconnected conversations. The difficult part is keeping the context together: what was learned, which sources support it, and what still needs an answer.

Nexus Research Engine is an evidence-first research platform that turns selected documents and approved web pages into cited answers, comparisons, and reports. Each investigation has its own workspace, keeping its question, sources, research runs, and findings together so you can inspect the evidence and return to the work later.

Research as a connected story, not a collection of answers.

![Nexus landing page with its dark theme, research introduction, and a preview connecting documents to evidence and a grounded answer](docs/images/nexus-landing-hero.png)

## From a question to a report

Suppose you want to answer:

> Should we adopt Technology X for our existing system?

You can bring in architecture documents, evaluation reports, and specific public web pages, then investigate the question within that selected material:

1. **Create a research workspace.** Give the investigation a name, save a draft question, and keep its sources and results separate from other topics.
2. **Choose your sources.** Upload text-extractable PDF, DOCX, or legacy DOC files, attach existing documents, or explicitly approve public HTTPS pages for the run.
3. **Run the research.** Choose a focused answer, comparison, synthesis, evidence search, or an agentic investigation. Follow the actual tasks and progress, or cancel the run.
4. **Inspect the findings.** Open citations to their exact saved passages, review which sources contributed, and examine reported gaps and possible contradictions.
5. **Keep and reuse the result.** Reopen saved reports, export Markdown or JSON, and record your own quality ratings and notes.

Document processing and research run in the background through Celery workers. Closing the browser does not stop accepted work while the local backend and worker remain running. Independent research questions can run in parallel; hybrid retrieval combines keyword matches with semantic vector search before the evidence is brought together into a report.

## Ways to research

| Mode                     | What it does                                                                                                          |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| Grounded Answer          | Answers a question from one selected source, with citations.                                                          |
| Compare Sources          | Compares two or more sources, preserving attribution and highlighting possible disagreements.                         |
| Multi-Document Synthesis | Brings complementary findings from multiple sources into one structured result.                                       |
| Evidence Only            | Returns relevant passages and source locations without generating an answer.                                          |
| Agentic Research         | Plans one to three focused retrieval questions, gathers evidence, and synthesizes a cited result within fixed limits. |

Agentic research is bounded: the system validates the plan before running it, and the model cannot add arbitrary tools or expand the approved source scope.

## Evidence you can inspect

Nexus keeps the material behind a result accessible through its source inspector, evidence explorer, and source–evidence–claim graph. Saved citations refer to the document snapshot used for that run, so an older finding remains traceable.

Results include source coverage, reported gaps, and candidate contradictions. Citation checks verify references and saved passages; they do not guarantee that a model's interpretation is correct. The evaluation screen separates execution statistics from your own assessments of relevance, grounding, and citation quality.

Nexus is intended for your local machine, using your configured Azure deployments for embeddings and generation. Web content comes from pages you explicitly approve, not autonomous web search. Redis is used for Celery messages only; prompt caching is not implemented.

See [local setup and workflow](docs/mvp3.md) for running the product and [performance verification](docs/performance.md) for what has actually been measured.
