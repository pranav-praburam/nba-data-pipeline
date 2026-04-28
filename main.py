import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.config import ALLOWED_HOSTS, ENABLE_DOCS
from app.db import models  # noqa: F401
from app.db.database import Base, engine


logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        # Only advertise HSTS when the request is already using HTTPS. Setting
        # it on plain HTTP would not meaningfully protect the current raw-IP deployment.
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


async def initialize_database(max_attempts: int = 5, delay_seconds: int = 3) -> None:
    # Render can start the web service before Postgres is ready, so startup retries
    # make deploys more reliable without crashing the whole API container.
    for attempt in range(1, max_attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialization succeeded on attempt %s.", attempt)
            return
        except SQLAlchemyError as exc:
            logger.warning(
                "Database initialization failed on attempt %s/%s: %s",
                attempt,
                max_attempts,
                exc,
            )
            if attempt == max_attempts:
                logger.warning(
                    "Starting API without confirmed database initialization. "
                    "Retry by redeploying or rerunning ingestion once the database is reachable."
                )
                return
            await asyncio.sleep(delay_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep table creation close to app startup for a simple portfolio deploy.
    # Larger production systems would usually replace this with Alembic migrations.
    await initialize_database()
    yield


app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(router)
