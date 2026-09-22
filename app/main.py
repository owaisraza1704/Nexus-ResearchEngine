from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.retrieval import router as retrieval_router
from app.api.sources import router as sources_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nexus Research Engine",
        version="0.1.0",
        description="A source-grounded research engine.",
    )
    app.include_router(health_router)
    app.include_router(retrieval_router)
    app.include_router(sources_router)
    return app


app = create_app()
