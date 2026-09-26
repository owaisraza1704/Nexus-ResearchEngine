# MVP3: the complete local research workflow

MVP3 connects the existing Next.js interface to real, persistent research workspaces and worker-backed research. It is designed for one person on their own machine, not as a hosted or multi-tenant service.

## Start the product

Keep the existing root `.env` with your Azure endpoint, key, API version, chat deployment, and embedding deployment. `.env.example` contains placeholders and the supported local limits; do not replace working deployment names with an assumed model name.

```sh
docker compose up --build -d
docker compose ps
```

Open **http://127.0.0.1:3000**. API documentation is at **http://127.0.0.1:8000/docs**.

The six local services are PostgreSQL/pgvector, FastAPI, Redis, a Celery worker, Celery Beat (the scheduler), and Next.js. The API applies migrations before becoming ready; the worker, scheduler and UI wait for readiness. Redis carries queue messages only, not prompts or cached answers. No hosting, authentication service, reverse proxy, or separate vector database is required. Published ports bind to loopback only.

The first PDF conversion may download Docling models. The first token estimate may download tokenizer data. Azure calls and approved web fetches also need internet access. This is a local application, not an offline model installation.

### Use it

1. Create a research workspace from the library.
2. Upload text-extractable PDF/DOCX or binary Word 97–2003 DOC files in **Sources**, or explicitly attach a previously uploaded source. Uploading authorizes Azure processing. Ingestion continues in the worker; wait for **ready**.
3. Select the sources and return to **Research**. Set the question, mode, retrieval strategy, and passages per source. Hybrid (keywords + vectors) is the default; vector-only remains available for comparison. **Save draft** persists the question/settings; running also saves them.
4. Optionally enter public HTTPS URLs and explicitly approve fetching them. That approval is required for each submission; saving a URL is not permission to fetch it.
5. Run research. The returned job is durable; you can close the tab, use another workspace, and return through **Research Runs**.
6. Inspect the validated findings, claims, coverage, gaps, and citations. A citation opens its exact saved document/chunk, not whichever version happens to be current.
7. Use **Reports** to reopen/export results, **Evidence** to inspect passages, **Research Graph** to inspect source/evidence/claim relationships, and **Evaluation** to save your own quality review.

The landing page retains its clearly labeled illustration. Operational screens contain database records, not example jobs, simulated progress, fabricated scores, or browser-local research data.

Run badges distinguish **Completed**, **Completed — gaps noted**, and **Finished — insufficient evidence**. The last label means execution finished but the selected evidence did not adequately support the requested answer; inspect **Result → Gaps** for the limitations. This display uses the saved answer outcome, not just job completion. The API retains its existing job `status` and exposes a separate `outcome` on job, workspace-run and evaluation responses (`null` before a result exists).

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
  -> transactional outbox -> Redis delivery -> Celery worker
  -> fixed workflow or structured Azure plan
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
| Celery execution and retry configuration | `app/worker.py`, `app/jobs/celery_app.py` |
| Keyword/vector retrieval and score fusion | `app/retrieval/vector_search.py` |
| Legacy DOC conversion before Docling parsing | `app/ingestion/legacy_word.py` |
| Durable records and additive migrations | `app/db/job_models.py`, migrations `0009`–`0011` |
| UI state/revalidation and same-origin backend calls | `NexusUI/src/components/ResearchStore.tsx`, `NexusUI/src/lib/api.ts` |
| Operational screens and reusable result/graph views | `NexusUI/src/views/`, `NexusUI/src/components/ResultContent.tsx`, `ResearchDiagram.tsx` |

## Reuse decisions

| Concern | Selected package | Reason |
| --- | --- | --- |
| Queue transport, workers, retries, periodic dispatch | Celery 5.6.3 / Kombu, BSD-3-Clause; Redis 7.4 broker | Celery now fulfills the explicit worker requirement. A PostgreSQL outbox keeps accepted work atomic with application state. Redis is not an LLM cache. |
| Keyword matching and rank fusion | PostgreSQL full-text search; ranx 0.3.21, MIT | Reuse indexing/tokenization and reciprocal rank fusion instead of implementing a search/ranking algorithm manually. |
| Binary DOC conversion | LibreOffice Writer, MPL-2.0 | Converts DOC to temporary DOCX; existing Docling parsing/chunking stays authoritative. |
| Graph validation | NetworkX 3.6.1, BSD-3-Clause | Reuse cycle/depth/ancestor algorithms; keep only research-specific permissions and graph shape in application code. |
| HTTP and DNS-pinned transport | HTTPX 0.28.1, BSD-3-Clause; SafeHTTPX 0.1.7, MIT | Reuse HTTP/TLS/streaming and pinned-IP transport. Apply explicit URL/domain policy at every redirect. |
| Readable web extraction | Trafilatura 2.2.0, Apache-2.0 | Extract readable content rather than hand-building HTML parsing. |
| Input-token estimates | tiktoken, MIT | Use a tokenizer, not a character-count heuristic; still distinguish estimates from provider-reported usage. |
| Parsing/chunking, vectors, structured output | Existing Docling, pgvector/SQLAlchemy, official Azure OpenAI SDK | Reuse the already-tested MVP1/MVP2 data and provider boundaries. |
| UI server state, graphs, Markdown | SWR, React Flow, Dagre, react-markdown, MIT | Use maintained data fetching, graph layout/rendering and Markdown parsing rather than implementing those facilities manually. |

