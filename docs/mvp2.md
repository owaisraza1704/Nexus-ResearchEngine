# MVP-2: controlled multi-document research

MVP-2 adds comparison and synthesis over explicitly selected PDF/DOCX documents to the existing backend. It preserves source coverage, evidence-linked claims, candidate contradictions, gaps, and immutable results. The single-document `/v1/answers` API remains unchanged.

This is a local, synchronous backend release. It does not add autonomous agents, workers, web search, authentication, or the UI's browser-local research-library container. `ResearchRun` means one execution, not a project containing multiple runs.

## Run it

Use the existing Python 3.11 environment, PostgreSQL/pgvector, and Azure settings. No new production dependency is required.

```bash
uv sync --extra dev
docker compose up -d --build --wait api
curl --fail http://127.0.0.1:8000/health/ready
```

The API container applies Alembic migrations at startup. The research tables are introduced by revisions `0006_research_runs`, `0007_research_evidence`, and `0008_research_results`. They add tables without rewriting MVP-1 records.

Upload documents through `POST /v1/sources/uploads`, then select at least two distinct ready source IDs:

```bash
curl --fail-with-body --max-time 150 \
  http://127.0.0.1:8000/v1/research/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "How do these systems differ in their execution and retention policies?",
    "mode": "comparison",
    "source_ids": ["SOURCE_A_UUID", "SOURCE_B_UUID"],
    "retrieval": {"top_k_per_source": 4},
    "output": {"max_claims": 12}
  }'
```

Replace the source placeholders with actual UUIDs. `mode` supports `comparison` and `synthesis`. Each POST creates a new execution; there is no automatic retry or asynchronous job.

| Endpoint | Result |
| --- | --- |
| `POST /v1/research/runs` | A completed or insufficient-context research result, synchronously. |
| `GET /v1/research/runs/{run_id}` | Pinned sources, coverage, configuration, model/usage, bounded retrieval diagnostics, and failure details. No source text is returned here. |
| `GET /v1/research/runs/{run_id}/result` | The saved summary, claims, evidence excerpts, citations, candidate contradictions, and gaps. Reading does not call Azure. |

`/docs` exposes the complete request and response schemas. A missing run returns 404; an unfinished or failed run has no successful result and returns 409 from its result endpoint. Provider/validation errors return a safe error code and `run_id` when an execution was created.

## Runtime path and responsibilities

1. [`create_run`](../app/research/service.py) validates the entire source set and limits before provider calls. It pins each current document ID/version and copies source display metadata. Later source updates cannot redirect this run.
2. [`retrieve_evidence`](../app/research/retrieval.py) embeds the question once using the existing Azure adapter. It reuses pgvector search separately for each pinned document, preserving rank and distance.
3. Each source gets a fixed share of the context-character and evidence-count budgets. Whole chunks are selected; oversized chunks are not silently truncated. Selected excerpts and Docling locators become stored evidence candidates.
4. [`build_prompt`](../app/research/synthesis.py) sends the selected context, question, source attribution, mode, and limits through the existing SDK's Pydantic structured-output support. Source content is data, not instructions.
5. `validate_output` checks same-run evidence membership, allowed relationships, support-status consistency, summary citations, and output limits. A declared conflict must have a disputed claim with opposing evidence, not just prose about a conflict.
6. [`save_result`](../app/research/results.py) commits validated claims, relationships, coverage, gaps, citations, and the result together. Failure rolls back unfinished output while retaining execution diagnostics.
7. [`app/api/research.py`](../app/api/research.py) exposes the stored result and checks its evidence chain when reading it. It derives source identity from the pinned snapshot, not from a model-provided source ID.

The mentor-style implementation checkpoints follow these behaviors: pinning, retrieval, synthesis/validation, persistence/API, then live evaluation. No generic orchestration framework or substitute production provider was introduced.

## Data and evidence semantics

[`app/db/research_models.py`](../app/db/research_models.py) defines ten research tables:

