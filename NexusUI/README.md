# Nexus UI

The Next.js interface for the local Nexus Research Engine. Workspaces, drafts, sources, jobs, findings and reviews are saved by the backend; there are no operational demo records or browser-local research stores.

## Run the complete product

From the repository root, with the existing Azure `.env` configured:

```sh
docker compose up --build -d
```

Open http://127.0.0.1:3000. The [local runbook](../docs/mvp3.md) covers setup, supported inputs, worker recovery, budgets, API contracts, verification and known limits.

## Frontend development

Use Node.js 22 and pnpm. Start the API and worker separately, then:

```sh
pnpm install --frozen-lockfile
pnpm dev
```

The dev server binds to loopback. `/api/backend/*` is proxied to `http://127.0.0.1:8000` by default. `NEXUS_API_URL` changes the upstream when building/running in a different local layout; Docker uses `http://api:8000`. Azure credentials are server-only and must never be put in a `NEXT_PUBLIC_*` variable.

## Navigation

| Route | Purpose |
| --- | --- |
| `/` | Approved dark landing page with a labeled illustrative hero |
| `/research` | Database-backed research library, cards/list and search |
| `/research/new` | Create an empty research workspace |
| `/research/[researchId]` | Question/draft, five modes, source selection and optional approved URLs |
| `.../sources` | Upload, select, inspect, retry failed uploads, attach existing sources |
| `.../sources/[sourceId]` | Original document, parsed text, chunks and historical exact-passage links |
| `.../runs` | Persisted job history |
| `.../runs/[runId]` | Live progress/cancellation or validated result; plan, tasks, attempts, events |
| `.../evidence` | Saved passages and provenance for a selected result |
| `.../reports` | Saved reports and Markdown/JSON download |
| `.../graph` | Source/evidence/claim graph from actual results |
| `.../evaluation` | Execution statistics and your persisted manual quality reviews |
| `.../settings` | Workspace editing and redacted local configuration/worker status |

The nested `runId` is the asynchronous job ID. Workspaces separate research context; they are not multi-user access-control boundaries. The old `/workflow` route redirects to actual run history.

## Check and build

```sh
pnpm typecheck
pnpm build
pnpm exec playwright install chromium
NEXUS_E2E_BASE_URL=http://127.0.0.1:3000 NEXUS_LIVE_E2E=1 pnpm test:e2e
```

The live browser cases upload synthetic PDF/DOCX fixtures and fetch an explicitly approved public page using the configured Azure deployments. They verify completion after closing/reopening the tab, exact citations, exports, manual reviews and fresh web consent. They leave labeled verification workspaces in the local database. Omit `NEXUS_LIVE_E2E` to skip those billable cases; the other browser tests still use the API/database. With no `NEXUS_E2E_BASE_URL`, Playwright starts the built frontend on port 3200.

SWR handles cache/revalidation and optimistic source selection. React Flow and Dagre render/layout the graphs. react-markdown renders output without executing raw HTML or loading generated images. The formatter was upgraded to oxfmt 0.70.0; `pnpm format --check` checks formatting.

The approved Inter and JetBrains Mono typography loads from Google Fonts. Network access is needed for those fonts and the configured Azure services.
