from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from .api.transactions import router as transactions_router
from .config import get_settings
from .db import Base, engine
from . import models  # noqa: F401
from .services.daily_report import run_daily_report_scheduler
from .services.telegram import create_telegram_bot, create_telegram_dispatcher

logger = logging.getLogger(__name__)


def sync_schema() -> None:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS phone TEXT"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    sync_schema()
    app.state.telegram_bot = create_telegram_bot(get_settings().telegram_bot_token)
    app.state.telegram_dispatcher = None
    app.state.telegram_polling_task = None
    app.state.daily_report_task = None

    if app.state.telegram_bot is not None:
        dispatcher = create_telegram_dispatcher()
        app.state.telegram_dispatcher = dispatcher
        app.state.telegram_polling_task = asyncio.create_task(
            dispatcher.start_polling(
                app.state.telegram_bot,
                handle_signals=False,
                close_bot_session=False,
            )
        )
        app.state.daily_report_task = asyncio.create_task(run_daily_report_scheduler(app.state.telegram_bot))

    try:
        yield
    finally:
        dispatcher = app.state.telegram_dispatcher
        polling_task = app.state.telegram_polling_task
        daily_report_task = app.state.daily_report_task

        if daily_report_task is not None and not daily_report_task.done():
            daily_report_task.cancel()

        if dispatcher is not None and polling_task is not None and not polling_task.done():
            try:
                await dispatcher.stop_polling()
            except RuntimeError:
                polling_task.cancel()

        if daily_report_task is not None:
            try:
                await daily_report_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Daily report scheduler stopped with error")

        if polling_task is not None:
            try:
                await polling_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Telegram polling stopped with error")

        bot = app.state.telegram_bot
        if bot is not None:
            await bot.session.close()


app = FastAPI(title="Collega API", lifespan=lifespan)
app.include_router(transactions_router)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