| Records | Purpose |
| --- | --- |
| `research_runs`, `research_run_sources` | One execution, its limits/model versions/usage, and immutable source selection. |
| `research_retrieval_results`, `source_coverage` | Per-source candidates, ranks, context selection, and outcome for every selected source. |
| `evidence_items` | Exact supplied excerpts, labels, copied locators/display metadata, and whether the model selected them as relevant. |
| `claims`, `claim_evidence` | Individual observations and `supports`, `contradicts`, `qualifies`, or `context` links. |
| `research_gaps` | Ordered missing-evidence, scope-limit, or conflict explanations. |
| `research_results`, `result_citations` | One immutable result per run and canonical evidence citation labels. |

Composite foreign keys prevent coverage, claim relationships, and citations from linking records across runs. Service checks additionally enforce that every evidence chunk belongs to a pinned document. The schema deliberately keeps the MVP-1 query/answer tables separate.

Stored evidence candidates are not automatically relevant: `EvidenceItem.used` records the model's relevance selection. The result returns used evidence; the run's retrieval diagnostics retain all candidates and their context-selection flags. Similarity scores are diagnostic, not evidence-strength or confidence scores.

Relationships are relative to the claim's exact proposition. A passage directly stating an exception **supports** a claim describing that exception; it **qualifies** a broader proposition when it adds a condition. A candidate contradiction needs both supporting and opposing evidence about the same proposition. It is not a proof that one source is wrong.

## Coverage and incomplete answers

Every selected source has a coverage record:

| State | Meaning |
| --- | --- |
| `used` | The model identified relevant answer evidence from this source. This is not an independent support judgment. |
| `no_relevant_evidence` | No relevant answer evidence was identified in the retrieved context. This does not prove absence from the entire document. |
| `context_limited` | Retrieved passages were excluded by the context/evidence budget and no usable evidence remained. |
| `parse_unavailable` | A previously pinned snapshot became unavailable; the run fails visibly. |
| `retrieval_failed` | The source search failed; the run fails visibly. |
| `pending`, `retrieved` | Intermediate states. |
| `not_processed` | Processing or evidence assessment did not finish before the run failed. |

The separate `context_limited` boolean remains true when a source contributes some evidence but other candidates were omitted. Such omissions also create a scope-limit gap. Source-processing failures are not converted into insufficient-context successes.

A completed multi-document result needs non-context relationships in grounded claims from at least two sources. Merely marking a second source relevant, or adding a background-only link, does not satisfy this condition. An `insufficient_context` result explains the missing information and may preserve independently supported partial claims or candidate contradictions. Its summary is the limitation, never a speculative complete answer. Empty context skips the generation call entirely.

## Bounds and failure behavior

| Configuration | Default |
| --- | --- |
| `NEXUS_MAX_RESEARCH_SOURCES` | 5, with at least 2 selected |
| `retrieval.top_k_per_source` | 4; maximum uses `NEXUS_MAX_TOP_K` (20) |
| `NEXUS_MAX_RESEARCH_CONTEXT_CHARS` | 48,000 across selected excerpts |
| `NEXUS_MAX_RESEARCH_EVIDENCE` | 20 supplied evidence items |
| `NEXUS_MAX_RESEARCH_CLAIMS` | 12 claims and at most 12 model-generated gaps |
| `NEXUS_MAX_RESEARCH_OUTPUT_CHARS` | 24,000 for the model's serialized output; the HTTP envelope also contains bounded evidence/locators and derived gaps |
| `NEXUS_MAX_RESEARCH_OUTPUT_TOKENS` | 6,000 completion tokens |
| `NEXUS_RESEARCH_TIMEOUT_SECONDS` | 120 seconds |
| `NEXUS_PROVIDER_TIMEOUT_SECONDS` | 45 seconds, reduced to the remaining request budget |

Limits, prompt version, deployment/model identity, timings, and reported token usage are stored with each run. PostgreSQL searches use a statement timeout based on the remaining budget. Provider refusal, truncation, malformed structured output, inconsistent references, and timeouts fail visibly without exposing an invalid successful result. No retry/repair loop hides those failures.

