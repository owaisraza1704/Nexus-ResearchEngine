You are redesigning the existing frontend for an AI research product called:

NEXUS
Agentic Research Engine

IMPORTANT:
You are working from an existing project/codebase and a detailed product specification.

First inspect the existing code and existing UI carefully.

Do NOT throw away the current implementation and create an unrelated generic AI dashboard.

Preserve existing functionality, structure, routes, components, naming, and working interactions wherever they are useful.

The frontend must be designed around the actual product architecture and the staged MVP roadmap described in the provided specifications.

==================================================
PRODUCT IDENTITY
==================================================

Nexus is not a chatbot.

It is an evidence-grounded research engine that progressively evolves from:

MVP-1:
single-document grounded question answering

to:

MVP-2:
controlled multi-document research and evidence/claim relationships

to:

MVP-3:
asynchronous research jobs, validated research plans, executable task graphs, durable workers, parallel task execution, progress tracking, cancellation, provenance, budgets and grounded final synthesis.

The ultimate product concept is:

RESEARCH REQUEST
        ↓
RESEARCH PLAN
        ↓
EXECUTABLE TASK GRAPH
        ↓
PARALLEL RESEARCH
        ↓
RETRIEVAL
        ↓
EVIDENCE
        ↓
CLAIMS
        ↓
VALIDATION
        ↓
GROUNDED SYNTHESIS
        ↓
CITED RESEARCH REPORT

The interface should make this transformation visually understandable.

==================================================
CURRENT IMPLEMENTATION — DO NOT MISREPRESENT THIS
==================================================

The current backend implementation already provides the foundation for:

- PDF upload
- DOCX upload
- source records
- document parsing
- page/section metadata
- deterministic document chunks
- embeddings
- PostgreSQL
- pgvector
- vector retrieval
- selected-source retrieval
- grounded answer generation
- structured answer output
- citation validation
- insufficient-context handling

The current API includes concepts around:

/v1/sources
/v1/retrieval

and the application currently uses:

FastAPI
PostgreSQL
pgvector
Azure OpenAI embeddings
Azure OpenAI structured generation
document parsing/chunking

The current implementation is NOT yet the complete asynchronous research system.

Therefore:

DO NOT pretend that Celery workers, asynchronous jobs, DAG execution, web search, cancellation, retries, budgets, planner-generated graphs, or full evidence/claim orchestration are already implemented.

Instead, design the interface so that these future capabilities have a natural place to exist.

Use appropriate visual states such as:

Available
In development
Coming in next phase

only where useful.

Do not clutter the UI with roadmap labels everywhere.

==================================================
PRODUCT DESIGN PHILOSOPHY
==================================================

Create a visually exceptional, next-generation research interface.

The product should feel like:

"an operating system for serious AI-powered research."

It should combine:

- advanced research software
- scientific tooling
- premium editorial design
- developer infrastructure interfaces
- knowledge graph interfaces
- modern AI workbenches

It should feel cutting-edge, premium and futuristic without looking like cyberpunk software.

Avoid:

- generic SaaS dashboards
- generic AI chatbot layouts
- excessive rounded cards
- excessive gradients
- purple neon AI clichés
- glowing borders everywhere
- meaningless 3D objects
- decorative blobs
- excessive glassmorphism
- excessive shadows
- card-grid-everything design
- unnecessary animations
- huge empty hero sections

The interface should feel designed by a world-class product/design team.

==================================================
VISUAL DIRECTION
==================================================

Use a dark-first visual system.

Base:

deep graphite / near-black
soft charcoal
warm off-white typography
muted slate surfaces
thin low-contrast borders

Use ONE primary accent color and a restrained secondary accent.

The accent should represent active intelligence / computation.

Semantic colors:

neutral = information
accent = active computation
green = verified / completed
amber = warning / unresolved
red = failure / contradiction
muted blue = sources / retrieval
secondary accent = synthesis / AI activity

Do not turn the interface into a rainbow.

Use subtle material depth rather than obvious gradients.

Use:

- hairline borders
- layered surfaces
- subtle translucency
- controlled blur
- extremely restrained shadows
- subtle inner highlights
- fine dividers
- sophisticated spacing

Glass effects should be used sparingly and only where they improve hierarchy.

==================================================
TYPOGRAPHY
==================================================

Typography is a major part of the visual identity.

Use a sophisticated modern grotesk / neo-grotesk typeface.

Create strong hierarchy between:

page titles
research questions
task names
technical metadata
body content
citations
source metadata
system states

Use large editorial typography for major research titles.

Use compact technical typography for:

