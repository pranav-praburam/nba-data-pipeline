import os
import threading
import time
from collections import defaultdict, deque
import secrets
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request

from app import config as config_module


router = APIRouter(prefix="/admin", tags=["admin"])
ADMIN_RATE_LIMIT = 10
ADMIN_RATE_WINDOW_SECONDS = 300
admin_request_history: dict[str, deque[float]] = defaultdict(deque)
admin_rate_limit_lock = threading.Lock()


def run_ingestion_job(season: str, full_refresh: bool, source: str):
    # Import lazily so normal API startup does not pay the nba_api/pandas import cost.
    from ingest_games import ingest_games

    ingest_games(season=season, full_refresh=full_refresh, source=source)


def run_generate_picks_job(target_date: Optional[str], last_n: int, edge_threshold: float):
    from app.db.database import SessionLocal
    from app.services.picks import generate_model_picks

    db = SessionLocal()
    try:
        generate_model_picks(
            db,
            target_date=target_date,
            last_n=last_n,
            edge_threshold=edge_threshold,
        )
    finally:
        db.close()


def run_settle_picks_job(settle_before_date: Optional[str]):
    from app.db.database import SessionLocal
    from app.services.picks import settle_model_picks

    db = SessionLocal()
    try:
        settle_model_picks(db, settle_before_date=settle_before_date)
    finally:
        db.close()


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
    ingest_api_key = os.getenv("INGEST_API_KEY") or config_module.INGEST_API_KEY
    if not ingest_api_key:
        raise HTTPException(
            status_code=503,
            detail="Admin ingestion is disabled because INGEST_API_KEY is not configured.",
        )

    if not x_api_key or not secrets.compare_digest(x_api_key, ingest_api_key):
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


@router.post("/picks/generate")
def trigger_picks_generation(
    request: Request,
    background_tasks: BackgroundTasks,
    game_date: Optional[str] = None,
    last_n: int = Query(default=10, ge=3, le=25),
    edge_threshold: float = Query(default=0.03, ge=0.0, le=0.25),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    ingest_api_key = os.getenv("INGEST_API_KEY") or config_module.INGEST_API_KEY
    if not ingest_api_key:
        raise HTTPException(
            status_code=503,
            detail="Admin picks generation is disabled because INGEST_API_KEY is not configured.",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, ingest_api_key):
        raise HTTPException(status_code=401, detail="Invalid ingestion API key.")

    client_host = request.client.host if request.client else "unknown"
    enforce_admin_rate_limit(client_host)
    background_tasks.add_task(run_generate_picks_job, game_date, last_n, edge_threshold)
    return {
        "status": "accepted",
        "trigger": "deployed_api",
        "job": "generate_picks",
        "game_date": game_date,
        "last_n": last_n,
        "edge_threshold": edge_threshold,
    }


@router.post("/picks/settle")
def trigger_picks_settlement(
    request: Request,
    background_tasks: BackgroundTasks,
    settle_before_date: Optional[str] = None,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    ingest_api_key = os.getenv("INGEST_API_KEY") or config_module.INGEST_API_KEY
    if not ingest_api_key:
        raise HTTPException(
            status_code=503,
            detail="Admin picks settlement is disabled because INGEST_API_KEY is not configured.",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, ingest_api_key):
        raise HTTPException(status_code=401, detail="Invalid ingestion API key.")

    client_host = request.client.host if request.client else "unknown"
    enforce_admin_rate_limit(client_host)
    background_tasks.add_task(run_settle_picks_job, settle_before_date)
    return {
        "status": "accepted",
        "trigger": "deployed_api",
        "job": "settle_picks",
        "settle_before_date": settle_before_date,
    }
