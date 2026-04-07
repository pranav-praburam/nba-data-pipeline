from fastapi import FastAPI
from app.api.routes import router
from app.db.database import engine, Base
from app.db import models

app = FastAPI()

# create tables (will do nothing for now)
Base.metadata.create_all(bind=engine)

app.include_router(router)