Application code owns research scope, lifecycle decisions, budgets and provenance. The packages own their mature infrastructure concerns.

Procrastinate 3.10.0 remains installed only because historical migration `0009` imports its pinned schema. No API or worker runtime imports or executes Procrastinate. Its old database tables are retained as history, not used as the active queue.

### Retrieval and DOC details

Hybrid search runs dense and keyword queries against the same ready, pinned documents and embedding identity. English stemming/stop words are handled by PostgreSQL; matching terms are ORed for passage recall. Each list contains at most `min(max(top_k * 4, 20), 100)` candidates. ranx applies reciprocal rank fusion (`k=60`); the evidence join keeps the best branch score for a repeated chunk. Per-source context limits still prevent one document from taking every evidence slot.

Cosine distance, lexical score and fusion score are stored separately. Fusion scores are ranks, not probabilities or groundedness scores. No-match keyword searches retain vector ordering. The generated keyword index automatically covers existing chunks; no re-embedding is needed. Historical synchronous MVP1/MVP2 endpoints keep their vector-only behavior.

For DOC, the original binary file/hash/download remain unchanged. LibreOffice uses a separate temporary profile for each conversion, then Docling processes the resulting DOCX. Stored conversion metadata records the tool/version. Citation locations refer to the converted document's blocks, not guaranteed page coordinates in the original DOC. Password-protected files and documents with no extractable text may fail explicitly; OCR and macro execution are not features.

## Persistence and recovery

- A workspace is a local research container, **not an authorization boundary**. There is no login or tenant isolation. Keep the services on loopback; do not expose this setup publicly.
- `workspace_sources` records explicit associations. `research_jobs.run_id` reuses the existing research run and its pinned document versions; there is no competing evidence/report model.
- Plans, task dependencies, attempts, ordered events and budgets are persisted in PostgreSQL. Queue messages contain IDs, not document text.
- Job creation and outbox insertion share one transaction. Task effects, task completion and dependent outbox entries share that transaction too. Accepting a job does not need a live Redis connection.
- Celery Beat requests outbox dispatch every second; finished tasks also publish newly unblocked work immediately. Broker publication failures leave durable intent in PostgreSQL for a later attempt.
- Delivery is at least once. A PostgreSQL session advisory lock, held on one physical connection across handler commits, prevents duplicate deliveries from overlapping. Completed effects are reused. A crash may repeat an external provider call, but must not duplicate a logical result.
- Outbox deliveries published over 60 seconds ago are eligible for recovery only when their task lock is free. A slow live task retains its lock and is not republished. A dead process releases the lock; dispatch can resume its task with the same Celery ID. Recovery also works after loss of broker messages. The 60-second threshold plus dispatch/queue time is not a guaranteed completion SLA.
- Attempts are capped at three. Interrupted attempts remain visible. Transient provider/network/database failures retry with the library's bounded backoff; malformed plans, invalid output and policy violations do not automatically retry.
- Cancellation is cooperative. Pending tasks stop immediately; an in-flight SDK call is bounded by its timeout. Returned output is discarded after cancellation. Azure may still finish/bill a request already sent.
- A failed optional web fetch becomes a visible `source_unavailable` gap. Required task failure, invalid citations or exhausted budgets cannot become a successful answer.
- Closing a tab does not stop the worker. Sleeping/shutting down the machine does stop computation; restart Docker/the stack to resume or record a terminal budget/attempt failure. Deadlines are wall-clock limits, not paused timers.

### Default limits

| Limit | Default |
| --- | --- |
| Upload | 20 MiB; PDF/DOCX/DOC; 100 PDF pages; no silent OCR fallback |
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
  NEXUS_TEST_CELERY_BROKER_URL=redis://127.0.0.1:6379/0 NUMBA_NUM_THREADS=1 \
  uv run pytest -q
