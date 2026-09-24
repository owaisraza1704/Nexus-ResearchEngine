import json
import os
from hashlib import sha256
from uuid import uuid4

import httpx
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from openai import AzureOpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import command
from app.config import Settings, get_settings
from app.db.models import ChunkEmbedding, Document, DocumentChunk, Source
from app.db.session import get_db
from app.embeddings import azure_openai as embeddings
from app.llm import azure_openai as llm
from app.main import create_app


@pytest.fixture
def mock_azure(monkeypatch):
    """Keep the real SDK's serialization and parsing; replace only HTTP."""

    def install(adapter, handler):
        def client(**kwargs):
            return AzureOpenAI(
                **kwargs,
                http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            )

        monkeypatch.setattr(adapter, "AzureOpenAI", client)

    return install


@pytest.fixture(scope="session")
def migrated_database():
    url = os.getenv("NEXUS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set NEXUS_TEST_DATABASE_URL to run isolated PostgreSQL integration tests")
    engine = create_engine(url)
    schema = f"nexus_test_{uuid4().hex}"
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
        connection.execute(CreateSchema(schema))
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'SET search_path TO "{schema}", public')
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            config.attributes["version_table_schema"] = schema
            command.upgrade(config, "head")
        yield engine, schema
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.fixture
def db(migrated_database):
    engine, schema = migrated_database
    with engine.connect() as connection:
        transaction = connection.begin()
        connection.exec_driver_sql(f'SET search_path TO "{schema}", public')
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        artifact_store_path=tmp_path / "artifacts",
        azure_openai_endpoint="https://test.openai.azure.com",
        azure_openai_api_key="test-key",
        azure_openai_api_version="2024-10-21",
        azure_openai_model="test-chat",
        azure_openai_embedding_deployment="test-embedding",
    )


@pytest.fixture
def client(db, settings):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client


@pytest.fixture
def ready_source(db, settings):
    def create(
        texts=("Nexus produces cited research answers.", "Sources retain document versions."),
    ):
        source = Source(
            display_name="Research fixture",
            original_filename="research.pdf",
            content_sha256=uuid4().hex * 2,
            status="ready",
        )
        db.add(source)
        db.flush()
        document = Document(
            source_id=source.id,
            version=1,
            status="ready",
            mime_type="application/pdf",
            parser_name="docling",
            parser_version="test",
            normalized_text="\n\n".join(texts),
            document_metadata={},
            page_count=len(texts),
        )
        db.add(document)
        db.flush()
        chunks = []
        for sequence, text in enumerate(texts):
            chunk = DocumentChunk(
                document_id=document.id,
                sequence=sequence,
                text=text,
                text_sha256=sha256(text.encode()).hexdigest(),
                locator={
                    "doc_items": [
                        {
                            "self_ref": f"#/texts/{sequence}",
                            "prov": [{"page_no": sequence + 1, "charspan": [0, len(text)]}],
                        }
                    ]
                },
            )
            db.add(chunk)
            db.flush()
            db.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    provider="azure_openai",
                    deployment=settings.azure_openai_embedding_deployment,
                    model="text-embedding-3-large",
                    dimensions=3072,
                    embedding=[1.0, sequence * 0.1] + [0.0] * 3070,
                )
            )
            chunks.append(chunk)
        source.current_document_id = document.id
        db.commit()
        return source, document, chunks

    return create


@pytest.fixture
def azure_api(mock_azure):
    state = {
        "calls": [],
        "answer": {
            "status": "completed",
            "answer": "Nexus produces cited research answers. [C1]",
            "citation_ids": ["C1"],
            "limitation": None,
        },
        "chat_error": None,
        "embedding_error": None,
    }

    def handler(request):
        payload = json.loads(request.content)
        state["calls"].append((request.url.path, payload))
        if request.url.path.endswith("/embeddings"):
            if state["embedding_error"]:
                raise state["embedding_error"]
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "model": "text-embedding-3-large",
                    "data": [
                        {"object": "embedding", "index": index, "embedding": [1.0] + [0.0] * 3071}
                        for index, _ in enumerate(payload["input"])
                    ],
                    "usage": {"prompt_tokens": 8, "total_tokens": 8},
                },
            )
        if state["chat_error"]:
            raise state["chat_error"]
        return httpx.Response(
            200,
            json={
                "id": "chat-test",
                "object": "chat.completion",
                "created": 1,
                "model": "test-chat-version",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(state["answer"]),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            },
        )

    mock_azure(embeddings, handler)
    mock_azure(llm, handler)
    return state


@pytest.fixture
def research_sources(ready_source):
    return [
        ready_source(("Alpha retains records for 30 days and executes requests synchronously.",)),
        ready_source(("Beta retains records for 90 days and executes requests asynchronously.",)),
    ]


@pytest.fixture
def research_azure(azure_api):
    azure_api["answer"] = {
        "status": "completed",
        "summary": "Alpha retains records for 30 days [E1]; Beta retains them for 90 days [E2].",
        "limitation": None,
        "relevant_evidence_ids": ["E1", "E2"],
        "claims": [
            {
                "text": "Alpha retains records for 30 days.",
                "claim_type": "comparison",
                "support_status": "supported",
                "evidence": [
                    {"evidence_id": "E1", "relationship": "supports", "explanation": None}
                ],
            },
            {
                "text": "Beta retains records for 90 days.",
                "claim_type": "comparison",
                "support_status": "supported",
                "evidence": [
                    {"evidence_id": "E2", "relationship": "supports", "explanation": None}
                ],
            },
        ],
        "gaps": [],
    }
    return azure_api