task IDs
source IDs
model names
latency
token usage
statuses
timestamps
retrieval scores

Use excellent line height and whitespace.

Do not make every element bold.

==================================================
GLOBAL APPLICATION STRUCTURE
==================================================

Create a professional research workstation.

Desktop-first.

Primary layout:

LEFT:
collapsible navigation

CENTER:
main research workspace

RIGHT:
contextual inspector when required

The left navigation should include:

Research
Sources
Research Runs
Evidence
Reports
Research Graph
Evaluation
Settings

The navigation should be compact and elegant.

Include:

Nexus logo / wordmark
workspace switcher
user profile
collapse control

Do not make the sidebar oversized.

==================================================
SCREEN 1 — RESEARCH HOME
==================================================

This should be the primary landing screen.

It should immediately communicate:

"Ask a complex research question. Nexus finds, retrieves, validates and explains the evidence."

Create a large but sophisticated research composer.

Header:

RESEARCH

Subtitle:

"Turn complex questions into evidence-grounded research."

Main composer:

Ask Nexus anything...

The composer should feel like an advanced research instrument, NOT a chat input.

Include:

Research question
Source selection
Upload source
Research mode
Retrieval configuration
Execution configuration

For MVP-1, support:

Upload PDF
Upload DOCX
Select source
Ask question

The current implemented workflow should feel extremely polished.

Show selected sources as compact source chips.

Example:

3 Sources
research-paper.pdf
architecture.docx
design-notes.pdf

Primary CTA:

Run Research

Secondary actions:

Add Source
Clear

Below the composer, show recent research activity.

==================================================
RESEARCH ACTIVITY
==================================================

Create a sophisticated activity list rather than a generic card grid.

Each research item should show:

research question
source count
status
created time
duration
citation count
result state

Example:

"How does architecture A compare with architecture B?"

COMPLETED

3 sources
12 evidence items
7 citations
3.2s

Another:

"Evaluate the proposed retrieval architecture..."

INSUFFICIENT CONTEXT

2 sources
1 evidence item
2 gaps

This directly reflects the actual research-result concepts from the specifications.

==================================================
SCREEN 2 — SOURCE LIBRARY
==================================================

Create a premium research source library.

The current implementation supports PDF and DOCX.

Show:

Sources
Documents
Status
Pages
Chunks
Parser
Version
Created
Embedding status

Source states:

Processing
Ready
Failed

A source item should show:

document name
file type
page count
chunk count
status
version
date

Example:

architecture.pdf
PDF
42 pages
128 chunks
READY
v1

Do not make this look like Google Drive.

It should feel like a research corpus.

==================================================
SCREEN 3 — DOCUMENT INSPECTOR
==================================================

When opening a source, create a sophisticated document inspection workspace.

LEFT:

document metadata

CENTER:

document content / page preview

RIGHT:

document structure / chunks

Show:

source ID
content hash
document version
parser
parser version
page count
normalized text status
chunk count

Allow the user to inspect chunk boundaries.

Each chunk should show:

Chunk 014
Page 6
Sequence 14

and a text preview.

Highlight relevant chunks when they are associated with retrieval.

This is important because the current implementation preserves document/page/section/chunk metadata.

==================================================
SCREEN 4 — RESEARCH RESULT
==================================================

This is the most important MVP-1 screen.

Create an exceptional research answer experience.

Do NOT make it look like ChatGPT.

Use an editorial research layout.

Top:

Research question

Then:

Answer

Below the answer, show citation markers such as:

[C1] [C3] [C5]

Citations should be interactive.

Hovering/clicking a citation should reveal:

Citation C3

Source:
architecture.pdf

Page:
14

Chunk:
42

Relevant excerpt:
"..."

Allow:

Answer
Evidence
Sources

as contextual tabs or panels.

The answer should feel like a researched document, not a chatbot response.

==================================================
EVIDENCE PANEL
==================================================

Create a right-side evidence inspector.

When a citation is selected:

CLAIM / ANSWER

↓

SUPPORTED BY

Evidence C3

↓

SOURCE

architecture.pdf

↓

DOCUMENT

Page 14

↓

CHUNK

Chunk 42

This provenance chain should be visually clear.

The user should be able to trace:

Answer
→ Citation
→ Evidence
→ Chunk
→ Document
→ Source

This is a core product principle.

==================================================
INSUFFICIENT CONTEXT STATE
==================================================

Do not hide uncertainty.

Create a beautiful but restrained state for:

INSUFFICIENT CONTEXT

Explain:

"The selected sources do not contain enough relevant evidence to answer this question reliably."

