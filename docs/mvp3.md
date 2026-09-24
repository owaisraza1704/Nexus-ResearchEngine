# MVP3: the complete local research workflow

MVP3 connects the existing Next.js interface to real, persistent research workspaces and worker-backed research. It is designed for one person on their own machine, not as a hosted or multi-tenant service.

## Start the product

Keep the existing root `.env` with your Azure endpoint, key, API version, chat deployment, and embedding deployment. `.env.example` contains placeholders and the supported local limits; do not replace working deployment names with an assumed model name.

```sh
docker compose up --build -d
docker compose ps
```

Open **http://127.0.0.1:3000**. API documentation is at **http://127.0.0.1:8000/docs**.

The four local services are PostgreSQL/pgvector, FastAPI, a Procrastinate worker, and Next.js. The API applies migrations before becoming ready; the worker and UI wait for that readiness. No Redis, cloud deployment, authentication service, reverse proxy, or separate vector database is required. Published ports bind to loopback only.

The first PDF conversion may download Docling models. The first token estimate may download tokenizer data. Azure calls and approved web fetches also need internet access. This is a local application, not an offline model installation.

### Use it

1. Create a research workspace from the library.
2. Upload text-extractable PDF/DOCX files in **Sources**, or explicitly attach a previously uploaded source. Uploading authorizes Azure processing. Ingestion continues in the worker; wait for **ready**.
3. Select the sources and return to **Research**. Set the question, mode, and passages per source. **Save draft** persists an unfinished question/settings; running also saves them.
4. Optionally enter public HTTPS URLs and explicitly approve fetching them. That approval is required for each submission; saving a URL is not permission to fetch it.
5. Run research. The returned job is durable; you can close the tab, use another workspace, and return through **Research Runs**.
6. Inspect the validated findings, claims, coverage, gaps, and citations. A citation opens its exact saved document/chunk, not whichever version happens to be current.
7. Use **Reports** to reopen/export results, **Evidence** to inspect passages, **Research Graph** to inspect source/evidence/claim relationships, and **Evaluation** to save your own quality review.

The landing page retains its clearly labeled illustration. Operational screens contain database records, not example jobs, simulated progress, fabricated scores, or browser-local research data.

## Research modes

| UI mode | Sources | Work performed |
| --- | --- | --- |
| Grounded Answer | Exactly one | Retrieve, retain evidence, generate structured claims, validate citations. |
| Comparison | At least two | Compare the selected sources, preserving attribution and candidate conflicts. |
| Synthesis | At least two | Combine complementary findings while reporting missing evidence. |
| Evidence Only | One or more | Retrieve candidate passages with locators; no generated answer or claim-quality judgment. |
| Agentic Research | One or more | Azure proposes one to three focused retrieval questions; the server validates the plan before execution. |

All modes use the durable job path in the UI. Only Agentic Research pays for a planning call. Existing synchronous MVP1/MVP2 endpoints remain available unchanged.

## Runtime path and code map

```text
Next.js research workspace
  -> POST job: pin sources + save policy/budget + enqueue in one transaction
  -> worker: fixed workflow or structured Azure plan
  -> Pydantic + NetworkX plan validation
  -> optional approved web snapshots
  -> bounded retrieval branches -> evidence join -> synthesis -> result validation
  -> immutable result, citations, coverage and gaps
  -> UI polling, exact-passage inspection, export and review
```

