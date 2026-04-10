import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.db import models  # noqa: F401
from app.db.database import Base, engine


logger = logging.getLogger(__name__)


async def initialize_database(max_attempts: int = 5, delay_seconds: int = 3) -> None:
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
    await initialize_database()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(router)