Then show:

Sources searched
Relevant evidence
Missing information

Do NOT show a confident AI answer when evidence is insufficient.

This state is an important part of the product's identity.

==================================================
SCREEN 5 — MULTI-DOCUMENT RESEARCH
FUTURE MVP-2
==================================================

Design the future multi-document workflow without pretending it is currently implemented.

The interface should allow:

multiple sources
comparison mode
synthesis mode
source coverage
evidence relationships
claims
gaps
contradictions
citations

Show a research workspace such as:

RESEARCH QUESTION

How do these architectures differ?

SOURCES

Architecture A
Architecture B
Architecture C

Then:

SOURCE COVERAGE

Architecture A     USED
Architecture B     USED
Architecture C     NO RELEVANT EVIDENCE

This should directly reflect the specified research model.

==================================================
SCREEN 6 — EVIDENCE EXPLORER
FUTURE MVP-2
==================================================

Create a dedicated evidence interface.

The central concept is:

SOURCE
↓
DOCUMENT
↓
CHUNK
↓
EVIDENCE
↓
CLAIM
↓
CITATION

Evidence should be a first-class object.

Each evidence item should contain:

Evidence ID
Source
Document
Locator
Excerpt
Related claim
Support status

Support states:

SUPPORTED
PARTIALLY SUPPORTED
CONTRADICTED
UNRESOLVED

Do not use fake confidence scores as evidence sufficiency.

Make the provenance system visually powerful.

==================================================
SCREEN 7 — ASYNCHRONOUS RESEARCH JOB
FUTURE MVP-3
==================================================

This is the flagship future experience.

Create a sophisticated live research execution workspace.

At the top:

Research title

Status:
RUNNING

Then:

Tasks
6 / 10 completed

Workers
3 active

Elapsed
00:18

Provider calls
8 / 20

Budget
42%

The center should contain an actual task DAG visualization.

Example:

RESEARCH REQUEST
        ↓
RESEARCH PLANNER
        ↓
┌────────────┬────────────┬────────────┐
│ Retrieval  │ Retrieval  │ Evidence   │
│ Task A     │ Task B     │ Task C     │
└────────────┴────────────┴────────────┘
        ↓
      SYNTHESIS
        ↓
      VALIDATION
        ↓
   FINAL RESULT

Task nodes should show:

task key
task type
status
dependencies
duration
attempt
worker

Statuses:

READY
RUNNING
SUCCEEDED
RETRYING
FAILED
BLOCKED
CANCELLED

The graph should feel like an actual execution system, not a decorative flowchart.

==================================================
TASK INSPECTOR
==================================================

When a task is selected, open a right-side inspector.

Show:

Task key
Task type
Status
Dependencies
Attempt
Worker
Started
Completed
Duration

Then:

Input
Output reference
Error
Retry state

For retrieval tasks show:

Query
Source scope
Top K
Retrieved chunks
Retrieval duration

For synthesis tasks show:

Evidence count
Claims
Citation validation
Result state

Never expose secrets, provider credentials or hidden prompts.

==================================================
SCREEN 8 — JOB PROGRESS
==================================================

Create a clean progress experience based on persisted task state.

Show:

Total tasks
Succeeded
Running
Pending
Failed

Example:

12 total
7 succeeded
2 running
2 pending
1 failed

Also show:

Budget

Tasks:
7 / 12

Provider calls:
14 / 20

Duration:
00:48

This should feel operational and trustworthy.

==================================================
SCREEN 9 — FINAL RESEARCH REPORT
==================================================

Create a premium editorial research report.

It should look like a high-quality intelligence/research document.

Structure:

Research title

Executive Summary

Key Findings

Evidence

Analysis

Gaps

Contradictions

Conclusion

Sources

Citations

Use narrow readable text columns.

Use excellent typography.

Citation markers should be subtle and interactive.

Selecting a citation highlights its supporting evidence.

Selecting evidence highlights the claim.

Selecting a source highlights all claims/evidence derived from it.

The report should communicate:

"This conclusion can be audited."

==================================================
SCREEN 10 — RESEARCH GRAPH
==================================================

Create a knowledge/provenance graph.

Nodes:

Source
Document
Chunk
Evidence
Claim
Report Section
Citation
Task

Example:

SOURCE A
   ↓
DOCUMENT A
   ↓
CHUNK 17
   ↓
EVIDENCE E7
   ↓
CLAIM C3
   ↓
REPORT SECTION 2
   ↓
CITATION [C3]

Do not create a meaningless futuristic network graphic.

Every edge must represent an actual relationship.

