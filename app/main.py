from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from .api.transactions import router as transactions_router
from .config import get_settings
from .db import Base, engine
from . import models  # noqa: F401
from .services.telegram import create_telegram_bot


def sync_schema() -> None:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS phone TEXT"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    sync_schema()
    app.state.telegram_bot = create_telegram_bot(get_settings().telegram_bot_token)
    try:
        yield
    finally:
        bot = app.state.telegram_bot
        if bot is not None:
            await bot.session.close()


app = FastAPI(title="Collega API", lifespan=lifespan)
app.include_router(transactions_router)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
