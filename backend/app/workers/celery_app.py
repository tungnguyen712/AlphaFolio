from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "alphafolio",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_default_queue="agents_graph",
    task_queues=None,
    task_acks_late=True,
    # Reject (re-queue) in-flight tasks when the worker process is killed
    # unexpectedly (OOM, node eviction). Combined with acks_late=True this
    # guarantees at-least-once delivery without losing the task.
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "evaluate-triggers-every-minute": {
            "task": "maintenance.evaluate_triggers",
            "schedule": 60.0,
            "options": {"queue": "maintenance"},
        },
    },
)
