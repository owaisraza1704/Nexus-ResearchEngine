from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from kombu.exceptions import OperationalError
from sqlalchemy import text

from app.db.job_models import QueueDelivery
from app.jobs.queue import cancel_delivery, enqueue, publish_pending


@pytest.fixture
def sender():
    return SimpleNamespace(conf=SimpleNamespace(task_default_queue="test"), send_task=Mock())


def test_enqueue_uses_callers_transaction_and_no_broker(db, sender):
    with pytest.raises(ValueError), db.begin_nested():
        identity = enqueue(db, "nexus.plan", lock="plan:test", job_id="test")
        raise ValueError("Application transaction failed")
    assert db.get(QueueDelivery, identity) is None
    sender.send_task.assert_not_called()


def test_broker_outage_preserves_accepted_work(db, sender):
    identity = enqueue(db, "nexus.plan", lock="plan:test", job_id="test")
    db.commit()
    sender.send_task.side_effect = OperationalError("broker offline")
    assert publish_pending(db, app=sender) == 0
    assert db.get(QueueDelivery, identity).published_at is None
    sender.send_task.side_effect = None
    assert publish_pending(db, app=sender) == 1
    delivery = db.get(QueueDelivery, identity)
    assert delivery.published_at is not None
    sender.send_task.assert_called_with(
        "nexus.deliver",
        args=[identity],
        task_id=str(delivery.celery_id),
        queue="test",
        retry=False,
    )


def test_cancelled_and_finished_deliveries_are_not_published(db, sender):
    cancelled = enqueue(db, "nexus.plan", lock="cancelled", job_id="test")
    finished = enqueue(db, "nexus.plan", lock="finished", job_id="test")
    cancel_delivery(db, cancelled)
    db.get(QueueDelivery, finished).finished_at = datetime.now(timezone.utc)
    db.commit()
    assert publish_pending(db, app=sender) == 0
    sender.send_task.assert_not_called()


def test_recovery_reuses_identity_but_never_republishes_a_live_task(db, migrated_database, sender):
    engine, _ = migrated_database
    key = "lock-test:" + uuid4().hex
    identity = enqueue(db, "nexus.plan", lock=key, job_id="test")
    db.commit()
    assert publish_pending(db, app=sender) == 1
    original_id = str(db.get(QueueDelivery, identity).celery_id)
    db.get(QueueDelivery, identity).published_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    db.commit()
    with engine.connect() as owner:
        owner.execute(text("SELECT pg_advisory_lock(hashtextextended(:key, 0))"), {"key": key})
        owner.commit()
        try:
            assert publish_pending(db, app=sender) == 0
        finally:
            owner.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"),
                {"key": key},
            )
            owner.commit()
    assert publish_pending(db, app=sender) == 1
    assert sender.send_task.call_args.kwargs["task_id"] == original_id


def test_repeated_dispatch_does_not_republish_recent_messages(db, sender):
    enqueue(db, "nexus.plan", lock="test", job_id="test")
    db.commit()
    assert publish_pending(db, app=sender) == 1
    assert publish_pending(db, app=sender) == 0
    assert sender.send_task.call_count == 1
