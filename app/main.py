import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.answers import router as answers_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.projects import router as projects_router
from app.api.research import router as research_router
from app.api.retrieval import router as retrieval_router
from app.api.sources import router as sources_router
from app.api.system import router as system_router
from app.errors import NexusError

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nexus Research Engine",
        version="0.1.0",
        description="A source-grounded research engine.",
    )

    @app.exception_handler(NexusError)
    async def nexus_error_handler(request: Request, error: NexusError) -> JSONResponse:
        detail = {"code": error.code, "message": str(error), "retryable": error.retryable}
        if error.query_id is not None:
            detail["query_id"] = str(error.query_id)
        if error.run_id is not None:
            detail["run_id"] = str(error.run_id)
        if error.job_id is not None:
            detail["job_id"] = str(error.job_id)
        return JSONResponse(status_code=error.status_code, content={"error": detail})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request fields are missing or invalid. See /docs for the schema.",
                    "retryable": False,
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, error: SQLAlchemyError) -> JSONResponse:
        # SQL exception details can include document text and bound credentials.
        logger.error("database_request_failed type=%s", type(error).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "The database request could not be completed.",
                    "retryable": True,
                }
            },
        )

    app.include_router(answers_router)
    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(jobs_router)
    app.include_router(system_router)
    app.include_router(research_router)
    app.include_router(retrieval_router)
    app.include_router(sources_router)
    return app


app = create_app()