Allow users to select nodes and inspect their relationships.

==================================================
SCREEN 11 — EVALUATION
FUTURE MVP-3
==================================================

Create an engineering-grade evaluation interface.

Metrics:

Report generation latency
Sequential vs parallel latency
Task parallelism
Retrieval relevance
Citation correctness
Groundedness
Cache hit rate
Token consumption
Failure recovery

Use elegant charts.

Do not overload the dashboard with giant metric cards.

Make it feel like:

AI research laboratory
+
observability platform
+
scientific evaluation environment

==================================================
COMMAND PALETTE
==================================================

Add a global command palette.

Commands:

Start research
Upload source
Search sources
Search evidence
Open recent research
Open report
Open research graph
Open evaluation
Settings

Keyboard-first interaction should feel natural.

==================================================
INTERACTION DESIGN
==================================================

Use subtle, high-quality micro-interactions.

Examples:

Submitting research transforms the composer into an active research state.

Source upload transitions:

Uploading
→ Parsing
→ Chunking
→ Embedding
→ Ready

Retrieval results should appear progressively.

Citations should reveal evidence on interaction.

Selecting a claim should highlight its evidence chain.

Future task graph nodes should resolve progressively.

Failed tasks should expose retry/error information.

Progress should feel alive but restrained.

No flashy animations.

No gratuitous particle effects.

No neon glowing animations.

==================================================
DESIGN SYSTEM
==================================================

Create a reusable design system.

Components:

Navigation
Buttons
Inputs
Research composer
Source chips
Source cards
Document cards
Status indicators
Progress bars
Task nodes
Task graph
Evidence cards
Claim cards
Citation markers
Document preview
Report sections
Inspector panels
Command palette
Search
Filters
Tabs
Drawers
Modals
Timeline
Charts
Empty states
Loading states
Error states
Insufficient-context states

Every component needs:

default
hover
active
selected
loading
success
warning
error
disabled

==================================================
RESPONSIVE BEHAVIOR
==================================================

Desktop-first.

Primary target:

1440px

Also support:

1280px
1024px

The product is a research workstation.

Do not simply stack everything vertically on smaller screens.

The graph and research workspace should adapt intelligently.

==================================================
IMPORTANT: DO NOT FAKE THE BACKEND
==================================================

The current backend has real concepts and endpoints.

Map the frontend architecture around the actual backend.

Current concepts include:

Source
Document
DocumentChunk
ChunkEmbedding
Retrieval
GroundedAnswer
Citation

Future concepts include:

ResearchRun
ResearchJob
ResearchPlan
ResearchTask
TaskAttempt
Evidence
Claim
Citation
SourceCoverage
Gap
Contradiction
Budget
JobEvent
Result

Do not invent unrelated entities.

Do not create arbitrary AI features.

Do not introduce generic "AI agents" everywhere.

Use the terminology from the specifications.

==================================================
PRODUCT EVOLUTION
==================================================

The UI should feel like ONE coherent product evolving through three stages.

MVP-1:

SOURCE
→ RETRIEVE
→ GROUNDED ANSWER
→ CITATIONS

MVP-2:

MULTIPLE SOURCES
→ RETRIEVAL
→ EVIDENCE
→ CLAIMS
→ GAPS / CONTRADICTIONS
→ CITED RESULT

MVP-3:

RESEARCH REQUEST
→ VALIDATED PLAN
→ TASK GRAPH
→ DURABLE ASYNC EXECUTION
→ PARALLEL TASKS
→ EVIDENCE
→ VALIDATION
→ GROUNDED RESULT

The visual language must remain consistent across all three.

==================================================
FINAL AESTHETIC TARGET
==================================================

The final interface should feel like:

"Linear meets a scientific research lab meets an advanced developer tool."

Premium.
Minimal.
Technical.
Editorial.
Evidence-driven.
Intelligent.
Calm.
Futuristic without being gimmicky.

It should NOT feel like:

another SaaS dashboard
another ChatGPT clone
another generic RAG interface
another neon AI concept

The strongest visual idea should be:

RESEARCH AS AN EXECUTABLE SYSTEM.

The user should be able to look at the interface and immediately understand:

"What is Nexus doing?"
"What evidence did it find?"
"Where did this claim come from?"
"What is still unresolved?"
"What is running?"
"What failed?"
"Can I trace this conclusion back to the source?"

Make those questions visually answerable.

Finally, use the existing codebase and specification terminology as the source of truth. Preserve working functionality, improve the existing UI rather than replacing useful behavior, and build the visual foundation for the complete Agentic RAG Research Platform.