import threading
import time
from collections import defaultdict, deque
import secrets
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

from app.config import INGEST_API_KEY


router = APIRouter(prefix="/admin", tags=["admin"])
ADMIN_RATE_LIMIT = 10
ADMIN_RATE_WINDOW_SECONDS = 300
admin_request_history: dict[str, deque[float]] = defaultdict(deque)
admin_rate_limit_lock = threading.Lock()


def run_ingestion_job(season: str, full_refresh: bool, source: str):
    # Import lazily so normal API startup does not pay the nba_api/pandas import cost.
    from ingest_games import ingest_games

    ingest_games(season=season, full_refresh=full_refresh, source=source)


def enforce_admin_rate_limit(client_host: str) -> None:
    now = time.time()

    with admin_rate_limit_lock:
        request_timestamps = admin_request_history[client_host]

        while request_timestamps and now - request_timestamps[0] > ADMIN_RATE_WINDOW_SECONDS:
            request_timestamps.popleft()

        if len(request_timestamps) >= ADMIN_RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Too many admin ingestion requests. Try again in a few minutes.",
            )

        request_timestamps.append(now)


@router.post("/ingest")
def trigger_ingestion(
    request: Request,
    background_tasks: BackgroundTasks,
    season: str = Query(default="2025-26"),
    full_refresh: bool = False,
    source: str = Query(default="live", pattern="^(live|stats)$"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    # GitHub Actions and manual deployment checks call this endpoint to trigger
    # ingestion without exposing database credentials outside the deployed service.
    if not INGEST_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Admin ingestion is disabled because INGEST_API_KEY is not configured.",
        )

    if not x_api_key or not secrets.compare_digest(x_api_key, INGEST_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid ingestion API key.")

    client_host = request.client.host if request.client else "unknown"
    enforce_admin_rate_limit(client_host)

    background_tasks.add_task(run_ingestion_job, season, full_refresh, source)

    return {
        "status": "accepted",
        "trigger": "deployed_api",
        "season": season,
        "full_refresh": full_refresh,
        "source": source,
        "message": "Ingestion started in the background. Check /pipeline/runs for the recorded result.",
    }
