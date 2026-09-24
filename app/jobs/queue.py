"""Use Procrastinate's transaction, delivery locks, retry scheduling, and worker heartbeats."""

import procrastinate
from sqlalchemy.orm import Session

producer = procrastinate.App(connector=procrastinate.SyncPsycopgConnector())


def enqueue(db: Session, task_name: str, *, lock: str, **kwargs: str) -> int:
    # SQLAlchemy owns this transaction. The library must not open or commit another one.
    connection = db.connection().connection.driver_connection
    return producer.configure_task(
        name=task_name, queue="nexus", lock=lock, connection=connection
    ).defer(**kwargs)