uv run ruff check app tests scripts
```

Database tests use disposable schemas. The subprocess Celery test uses a disposable database and a unique Redis key prefix/queue; the local database role needs `CREATEDB`. Neither test resets the application's tables or flushes Redis. The subprocess test kills a real worker, makes only its test outbox delivery eligible for recovery, starts another worker, and verifies one logical output after duplicate delivery. Upgrade tests also cover existing chunks and pending pre-Celery queue identifiers.

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

Browser checks cover the actual backend: library/new-workspace flow, saved drafts and retrieval strategy, PDF/DOCX/DOC upload, original DOC download, asynchronous research, closing/reopening a tab, exact citation passage, task graph/attempt history, report download, saved human review, approved web acquisition, navigation, mobile layout and offline errors. The DOC fixture is generated with the running API image's LibreOffice installation. Without `NEXUS_LIVE_E2E`, billable upload/research cases are skipped; the other tests still require a local API/database.

### Current acceptance record: 2026-09-26 (Celery/hybrid/DOC)

**237 backend tests and six live browser journeys passed.** Ruff, UI type checking, formatting checks, and native/Docker Next.js builds passed. The backend suite uses real PostgreSQL and Redis, including a subprocess Celery worker interruption/recovery test; provider HTTP is mocked in that suite. The live API and browser checks use the configured Azure deployments. Existing dependency deprecation warnings remain.

Live verification covered all five research modes, an unsupported question returning `insufficient_context`, approved web ingestion, exact evidence text/locators, and report export. The browser also verified PDF/DOCX/DOC ingestion, byte-identical original DOC download, a grounded DOC answer, saved retrieval strategy, tab-close/reopen, task history, citations, graphs, and human review. Synthetic workspaces and reports remain available for inspection.

Redis was deliberately stopped while the API remained running. Job `ec5fcacf-44fe-4592-ac22-fa779bda23ad` was accepted with HTTP 202 and zero provider calls, then completed with one embedding call after Redis restarted, without restarting the API or worker. `/v1/system` returned HTTP 200 before and during the outage and on all 11 recovery polls. The status endpoint now handles raw Redis connection/timeout errors as well as Kombu transport errors; three regression cases cover that previously missed reconnection path.

The sequential/parallel experiment observed medians of **18.384 s and 15.659 s** across three measured runs per variant. Parallel branches actually overlapped, but plans and provider latency varied. This does **not** substantiate a 50% speedup claim. See [the measurement method, raw records and limitations](performance.md). Redis remains a broker only; prompt caching and token-reduction claims are excluded.

### Historical MVP3 acceptance record: 2026-09-25 (before Celery/hybrid/DOC)

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

Migrations `0009`–`0011` are additive. Existing sources, document versions, answers and results are preserved. Stop the old API/Procrastinate worker before the first Celery upgrade: `docker compose stop api worker`, then `docker compose up --build -d`. Migration `0011` copies pending deliveries with their existing IDs; do not restart an old Procrastinate worker against the upgraded database. Old global sources can be attached explicitly in **Sources**. Historical MVP1/MVP2 API runs have no workspace/job/plan association; their original APIs remain available.

The pre-Celery/hybrid database backup for this working copy is `.data/backups/pre-search-workers-scw1Mx/database.backup` (private, ignored by Git). Original files remain in the existing artifact volume. For a complete future backup, preserve **both** the database and artifact volume; a database dump does not contain uploaded files. Redis uses AOF persistence; PostgreSQL's outbox is still the durable source of accepted delivery intent.

```sh
docker compose logs --tail=60 api worker scheduler redis
docker compose stop
docker compose up -d
```

`stop` preserves data. Do not use `down -v` or delete named volumes unless you intentionally want to erase local data. Keep `.env` untracked. After changing environment configuration, recreate services with `docker compose up -d --force-recreate api worker scheduler` so they load it.

For Python/UI development, run PostgreSQL and Redis in Docker, use Python 3.11 with `uv sync --extra dev`, apply `uv run alembic upgrade head`, then run these in separate terminals. Native DOC ingestion also requires LibreOffice (`brew install --cask libreoffice` on macOS); the Docker image already includes it.

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
NUMBA_NUM_THREADS=1 uv run celery -A app.worker:celery_app worker --loglevel=INFO
uv run celery -A app.worker:celery_app beat --loglevel=INFO --schedule=.data/celerybeat
```

In `NexusUI`, `pnpm dev` uses the local API at port 8000. Do not run both Docker and native services on the same ports. Native and Docker artifact paths are different stores; choose one setup consistently or deliberately copy/mount your existing artifacts.

## Deliberately outside this local release

Authentication/multi-user hosting, autonomous broad web search, arbitrary tools/code execution, image-only/OCR documents, automatic quality certification, verified monetary budgets, cross-encoder reranking, LLM prompt/response caching, and distributed deployment hardening are not included. In particular, no 35% token-reduction claim is made. See [performance verification](performance.md) for the sequential/parallel measurement method and its limits.
