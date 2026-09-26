"""A real worker-process crash/restart test, isolated from the user's database schema.

Only the provider HTTP response is controlled. Queue delivery, PostgreSQL commits,
the worker executable, crash recovery, handlers, and result persistence are real.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import pytest
from alembic.config import Config
from celery import Celery
from redis import Redis
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from alembic import command
from app.db.job_models import (
    JobBudget,
    JobEvent,
    QueueDelivery,
    ResearchJob,
    ResearchTask,
    TaskAttempt,
    WorkspaceSource,
)
from app.db.models import ChunkEmbedding, Document, DocumentChunk, Source, Workspace
from app.db.research_models import EvidenceItem, ResearchResult, ResultCitation
from app.jobs.contracts import JobRequest
from app.jobs.queue import enqueue, publish_pending
from app.jobs.service import create_job, job_progress


@pytest.fixture
def worker_database():
    url = os.getenv("NEXUS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set NEXUS_TEST_DATABASE_URL to run the isolated worker integration test")
    # Queue functions accept schema-local enum types. A second queue schema on the
    # same search path makes overload resolution ambiguous; use a disposable DB.
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    name = "nexus_worker_test_" + uuid4().hex
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = create_engine(admin.url.set(database=name))
    try:
        with engine.begin() as connection:
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{name}"')
        admin.dispose()


def test_worker_crash_recovery_and_duplicate_delivery(worker_database, settings):
    engine = worker_database
    broker = os.getenv("NEXUS_TEST_CELERY_BROKER_URL")
    if not broker:
        pytest.skip("Set NEXUS_TEST_CELERY_BROKER_URL for the real Celery worker test")
    queue = "nexus_test_" + uuid4().hex
    sender = Celery("isolated-test", broker=broker)
    sender.conf.update(
        task_default_queue=queue,
        broker_transport_options={"global_keyprefix": queue + ":"},
    )
    called, release = threading.Event(), threading.Event()
    calls = []

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(payload)
            called.set()
            if len(calls) == 1:
                release.wait(30)
            body = json.dumps(
                {
                    "object": "list",
                    "model": "text-embedding-3-large",
                    "data": [
                        {"object": "embedding", "index": 0, "embedding": [1.0] + [0.0] * 3071}
                    ],
                    "usage": {"prompt_tokens": 8, "total_tokens": 8},
                }
            ).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    processes = []
    logs = tempfile.TemporaryFile(mode="w+")
    environment = {
        **os.environ,
        "NEXUS_DATABASE_URL": engine.url.render_as_string(hide_password=False),
        "NEXUS_AZURE_OPENAI_ENDPOINT": f"http://127.0.0.1:{server.server_port}",
        "NEXUS_AZURE_OPENAI_API_KEY": "test-only-key",
        "NEXUS_AZURE_OPENAI_API_VERSION": "2024-10-21",
        "NEXUS_AZURE_OPENAI_EMBEDDING_DEPLOYMENT": settings.azure_openai_embedding_deployment,
        "NEXUS_AZURE_OPENAI_MODEL": "test-chat",
        "NEXUS_WORKER_CONCURRENCY": "1",
        "NEXUS_CELERY_BROKER_URL": broker,
        "NEXUS_CELERY_QUEUE": queue,
        "NUMBA_NUM_THREADS": "1",
    }

    def start_worker():
        process = subprocess.Popen(
            [
                str(Path(sys.executable).with_name("celery")),
                "-A",
                "app.worker:celery_app",
                "worker",
                "--pool=solo",
                "--concurrency=1",
                "--loglevel=INFO",
                "--without-gossip",
                "--without-mingle",
            ],
            env=environment,
            stdout=logs,
            stderr=logs,
        )
        processes.append(process)
        return process

    def wait_until(predicate, seconds=25):
        deadline = monotonic() + seconds
        while monotonic() < deadline:
            with Session(engine) as db:
                if predicate(db):
                    return
            sleep(0.1)
        logs.seek(0)
        raise AssertionError("Worker did not settle:\n" + logs.read()[-5000:])

    try:
        with Session(engine, autoflush=False) as db:
            project = Workspace(name="Worker process test", slug=uuid4().hex, policy={})
            source = Source(
                display_name="Worker fixture",
                original_filename="fixture.pdf",
                content_sha256=uuid4().hex * 2,
                status="ready",
            )
            db.add_all([project, source])
            db.flush()
            passage = "Alpha retains records for 30 days."
            document = Document(
                source_id=source.id,
                version=1,
                status="ready",
                mime_type="application/pdf",
                parser_name="fixture",
                parser_version="1",
                normalized_text=passage,
                document_metadata={},
            )
            db.add(document)
            db.flush()
            chunk = DocumentChunk(
                document_id=document.id,
                sequence=0,
                text=passage,
                text_sha256=sha256(passage.encode()).hexdigest(),
                locator={"page": 1},
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
                    embedding=[1.0] + [0.0] * 3071,
                )
            )
            source.current_document_id = document.id
            db.add(WorkspaceSource(workspace_id=project.id, source_id=source.id))
            db.commit()
            job = create_job(
                db,
                JobRequest(
                    workspace_id=project.id,
                    question="Alpha retention period?",
                    source_ids=[source.id],
                    mode="evidence",
                ),
                settings,
            )
            job_id, run_id = job.id, job.run_id
            assert publish_pending(db, app=sender) == 1
        first = start_worker()
        assert called.wait(25), "The real worker did not reach the local provider"
        first.kill()
        first.wait(timeout=10)
        release.set()
        with Session(engine) as db:
            db.execute(
                text(
                    "UPDATE queue_deliveries SET published_at=now()-interval '2 minutes' "
                    "WHERE task_name='nexus.execute' AND finished_at IS NULL"
                ),
            )
            db.commit()
            assert publish_pending(db, app=sender) == 1
        start_worker()
        wait_until(lambda db: db.get(ResearchJob, job_id).status == "completed")
        with Session(engine) as db:
            retrieval = db.scalar(
                select(ResearchTask).where(
                    ResearchTask.job_id == job_id, ResearchTask.task_type == "retrieve_internal"
                )
            )
            attempts = db.scalars(
                select(TaskAttempt)
                .where(TaskAttempt.task_id == retrieval.id)
                .order_by(TaskAttempt.attempt_number)
            ).all()
            assert [attempt.status for attempt in attempts] == ["interrupted", "succeeded"]
            duplicate_id = enqueue(
                db, "nexus.execute", lock=f"task:{retrieval.id}", task_id=str(retrieval.id)
            )
            db.commit()
            assert publish_pending(db, app=sender) == 1
        wait_until(lambda db: db.get(QueueDelivery, duplicate_id).finished_at is not None)
        with Session(engine) as db:
            assert len(calls) == 2
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(ResearchResult)
                    .where(ResearchResult.research_run_id == run_id)
                )
                == 1
            )
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(EvidenceItem)
                    .where(EvidenceItem.research_run_id == run_id)
                )
                == 1
            )
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(ResultCitation)
                    .where(ResultCitation.research_run_id == run_id)
                )
                == 1
            )
            assert db.get(JobBudget, job_id).reserved_input_tokens > 0
            assert (
                job_progress(db, db.get(ResearchJob, job_id))["budget"]["unknown_usage_calls"] == 1
            )
            events = db.scalars(select(JobEvent.event_type).where(JobEvent.job_id == job_id)).all()
            assert "task_recovered" in events and "task_delivery_reused" in events
    finally:
        release.set()
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        server.shutdown()
        server.server_close()
        logs.close()
        engine.dispose()
        sender.close()
        # Only this test's unique broker namespace; never flush the shared Redis database.
        with Redis.from_url(broker) as redis:
            keys = list(redis.scan_iter(match=queue + ":*"))
            if keys:
                redis.delete(*keys)
