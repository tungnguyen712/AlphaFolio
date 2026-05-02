#!/bin/sh
set -e

case "$SERVICE_TYPE" in
  worker)
    exec celery -A app.workers.celery_app worker -Q agents_graph,ingest,maintenance --loglevel=INFO --concurrency=2
    ;;
  beat)
    exec celery -A app.workers.celery_app beat --loglevel=INFO
    ;;
  *)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
esac
