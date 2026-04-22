from __future__ import annotations

import logging

from aiogram import Bot

logger = logging.getLogger(__name__)


def create_telegram_bot(token: str | None) -> Bot | None:
    if not token:
        return None
    return Bot(token=token)


def format_cancellation_message(message_text: str) -> str:
    return f"❌ {message_text}"


async def send_cancellation_notification(bot: Bot | None, chat_id: str, message_text: str) -> None:
    if bot is None:
        return

    try:
        await bot.send_message(chat_id=chat_id, text=format_cancellation_message(message_text))
    except Exception:
        logger.exception("Failed to send cancellation notification", extra={"uid_chat_id": chat_id})
