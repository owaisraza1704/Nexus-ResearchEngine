"""Bridge our PostgreSQL transaction to Celery without a database/broker dual-write gap."""

import logging
from datetime import datetime, timedelta, timezone

from kombu.exceptions import OperationalError
from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from app.db.job_models import QueueDelivery
from app.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def enqueue(db: Session, task_name: str, *, lock: str, **kwargs: str) -> int:
    delivery = QueueDelivery(task_name=task_name, args=kwargs, lock_key=lock)
    db.add(delivery)
    db.flush()
    return delivery.id


def cancel_delivery(db: Session, delivery_id: int) -> None:
    db.execute(
        update(QueueDelivery)
        .where(QueueDelivery.id == delivery_id)
        .values(cancelled_at=datetime.now(timezone.utc))
    )


def publish_pending(db: Session, *, app=celery_app) -> int:
    """Publish committed intent; re-deliver abandoned work, never a live locked task."""
    now = datetime.now(timezone.utc)
    deliveries = db.scalars(
        select(QueueDelivery)
        .where(
            QueueDelivery.finished_at.is_(None),
            QueueDelivery.cancelled_at.is_(None),
            or_(
                QueueDelivery.published_at.is_(None),
                QueueDelivery.published_at < now - timedelta(seconds=60),
            ),
        )
        .order_by(QueueDelivery.id)
        .limit(100)
        .with_for_update(skip_locked=True)
    ).all()
    published = 0
    for delivery in deliveries:
        if delivery.published_at is not None:
            available = db.scalar(
                text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"),
                {"key": delivery.lock_key},
            )
            if not available:
                continue
            db.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"),
                {"key": delivery.lock_key},
            )
        try:
            app.send_task(
                "nexus.deliver",
                args=[delivery.id],
                task_id=str(delivery.celery_id),
                queue=app.conf.task_default_queue,
                retry=False,
            )
        except (OperationalError, OSError):
            db.rollback()
            logger.warning("queue_broker_unavailable")
            return 0
        delivery.published_at = now
        published += 1
    db.commit()
    return published