| Responsibility | Implementation |
| --- | --- |
| Workspaces, drafts, source association and async uploads | `app/api/projects.py` |
| Job/status/plan/task/event/cancel/result/export/review API | `app/api/jobs.py` |
| Request, policy, budget and graph contracts | `app/jobs/contracts.py` |
| Atomic enqueue and dependency scheduling | `app/jobs/queue.py`, `app/jobs/service.py` |
| Attempts, retry classification, checkpoints and terminal states | `app/jobs/execution.py`, `app/jobs/state.py` |
| Provider-backed planner | `app/jobs/planner.py` |
| Reused retrieval, evidence, synthesis and validation operations | `app/jobs/handlers.py`, existing `app/research/` |
| Public URL policy, pinned DNS and bounded fetch | `app/jobs/web.py` |
| Provider admission, reservations and measured usage | `app/jobs/providers.py` |
| Worker entry point, native retries and stalled-job recovery | `app/worker.py` |
| Durable records and migration | `app/db/job_models.py`, `alembic/versions/0009_local_research_jobs.py` |
| UI state/revalidation and same-origin backend calls | `NexusUI/src/components/ResearchStore.tsx`, `NexusUI/src/lib/api.ts` |
| Operational screens and reusable result/graph views | `NexusUI/src/views/`, `NexusUI/src/components/ResultContent.tsx`, `ResearchDiagram.tsx` |

## Reuse decisions

| Concern | Selected package | Reason |
| --- | --- | --- |
| Durable queue, worker, locks, heartbeat, retry/backoff | Procrastinate 3.10.0, MIT | Uses the existing PostgreSQL database and supports enqueueing on the same transaction as application state. Celery/Redis would add another service without a current requirement. |
| Graph validation | NetworkX 3.6.1, BSD-3-Clause | Reuse cycle/depth/ancestor algorithms; keep only research-specific permissions and graph shape in application code. |
| HTTP and DNS-pinned transport | HTTPX 0.28.1, BSD-3-Clause; SafeHTTPX 0.1.7, MIT | Reuse HTTP/TLS/streaming and pinned-IP transport. Apply explicit URL/domain policy at every redirect. |
| Readable web extraction | Trafilatura 2.2.0, Apache-2.0 | Extract readable content rather than hand-building HTML parsing. |
| Input-token estimates | tiktoken, MIT | Use a tokenizer, not a character-count heuristic; still distinguish estimates from provider-reported usage. |
| Parsing/chunking, vectors, structured output | Existing Docling, pgvector/SQLAlchemy, official Azure OpenAI SDK | Reuse the already-tested MVP1/MVP2 data and provider boundaries. |
| UI server state, graphs, Markdown | SWR, React Flow, Dagre, react-markdown, MIT | Use maintained data fetching, graph layout/rendering and Markdown parsing rather than implementing those facilities manually. |

Application code owns research scope, lifecycle decisions, budgets and provenance. The packages own their mature infrastructure concerns.

## Persistence and recovery

- A workspace is a local research container, **not an authorization boundary**. There is no login or tenant isolation. Keep the services on loopback; do not expose this setup publicly.
- `workspace_sources` records explicit associations. `research_jobs.run_id` reuses the existing research run and its pinned document versions; there is no competing evidence/report model.
- Plans, task dependencies, attempts, ordered events and budgets are persisted in PostgreSQL. Queue messages contain IDs, not document text.
- Job creation and enqueue share one transaction. Task effects, task completion and enqueueing dependent tasks also share one transaction.
- Delivery is at least once. Native task locks serialize duplicate deliveries; already committed effects are reused. A crash may repeat an external provider call, but must not duplicate a logical result.
- Procrastinate worker heartbeats distinguish a dead worker from a slow live one. A maintenance task checks once per minute and requeues jobs whose worker heartbeat has been absent for 30 seconds. With a healthy restarted worker, detection is normally about 30–90 seconds, plus queue/execution time.
- Attempts are capped at three. Interrupted attempts remain visible. Transient provider/network/database failures retry with the library's bounded backoff; malformed plans, invalid output and policy violations do not automatically retry.
- Cancellation is cooperative. Pending tasks stop immediately; an in-flight SDK call is bounded by its timeout. Returned output is discarded after cancellation. Azure may still finish/bill a request already sent.
- A failed optional web fetch becomes a visible `source_unavailable` gap. Required task failure, invalid citations or exhausted budgets cannot become a successful answer.
- Closing a tab does not stop the worker. Sleeping/shutting down the machine does stop computation; restart Docker/the stack to resume or record a terminal budget/attempt failure. Deadlines are wall-clock limits, not paused timers.

