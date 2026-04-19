from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.transactions import router as transactions_router
from .db import Base, engine
from . import models  # noqa: F401


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Collega API", lifespan=lifespan)
app.include_router(transactions_router)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