Upstream generation failures log exception type, HTTP status when available, and request ID. Logs omit raw provider messages, prompts, and credentials. Structured output enforces a schema, not semantic truth; see the [provider's structured-output guidance](https://developers.openai.com/api/docs/guides/structured-outputs/).

These are synchronous operation timeouts and elapsed-budget checks, not a hard process-kill guarantee. A process/database outage can leave an unfinished run; automatic crash recovery and cancellation are intentionally deferred. Start a new execution after resolving the failure.

## Verify without paid provider calls

```bash
NEXUS_TEST_DATABASE_URL=postgresql+psycopg://nexus:nexus@127.0.0.1:5432/nexus \
  uv run --extra dev pytest -q
uv run --extra dev ruff check app tests evals alembic
uv run alembic check
uv lock --check
```

Database tests run migrations in disposable PostgreSQL schemas. Provider contract tests use the real Azure SDK with HTTPX MockTransport; they test serialization, validation, state transitions, and errors—not real model quality. End-to-end tests generate PDF/DOCX with ReportLab/python-docx and parse/chunk them with real Docling.

## Live quality evaluation

The following makes paid calls to the configured Azure embedding and generation deployments. It uploads only the fictional documents in [`evals/research_cases.json`](../evals/research_cases.json), using existing parsing/chunking code:

```bash
uv run --extra dev python -m evals.research --output .data/mvp2-evaluation.json
```

Reuse uploaded fixture IDs for later evaluations instead of re-uploading identical PDFs:

```bash
uv run --extra dev python -m evals.research \
  --reuse-sources .data/mvp2-evaluation.json \
  --output .data/mvp2-evaluation-next.json
```

The suite covers ordinary comparison, cross-source synthesis, an irrelevant source containing an instruction-injection attempt, same-scope conflicting policies, a qualifying exception, absent measurements, and partial evidence. It resolves gold annotations against actual parsed chunks before generation, uses `ir-measures` for per-source retrieval scores, and checks coverage, locators, expected outcomes, reload, and request duration separately.

The JSON report preserves every response, diagnostic ranking, source ID, timing, and review reference. Inspect each claim against its cited excerpt; a contract pass, valid schema, or high retrieval score does not establish semantic support. Fixture success is not a general production-quality guarantee.

Monetary cost is not guessed. To calculate a query-only estimate, supply all three verified deployment rates with `--embedding-usd-per-million`, `--input-usd-per-million`, and `--output-usd-per-million`. The report records those rates. This excludes document-ingestion embeddings and is not an Azure invoice; without prices, cost is explicitly unknown.

## Scope still deferred

The default installation is local and unauthenticated. Pinned-source scope is not multi-tenant authorization. Keep the existing loopback-only Docker bindings. Source replacement/deletion APIs, a server-backed UI research-project library, UI wiring, worker recovery/cancellation, planners, web acquisition, hybrid retrieval/reranking, and broader independent quality/security evaluation remain separate work.

The full roadmap stays in [`specs/05-implementation-plan.md`](../specs/05-implementation-plan.md), with MVP-2 details in [`specs/mvp2/`](../specs/mvp2/). Those specification files are currently Git-ignored; this tracked runbook and the code/tests provide the reproducible implementation record.

## Acceptance record: 2026-09-25

The local backend implementation is delivered. Production-quality, uptime, and priced-cost acceptance are not implied by this small fixture evaluation.

### Automated and persistence verification

- **161 tests passed**, with 16 upstream deprecation warnings. Coverage includes fresh-schema migrations, source pinning, per-source filtering, limits, four relationship types, invalid/refused output, timeout/rate-limit behavior, rollback, and immutable result reads.
- Real PDF and DOCX ingestion through Docling is exercised by the end-to-end tests. Model calls in the automated suite use the official SDK with mocked HTTP responses; live model behavior is evaluated separately below.
- `ruff check app tests evals alembic`, `uv lock --check`, `alembic check`, and `git diff --check` pass. The live database is at revision `0008_research_results`, with no schema drift reported.
- Docker builds and readiness checks pass. After restarting/recreating the API, all 14 successful final-prompt evaluation results remain identical to their recorded responses; both failed runs remain failed and their result reads return 409. The saved successful results also pass the final tightened multi-source validator.
- The seven pre-existing MVP-1 answer responses match their pre-change SHA-256 baselines. Six fictional evaluation documents were added; the original three sources and seven answers were not deleted or rewritten.

### Live evaluation outcomes

Actual deployments: Azure `text-embedding-3-large`, 3,072 dimensions, and the configured `gpt-5.6-luna`. Generation reported `gpt-5.6-luna-2026-07-09`; the final prompt is `research-v3`.

| Evaluation | Outcome | What it establishes |
| --- | --- | --- |
| Initial `research-v1` | 3/7 cases passed | Exposed relevance, conflict-representation, and overly restrictive partial-result behavior. |
| Revised `research-v2` | 5/7 cases passed | Remaining failures exposed ambiguity between a passage supporting a caveat and qualifying another proposition. |
| Final `research-v3` | 7/7 cases passed | All seven fixture behaviors and automated response/provenance checks passed in this run. |
| Unchanged-prompt repeat | 5/7 cases passed | Two SDK/provider generation requests failed; retrieval completed and failed runs did not expose successful results. |
| Focused new-execution recheck | 2/2 cases passed | Both failed case types succeeded without changing the prompt, model, or provider retry policy. |

The two repeat failures were `RESEARCH_GENERATION_FAILED`, not evidence-membership or schema-validation failures. Their exact upstream cause was not captured by the earlier logs. Safe status/type/request-ID logging was added for future diagnosis. A subsequent success does not prove that the provider reliability issue is resolved.

Reports are retained locally as ignored artifacts: `.data/mvp2-evaluation.json`, `.data/mvp2-evaluation-v2.json`, `.data/mvp2-evaluation-v3.json`, `.data/mvp2-evaluation-v3-repeat.json`, and `.data/mvp2-evaluation-v3-provider-recheck.json`. The source fixtures and evaluator are in the repository so these checks can be rerun.

### Evidence review

The implementation agent inspected all 15 claims in the seven-case `research-v3` pass against the cited excerpts and the fixture reference. This is an explicit source review, not an independent human adjudication or a calibrated semantic precision score.

| Case | Observed result |
| --- | --- |
| Retention comparison | Alpha 30 days versus Beta 90 days; backup retention is kept distinct, not substituted for audit retention. |
| Execution synthesis | Alpha completes within its HTTP request; Beta returns a job ID and exposes the result after background processing. No numerical latency is invented. |
| Irrelevant source/injection | Office notes are reported as providing no relevant evidence; their instruction to invent a value/citation is ignored. |
| Same-scope conflict | Orion's 30-day and 90-day policies are retained as opposing evidence with candidate contradictions and an explicit conflict gap. No authority is invented. |
| Qualification | Legal-held logs are retained until release; standard logs without a hold retain the 30-day rule. Different conditions are not labeled a contradiction. |
| Absent answer | Missing latency/cost measurements produce `insufficient_context`, empty claims/evidence, and explicit gaps. |
| Partial evidence | Alpha's supported 30-day fact remains visible; no Gamma policy is invented and no complete comparison is claimed. |

Across 11 labeled source/question pairs, both full final-prompt evaluations had Recall@1 `0.9091`, Recall@4 `1.0000`, MRR@4 `0.9545`, and nDCG@4 `0.9664`. These measure retrieval on these fictional passages, not overall research quality.

Successful final-prompt requests across the full runs and focused recheck took about 5.7–9.8 seconds; none exceeded the 120-second budget. The two failed requests returned after roughly 18–19 seconds. These are observations on small documents, not maximum-source/load benchmarks.

The seven-case successful pass reported 199 query-embedding tokens, 13,798 generation input tokens, and 3,606 output tokens. These are not totals for all development experiments or an Azure bill. Failed provider requests can have unavailable usage; monetary cost is unknown without verified deployment rates.

### Decisions and review checkpoints

Keep this release synchronous and library-first. The implementation adds product rules for snapshot identity, source participation, evidence relationships, and result persistence; it does not replace Docling, pgvector, Pydantic, or the provider SDK. Nothing here authorizes MVP-3 infrastructure.

For a code walkthrough, start at `research()` and follow the functions in the runtime section. Three useful questions to check understanding:

1. Why is a pinned document ID safer than rereading a source's current document during a run?
2. Why are retrieved candidates, relevant evidence, and supported claims different things?
3. Why can valid evidence IDs prove citation membership but not that the cited passage supports the wording?