### Default limits

| Limit | Default |
| --- | --- |
| Upload | 20 MiB; PDF/DOCX; 100 PDF pages; no silent OCR fallback |
| Parsed document | 500,000 characters; 1,000 chunks; 16,000 characters/chunk |
| Question | 4,000 characters |
| Selected sources | 5 total, including up to 3 approved web URLs |
| Retrieval | Up to 20 candidates/source; final context 48,000 characters and 20 evidence items |
| Plan | 12 tasks; depth 6; maximum fan-out 6; at most 3 retrieval branches |
| Concurrency | 2 worker slots and 2 active tasks/job |
| Job | 600 seconds from planning start; 20 provider calls; 100,000 input and 20,000 output tokens |
| Generation | 2,000 maximum planner output tokens; 6,000 maximum synthesis output tokens |
| Provider timeout | 45 seconds, clamped to remaining job time |
| Web request | Public HTTPS/443, exact approved hosts, up to 4 HTTP hops, 20 seconds total, 2 MiB uncompressed text/HTML |

Budgets apply to research job provider work, including its planning, retrieval and optional web embedding. Initial document ingestion is separate and bounded by its upload/document limits; it is not billed to a later research job. A job may request lower budgets through the API, never higher than the configured caps.

Calls reserve capacity before sending. Successful usage uses SDK-reported tokens; missing responses retain reservations because billing may be unknown. The API counts unfinished calls as unknown/in-flight usage, including process crashes. Input admission is an estimate, not an exact Azure monetary cap. No pricing or parallel speedup is invented.

## Approved web access

This release fetches **specific URLs you approve**, not autonomous broad web search. The planner sees URL indices/counts, not a tool that can browse arbitrary targets. Private, loopback, link-local and non-public DNS results are denied; the connection uses the validated IP. Redirect targets require the same checks. Environment proxy settings and third-party DNS fallback are not used.

Snapshots record the input/final URL, title, content hash, retrieval time and extraction metadata. Changed content creates a new source snapshot; existing citations retain their original document/locator. Identical URL/content can reuse the immutable document while recording the new acquisition event. No login walls, interactive pages, PDF URLs, custom ports, unrestricted browser automation or search-provider account is implemented. You remain responsible for having permission to fetch and process the chosen content.

Uploaded text, questions, source names and web content are untrusted data. They cannot add executable task types or change scope/budgets. Markdown does not execute raw HTML or load model-supplied images. Prompt-injection resistance and citation identity checks do **not** establish that every model conclusion is true.

## Verification

Install test dependencies with `uv sync --extra dev`. Ordinary regression tests mock only provider HTTP; PostgreSQL, migrations, SDK serialization and result validators are real.

```sh
NEXUS_TEST_DATABASE_URL=postgresql+psycopg://nexus:nexus@127.0.0.1:5432/nexus \
  uv run pytest -q
uv run ruff check app tests scripts
```

Database tests use disposable schemas. The subprocess worker test uses a disposable database to isolate the queue's schema-local enum/functions; the local test database role needs `CREATEDB`. Neither test path resets the application's public tables. The subprocess test kills a real worker, expires only its test heartbeat, starts another worker, and verifies one logical output after a duplicate delivery.

For real Azure and the running Docker services:

```sh
uv run python scripts/smoke_local.py --web
```

This creates a labeled verification workspace, generates synthetic PDF/DOCX files, and exercises all five modes plus an unanswerable question and an approved public web page. It checks exact chunk text/locators and JSON export. It makes billable Azure calls and leaves the workspace for inspection; it never deletes existing research.

From `NexusUI/`:

```sh
pnpm install --frozen-lockfile
pnpm typecheck
pnpm build
pnpm exec playwright install chromium
NEXUS_E2E_BASE_URL=http://127.0.0.1:3000 NEXUS_LIVE_E2E=1 pnpm test:e2e
```

