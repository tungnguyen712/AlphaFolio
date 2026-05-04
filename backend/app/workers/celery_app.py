import time
from types import TracebackType
from typing import Any

import structlog
from celery import Celery, signals

from app.config import get_settings
from app.logging import configure_logging

configure_logging()
settings = get_settings()
logger = structlog.get_logger(__name__)

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


@signals.task_prerun.connect
def _log_task_started(
    task_id: str | None = None,
    task: Any | None = None,
    args: tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
    **_: Any,
) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(task_id=task_id, task_name=task.name if task else None)
    if task is not None:
        task.request._alphafolio_started_at = time.perf_counter()
    logger.info(
        "celery_task_started",
        task_id=task_id,
        task_name=task.name if task else None,
        args_count=len(args or ()),
        kwargs_keys=sorted((kwargs or {}).keys()),
    )


@signals.task_postrun.connect
def _log_task_finished(
    task_id: str | None = None,
    task: Any | None = None,
    state: str | None = None,
    retval: Any | None = None,
    **_: Any,
) -> None:
    started = getattr(task.request, "_alphafolio_started_at", None) if task else None
    latency_ms = round((time.perf_counter() - started) * 1000, 2) if started else None
    logger.info(
        "celery_task_finished",
        task_id=task_id,
        task_name=task.name if task else None,
        state=state,
        latency_ms=latency_ms,
        result=str(retval)[:300] if retval is not None else None,
    )
    structlog.contextvars.clear_contextvars()


@signals.task_retry.connect
def _log_task_retry(
    request: Any | None = None,
    reason: BaseException | None = None,
    einfo: Any | None = None,
    **_: Any,
) -> None:
    logger.warning(
        "celery_task_retry",
        task_id=getattr(request, "id", None),
        task_name=getattr(request, "task", None),
        reason=str(reason) if reason else None,
        exception=str(einfo.exception) if einfo else None,
    )


@signals.task_failure.connect
def _log_task_failure(
    task_id: str | None = None,
    exception: BaseException | None = None,
    traceback: TracebackType | None = None,
    sender: Any | None = None,
    **_: Any,
) -> None:
    exc_info = (type(exception), exception, traceback) if exception else None
    logger.error(
        "celery_task_failed",
        task_id=task_id,
        task_name=getattr(sender, "name", None),
        error=str(exception) if exception else None,
        exc_info=exc_info,
    )
