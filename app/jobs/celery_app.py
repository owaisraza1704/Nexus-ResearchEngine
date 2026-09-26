"""Celery owns transport, worker processes, retries and periodic outbox delivery."""

from celery import Celery

from app.config import get_settings

settings = get_settings()
celery_app = Celery("nexus", broker=settings.celery_broker_url, include=["app.worker"])
celery_app.conf.update(
    task_default_queue=settings.celery_queue,
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.worker_concurrency,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    broker_connection_timeout=2,
    broker_transport_options={
        "visibility_timeout": 3600,
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
        "global_keyprefix": settings.celery_queue + ":",
    },
    beat_schedule={
        "deliver-accepted-work": {
            "task": "nexus.dispatch",
            "schedule": 1.0,
            "options": {"expires": 1},
        },
    },
)
