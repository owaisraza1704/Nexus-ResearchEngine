# Nexus Research Engine

The repository contains the architecture source, the MVP-first implementation specifications, and a provisional service skeleton. The coherent implementation plan is [`specs/05-implementation-plan.md`](specs/05-implementation-plan.md).

## Local development

Create an isolated environment and install the project with development dependencies:

```bash
uv sync --extra dev
```

Run the focused tests:

```bash
uv run pytest
```

Run the API without external services:

```bash
uv run uvicorn app.main:app --reload
```

The liveness endpoint is available at `http://127.0.0.1:8000/health/live`. The readiness endpoint requires PostgreSQL.

Start the local infrastructure with Docker Compose:

```bash
docker compose up -d postgres
uv run alembic upgrade head
docker compose up api
```

The active implementation order and acceptance gates are documented in [`specs/05-implementation-plan.md`](specs/05-implementation-plan.md). The release progression is [`specs/release-roadmap.md`](specs/release-roadmap.md); stage-specific details live in the linked `mvp1/`, `mvp2/`, and `mvp3/` folders.