Browser checks cover the actual backend: library/new-workspace flow, saved drafts, source selection and upload, asynchronous research, closing/reopening a tab, exact citation passage, task graph/attempt history, report download, saved human review, navigation, mobile layout and offline errors. Without `NEXUS_LIVE_E2E`, the billable upload/research case is skipped; the other tests still require a local API/database.

### Acceptance record: 2026-09-25

Final regression checks: **213 backend tests passed**, **five live browser journeys passed**, Ruff passed, and native/Docker Next.js builds plus type checking passed. Tests retain dependency deprecation warnings from Starlette/Docling; these did not fail verification.

The actual Docker worker was interrupted during an Azure embedding request and restarted. Job `cd9c1c0c-5cde-4b33-aa70-a89526066d78` recovered after 81.5 seconds with one interrupted attempt, one successful attempt, one result, and one correctly reported unknown-usage call. Browser cancellation while the worker was stopped produced `cancelled` with zero provider calls; a separate accepted job completed across an API container restart.

The configured Azure deployments were kept as supplied: generation `gpt-5.6-luna` and `text-embedding-3-large` embeddings at 3,072 dimensions. Real PDF and DOCX ingestion, all five modes, exact citation inspection, and `example.com` acquisition succeeded. The unsupported Mars-office question returned `insufficient_context` with no claims/citations.

One recorded live sample (not a throughput/quality benchmark):

| Case | Duration | Provider calls | Reported input/output tokens |
| --- | --- | --- | --- |
| Single-source answer | 29.788 s | 2 | 1,666 / 158 |
| Comparison | 6.645 s | 2 | 1,759 / 343 |
| Synthesis | 7.028 s | 2 | 1,764 / 610 |
| Evidence only | 1.522 s | 1 | 6 / 0 |
| Agentic research | 11.332 s | 4 | 2,748 / 879 |
| Insufficient-context answer | 4.830 s | 2 | 1,674 / 122 |
| Approved-web evidence | 4.420 s | 2 | 26 / 0 |

The first answer included cold initialization; these are not comparable sequential/parallel benchmark measurements. Token counts cover the job, not the earlier PDF/DOCX ingestion. Dollar cost is unknown without verified deployment rates. The broader labeled retrieval/research evaluations remain in `evals/`; the UI reports execution data and manual ratings, not invented Recall/MRR or universal correctness scores.

## Existing data and local operation

Migration `0009` is additive. Existing sources, document versions, answers and MVP2 results are preserved. Old global sources can be attached explicitly in **Sources**. Historical MVP1/MVP2 API runs have no workspace/job/plan association; they remain accessible through their original APIs and are not fabricated into agentic UI history.

The pre-upgrade database backup for this working copy is `.data/backups/pre-mvp3-erJBKN/database.backup` (private, ignored by Git). Original document files remain in the existing artifact volume. For a complete future backup, preserve **both** the database and artifact volume; a database dump alone does not contain uploaded files.

```sh
docker compose logs --tail=60 api worker
docker compose stop
docker compose up -d
```

`stop` preserves data. Do not use `down -v` or delete named volumes unless you intentionally want to erase local data. Keep `.env` untracked. After changing environment configuration, recreate the API/worker with `docker compose up -d --force-recreate api worker` so new processes load it.

For Python/UI development, run only PostgreSQL in Docker, use Python 3.11 with `uv sync --extra dev`, apply `uv run alembic upgrade head`, then run the following in separate terminals:

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
uv run procrastinate --app app.worker.worker worker
```

In `NexusUI`, `pnpm dev` uses the local API at port 8000. Do not run both Docker and native services on the same ports. Native and Docker artifact paths are different stores; choose one setup consistently or deliberately copy/mount your existing artifacts.

## Deliberately outside this local release

Authentication/multi-user hosting, automatic broad web search, arbitrary tools/code execution, image-only/OCR documents, automatic quality certification, verified monetary budgets, evaluation-driven hybrid/reranking/caching, and distributed deployment hardening are not silently added. None is required to use the local source-to-research-to-report workflow.
