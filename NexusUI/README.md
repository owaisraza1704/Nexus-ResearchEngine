# Nexus UI

The Next.js interface for Nexus Research Engine: a public introduction, a research library, and a dedicated workspace for each research.

This is a UI-only preview. Uploads and research generation are not connected to the backend. Sample results are labelled examples, not answers generated from a new question.

## Navigation

| Route | Purpose |
| --- | --- |
| `/` | Public landing page without the workspace sidebar |
| `/research` | Search, browse, and open researches in card or list view |
| `/research/new` | Create a new, empty research |
| `/research/[researchId]` | Research-specific question composer and recent runs |
| `/research/[researchId]/sources` | Only this research's sources and source selection |
| `/research/[researchId]/sources/[sourceId]` | Inspect a source belonging to this research |
| `/research/[researchId]/runs` | This research's run history |
| `/research/[researchId]/runs/[runId]` | A result belonging to this research |

Evidence, reports, graph, evaluation, settings, and the future workflow preview also live beneath `/research/[researchId]`. The original illustrative screens are available in the Transformer architectures example; other researches show empty states instead of borrowing its data. The old unscoped URLs such as `/sources`, `/jobs`, and `/evidence` have been replaced by research-specific routes.

## Local state

Creating research, editing its question, choosing a mode/Top-K, and selecting sources work locally. Zustand persists these changes in browser storage under `nexus-research-ui`, so switching researches or refreshing does not discard a draft. A new research starts with no sources or runs.

This is not server persistence or access control. Local research URLs only resolve in the browser where the research was created; they are not shareable records across devices. Clearing this site's browser storage resets the examples and removes local drafts. No document files are uploaded or stored by this interface.

## Run locally

Use Node.js 22 and pnpm.

```sh
pnpm install
pnpm dev
```

Open http://localhost:3000.

## Check and build

```sh
pnpm typecheck
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

The browser tests start a production server on port 3200 and stop it afterward. To run production manually, use `pnpm start` after building.

Formatting note: the existing `pnpm format` command uses an older oxfmt version that produced invalid TypeScript during this change. The affected declaration was corrected, and the new files were formatted with Prettier. Updating the project's formatter remains a separate tooling task.

## Where things live

- `src/app/`: Next.js routes, the root layout, and font loading.
- `src/views/`: interactive screen components.
- `src/components/`: shared sidebar, layout, and command palette.
- `src/components/ResearchStore.tsx`: browser-local research state and persistence.
- `src/components/ResearchScope.tsx`: selects the research for all nested screens.
- `src/data/research.ts`: minimal UI models and explicitly labelled example records.
- `src/index.css` and `src/styles/`: workspace theme, research layouts, and landing styles.
- `tests/`: browser checks for routes and demo interactions.

The interface loads Inter and JetBrains Mono from Google Fonts; the typography check requires network access.

Browser tests cover creation, research isolation, persisted drafts and source selections, invalid cross-research links, citation inspection, navigation, mobile layouts, and hydration errors.
