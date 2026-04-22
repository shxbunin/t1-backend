from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ReactionTypeEmoji
from sqlalchemy import select

from ..db import SessionLocal
from ..models import UidAmountSetting, UidTelegramChat

logger = logging.getLogger(__name__)

telegram_router = Router()


def create_telegram_bot(token: str | None) -> Bot | None:
    if not token:
        return None
    return Bot(token=token)


def create_telegram_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(telegram_router)
    return dispatcher


def format_cancellation_message(message_text: str, phone: str | None) -> str:
    if not phone:
        return f"❌ {message_text}"
    return f"❌ {phone} {message_text}"


def set_uid_amount_for_chat(chat_id: str, amount: int) -> str | None:
    with SessionLocal() as db:
        chat = db.scalar(select(UidTelegramChat).where(UidTelegramChat.chat_id == chat_id))
        if chat is None:
            return None

        setting = db.scalar(select(UidAmountSetting).where(UidAmountSetting.uid == chat.uid))
        if setting is None:
            db.add(UidAmountSetting(uid=chat.uid, amount=amount))
        else:
            setting.amount = amount

        db.commit()
        return chat.uid


async def set_uid_amount_for_chat_async(chat_id: str, amount: int) -> str | None:
    return await asyncio.to_thread(set_uid_amount_for_chat, chat_id, amount)


async def add_success_reaction(message: Message) -> None:
    await message.bot.set_message_reaction(
        chat_id=message.chat.id,
        message_id=message.message_id,
        reaction=[ReactionTypeEmoji(emoji="👍")],
    )


@telegram_router.message(Command("sum", ignore_case=True, ignore_mention=True))
async def handle_sum_command(message: Message, command: CommandObject) -> None:
    if message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return

    if command.args is None:
        await message.answer("Использование: /sum 5000")
        return

    try:
        amount = int(command.args.strip())
    except ValueError:
        await message.answer("Использование: /sum 5000")
        return

    if amount < 0:
        return

    try:
        uid = await set_uid_amount_for_chat_async(str(message.chat.id), amount)
    except Exception:
        logger.exception("Failed to set uid amount from Telegram command", extra={"chat_id": message.chat.id})
        return

    if uid is None:
        await message.answer("Чат не привязан")
        return

    try:
        await add_success_reaction(message)
    except Exception:
        logger.exception(
            "Failed to add success reaction for Telegram command",
            extra={"chat_id": message.chat.id, "uid": uid},
        )


async def send_cancellation_notification(
    bot: Bot | None,
    chat_id: str,
    message_text: str,
    phone: str | None,
) -> None:
    if bot is None:
        return

    try:
        await bot.send_message(chat_id=chat_id, text=format_cancellation_message(message_text, phone))
    except Exception:
        logger.exception("Failed to send cancellation notification", extra={"uid_chat_id": chat_id})
