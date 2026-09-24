# MVP-1: run, understand, and verify

MVP-1 is a local API for asking a question over one uploaded document. It accepts text PDFs and DOCX files, creates searchable chunks, and returns a saved answer with inspectable citations or an explicit insufficient-context response.

The root README describes the idea. This guide describes the implemented release. The detailed local specifications are in [specs/mvp1](../specs/mvp1/README.md); the broader release order remains in [the coherent implementation plan](../specs/05-implementation-plan.md).

## Start it

Use Python 3.11, Docker Compose, and the reviewed Azure deployments. Fill your local `.env` using the placeholder names in [.env.example](../.env.example). Do not commit credentials.

```bash
uv sync --locked --extra dev
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8000/health/ready
```

Wait for the API to be healthy before uploading. The container applies Alembic migrations on startup. PostgreSQL and artifacts use named volumes; container recreation preserves them. Docling model downloads use a separate cache volume. The first PDF conversion may download layout-model weights.

The Docker image uses Python 3.11 and the locked dependencies. PyTorch and torchvision are explicit dependencies so uv can select their official CPU wheels on Linux; this avoids installing CUDA runtimes for the local parser. macOS keeps its normal PyPI wheels.

Open [interactive API documentation](http://127.0.0.1:8000/docs).

For local Python development instead of the API container:

```bash
docker compose stop api
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The local `.env` database URL should use localhost; Compose supplies its own internal PostgreSQL hostname to the API container.

## Try the complete flow

Upload a document you are permitted to send to Azure:

```bash
curl --max-time 195 -X POST http://127.0.0.1:8000/v1/sources/uploads \
  -F 'file=@architecture/Agentic_RAG_Research_Platform_Synopsis.pdf'
```

A successful upload returns 201, a `source_id`, and a ready document with block/chunk counts. If this exact file is already ready, 409 is expected; find its ID through the list endpoint. An identical upload whose earlier ingestion failed retries the same source.

```bash
curl http://127.0.0.1:8000/v1/sources
```

Copy the source ID into the commands below, replacing `SOURCE_UUID`:

```bash
curl http://127.0.0.1:8000/v1/sources/SOURCE_UUID
curl http://127.0.0.1:8000/v1/sources/SOURCE_UUID/chunks

curl -X POST http://127.0.0.1:8000/v1/retrieval \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the project objective?","source_ids":["SOURCE_UUID"],"top_k":5}'

curl --max-time 100 -X POST http://127.0.0.1:8000/v1/answers \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is the project objective?","source_ids":["SOURCE_UUID"],"retrieval":{"top_k":5}}'
```

An answer returns `answer_id`, `query_id`, status, text, citations, retrieval metadata, actual model, prompt version, tokens, and duration. Each citation includes its source/document/chunk IDs, a display location, and the saved Docling locator.

Reload it without calling Azure again:

```bash
curl http://127.0.0.1:8000/v1/answers/ANSWER_UUID
```

Try an unsupported question such as “What is the exact approved development budget in Indian rupees?” The synopsis does not supply that amount; the expected response is 200 with `status=insufficient_context`, an explanation, and no citations.

Source listing supports `limit`/`offset` (50 by default, at most 100). Chunk listing defaults to 100, at most 200. Pass `document_id` to inspect a particular snapshot referenced by a citation.

## How the code fits together

| Stage | Code | Reason it exists |
| --- | --- | --- |
| Validate/store upload | [sources.py](../app/api/sources.py), [artifacts.py](../app/ingestion/artifacts.py) | Bound the input and use content-addressed storage instead of filename paths. |
| Parse | [docling_parser.py](../app/ingestion/docling_parser.py) | Convert through Docling and retain text/provenance. |
| Chunk | [docling_chunker.py](../app/ingestion/docling_chunker.py) | Adapt Docling's existing HierarchicalChunker output. |
| Embed | [embedding adapter](../app/embeddings/azure_openai.py) | Use the official SDK and check vector counts/dimensions. |
| Search | [vector_search.py](../app/retrieval/vector_search.py) | Let pgvector rank the selected document's vectors. |
| Save retrieval | [retrieval service](../app/retrieval/service.py) | Pin the document and retain query configuration, evidence, scores, and failures. |
| Generate/validate | [answer service](../app/answers/service.py), [LLM adapter](../app/llm/azure_openai.py) | Limit source context, parse structured output, and check citation membership. |
| Save/return answer | [answers API](../app/api/answers.py), [models](../app/db/models.py) | Persist the answer and copied citation locators, then support repeatable reads. |

The important distinction is between a source and a document snapshot. A query saves the snapshot it searched. A citation points to a saved retrieval result and copies its locator/display label. Reading an old answer therefore does not reinterpret it using the source's latest metadata.

Chunks use Docling's native structure-aware strategy. There is no manual fixed-size/recursive splitter or overlap implementation. Oversized chunks are rejected explicitly. PDF citations preserve page/item provenance; DOCX uses headings/item references and chunk numbers without inventing page numbers.

The model sees only the question and the selected whole chunks that fit the context budget. It returns structured `status`, `answer`, `citation_ids`, and `limitation`. The server checks allowed labels and agreement with inline `[C1]` markers. Missing/refused/truncated/invalid output fails the query; it cannot become an uncited successful answer.

An empty retrieval or context budget with no fitting passages returns a saved insufficient-context answer without a generation call. Inadequate nonempty context can also produce an explicit limitation from the model.

## Configuration and failure behavior

| Setting suffix, prefixed with NEXUS_ | Default |
| --- | --- |
| MAX_UPLOAD_BYTES | 20 MiB |
| MAX_DOCUMENT_PAGES | 100 |
| MAX_DOCUMENT_CHARS | 500,000 |
| MAX_DOCUMENT_CHUNKS | 1,000 |
| MAX_CHUNK_CHARS | 16,000 |
| MAX_QUESTION_CHARS | 4,000 |
| MAX_TOP_K | 20 |
| MAX_CONTEXT_CHARS | 24,000 |
| MAX_ANSWER_CHARS | 12,000 |
| MAX_ANSWER_TOKENS | 2,000 |
| PROVIDER_TIMEOUT_SECONDS | 45 |
| ANSWER_TIMEOUT_SECONDS | 90 |
| INGESTION_TIMEOUT_SECONDS | 180 |

The embedding schema is `vector(3072)` for the reviewed `text-embedding-3-large` deployment. Changing dimensions is a schema/indexing decision, not just an environment-variable change. `NEXUS_AZURE_OPENAI_MODEL` is the Azure chat deployment name; the configured `gpt-5.6-luna` name is used unchanged.

SDK retries are disabled. Missing configuration returns 503; provider failures/invalid output return 502; timeouts return 504. Invalid requests/documents return explicit 4xx codes. Failures after query creation include a `query_id`. Source failures can be inspected through the source list/detail endpoints.

Readiness checks database connectivity and whether provider settings are present. It does not validate credentials, make a paid request, or certify model quality.

PDF conversion uses Docling's timeout, and Azure uses SDK network timeouts. Elapsed budgets are checked between stages and before success. These are not OS-level hard deadlines that can forcibly interrupt a native parser or a model-weight download. Abrupt process termination/database loss can leave an in-progress record; durable recovery belongs to a later reviewed worker requirement.

## Privacy and dependencies

Original files, normalized text, vectors, questions, answers, and citation metadata are stored locally. Embedding requests send chunk text and questions to the configured Azure resource. Generation sends the question and bounded retrieved passages. Use only documents approved for that egress; this MVP has no tenant-level egress-policy engine. Docling parses locally but may download model weights from Hugging Face.

There is no authentication in this release. Docker publishes the database and API only on 127.0.0.1. Do not expose the API publicly without authentication, authorization, deployment hardening, and retention controls.

Core dependencies reviewed from the installed package metadata:

| Library | Responsibility | License metadata |
| --- | --- | --- |
| Docling 2.129.0, docling-core 2.97.1, docling-parse 7.20.0 | Parsing, structure-aware chunking, provenance | MIT |
| OpenAI SDK 1.109.1 | Azure requests and structured parsing | Apache-2.0 |
| SQLAlchemy 2.0.54, Alembic 1.20.0 | ORM and migrations | MIT |
| pgvector Python 0.5.0 | PostgreSQL vector bindings | MIT |
| psycopg 3.3.6 | PostgreSQL driver | LGPL-3.0-only |
| FastAPI 0.141.1, Pydantic 2.13.5 | HTTP/schema validation | MIT |
| PyTorch 2.14.0 / torchvision 0.29.0 | Local Docling inference | Bundled Apache/BSD/MIT/BSL terms; torchvision reports BSD |

Exact dependency versions and Linux CPU sources are in `uv.lock`. These notes are not a transitive-license or vulnerability certification; bundled native components and downloaded model weights retain their upstream terms. Tests reuse pytest, HTTPX, python-docx, and ReportLab. Retrieval metrics come from ir-measures.

## Reproduce verification

The PostgreSQL suite creates a uniquely named temporary schema, applies all migrations there, isolates each test transaction, and removes only that test schema. It does not clear your documents or reset the development database.

```bash
NEXUS_TEST_DATABASE_URL=postgresql+psycopg://nexus:nexus@localhost:5432/nexus \
  uv run --extra dev pytest -q

uv run --extra dev ruff check app tests evals alembic
uv run alembic check
uv lock --check
```

Without `NEXUS_TEST_DATABASE_URL`, database integration tests are explicitly skipped. Unit/provider tests need no real Azure credentials: they use the actual SDK with HTTPX MockTransport. Real PDF tests may download Docling's local inference weights. The optional synopsis chunk test is skipped if the local architecture PDF is absent; generated document fixtures remain available.

Live evaluation makes paid calls to your configured Azure deployments:

```bash
uv run --extra dev python -m evals.retrieval
uv run --extra dev python -m evals.answers --source-id SOURCE_UUID
```

Both default datasets target the architecture synopsis identified by its content hash. The answer runner verifies expected status, citation ownership/locators, and saved reload, and prints cited passages for a separate support review. An automated contract pass alone does not prove factual grounding.

## Acceptance record — 2026-09-24

Measured against local PostgreSQL/pgvector and the configured Azure deployments:

- 83 tests passed, including isolated real-PostgreSQL tests, real PDF/DOCX conversion, malformed/image-only inputs, limits, selected-source filtering, citation snapshots, timeouts, and invalid outputs.
- Ruff, lockfile consistency, and Alembic schema comparison passed. Upstream FastAPI/Starlette/Docling deprecation warnings remain; no test failed.
- Python 3.11 CPU-only Docker build and startup passed; database and API were healthy.
- The original 55-chunk synopsis source was preserved. Its 20 labeled retrieval questions produced Recall@1 0.6433, Recall@3 0.8800, Recall@5 0.9317, MRR@5 0.9000, and nDCG@5 0.8896. Labels were not changed for this run.
- Five live synopsis answer cases passed: direct objective, paraphrased retrieval, planner/dependency synthesis, missing budget, and outside-source knowledge. The final two correctly returned insufficient_context.
- Fresh two-page PDF and DOCX fixtures each completed upload, embedding storage, HTTP retrieval, two-passage generation, citation inspection, saved reload, and duplicate rejection inside Docker.
- All seven saved answers remained readable after the final API container recreation; the original synopsis still had its 55 ready chunks.

| Live operation | Observed time |
| --- | --- |
| Fresh PDF ingestion, including first container model download | 23.108 s |
| Fresh DOCX ingestion | 2.144 s |
| PDF fixture answer, including retrieval | 4.748 s |
| DOCX fixture answer, including retrieval | 5.107 s |
| Five synopsis answer HTTP requests | 4.455–6.414 s each |

The actual answer model reported `gpt-5.6-luna-2026-07-09`; prompt version was `grounded-answer-v3`. The seven answer requests reported 3,457 input tokens and 642 output tokens. Query embedding token counts are also saved. Monetary cost was not inferred from unverified deployment pricing; ingestion batch token totals are not currently persisted.

I reviewed the five supported answers against their 12 cited passages: the cited text supported the claims in these fixtures, and all 12 citation references/locators resolved correctly. This is an agent-performed fixture review, not an independent human evaluation or a statistically representative benchmark. The two deliberately unsupported questions correctly abstained; this does not establish general abstention precision.

The generated acceptance sources remain in the local database for inspection:

| Fixture | Source ID | Saved answer ID |
| --- | --- | --- |
| PDF | 4ed35701-43d5-49ae-a7b5-42beba6977f9 | 5d11aa5a-c8ee-40e6-b13f-f8463c64f8a5 |
| DOCX | f85353bd-3c5a-4cb5-a117-f13ef7882962 | 6d8a843c-6bc3-4552-a5cb-6bd44a0aa494 |

## Scope and known limitations

This release is a single-source API with exact vector retrieval. It has no frontend, multi-document synthesis, hybrid search/reranking, planner, worker/queue, web ingestion, cache, evidence/claim graph, or authentication. OCR and table/image understanding are deferred. Ready-source replacement/deletion and automatic recovery are also deferred.

Citation membership checks prevent references to unknown context labels; they cannot guarantee that every generated claim is supported. Retrieval results are nearest neighbors, not calibrated relevance probabilities. The small synopsis/fixture evaluation demonstrates the MVP path and supplies a baseline; broader documents and independent answer-quality review are still needed before a production quality claim.

MVP-2 remains a separate scope decision. Start it by choosing a concrete multi-document question after reviewing this working MVP.
