from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.enums import ParseMode
from sqlalchemy import case, func, select

from ..db import SessionLocal
from ..models import Transaction, UidTelegramChat

logger = logging.getLogger(__name__)

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


@dataclass(frozen=True)
class ReportPeriod:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class PhoneStats:
    phone: str | None
    canceled_count: int
    succeeded_count: int
    canceled_amount: int


@dataclass(frozen=True)
class UidStats:
    canceled_count: int
    succeeded_count: int
    canceled_amount: int


@dataclass(frozen=True)
class DailyReportMessage:
    uid: str
    chat_id: str
    text: str


@dataclass
class UidReportAccumulator:
    chat_id: str
    phone_stats: list[PhoneStats]
    totals: UidStats


def get_next_moscow_midnight(now: datetime | None = None) -> datetime:
    current = (now or datetime.now(MOSCOW_TZ)).astimezone(MOSCOW_TZ)
    return datetime.combine(current.date() + timedelta(days=1), time.min, tzinfo=MOSCOW_TZ)


def get_completed_moscow_day_period(reference: datetime | None = None) -> ReportPeriod:
    current = (reference or datetime.now(MOSCOW_TZ)).astimezone(MOSCOW_TZ)
    end = datetime.combine(current.date(), time.min, tzinfo=MOSCOW_TZ)
    return ReportPeriod(start=end - timedelta(days=1), end=end)


def get_current_moscow_day_period(reference: datetime | None = None) -> ReportPeriod:
    current = (reference or datetime.now(MOSCOW_TZ)).astimezone(MOSCOW_TZ)
    start = datetime.combine(current.date(), time.min, tzinfo=MOSCOW_TZ)
    return ReportPeriod(start=start, end=current)


def calculate_cancel_percentage(canceled_count: int, succeeded_count: int) -> str:
    total_count = canceled_count + succeeded_count
    if total_count == 0:
        return "0.00%"
    return f"{(canceled_count / total_count) * 100:.2f}%"


def format_report_title(period: ReportPeriod) -> str:
    start = period.start.astimezone(MOSCOW_TZ)
    end = period.end.astimezone(MOSCOW_TZ)

    if end.time() == time.min and end.date() == start.date() + timedelta(days=1):
        return f"Отчет за {start:%d.%m.%Y} (МСК)"

    return f"Отчет за {start:%d.%m.%Y} с {start:%H:%M} до {end:%H:%M} (МСК)"


def calculate_total_stats(phone_stats: list[PhoneStats]) -> UidStats:
    return UidStats(
        canceled_count=sum(item.canceled_count for item in phone_stats),
        succeeded_count=sum(item.succeeded_count for item in phone_stats),
        canceled_amount=sum(item.canceled_amount for item in phone_stats),
    )


def build_uid_daily_report(uid: str, period: ReportPeriod, phone_stats: list[PhoneStats], total_stats: UidStats) -> str:
    lines = [
        format_report_title(period),
        f"UID: <b>{escape(uid)}</b>",
        "",
    ]

    for stats in sorted(phone_stats, key=lambda item: (item.phone is None, item.phone or "")):
        phone_label = stats.phone or "Без номера"
        lines.extend(
            [
                f"<b>{escape(phone_label)}</b>",
                f"❌ Отмен: {stats.canceled_count}",
                f"✅ Прошедших: {stats.succeeded_count}",
                f"Сумма отмен: {stats.canceled_amount}",
                f"% отмен: {calculate_cancel_percentage(stats.canceled_count, stats.succeeded_count)}",
                "",
            ]
        )

    lines.extend(
        [
            "<b>Итого по UID</b>",
            f"❌ Отмен: {total_stats.canceled_count}",
            f"✅ Прошедших: {total_stats.succeeded_count}",
            f"Сумма отмен: {total_stats.canceled_amount}",
            f"% отмен: {calculate_cancel_percentage(total_stats.canceled_count, total_stats.succeeded_count)}",
        ]
    )

    return "\n".join(lines)


def build_uid_daily_report_message(
    uid: str,
    chat_id: str,
    period: ReportPeriod,
    phone_stats: list[PhoneStats],
    total_stats: UidStats | None = None,
) -> DailyReportMessage | None:
    if not phone_stats:
        return None

    if total_stats is None:
        total_stats = calculate_total_stats(phone_stats)

    return DailyReportMessage(
        uid=uid,
        chat_id=chat_id,
        text=build_uid_daily_report(
            uid=uid,
            period=period,
            phone_stats=phone_stats,
            total_stats=total_stats,
        ),
    )


def build_phone_stats_for_uid(uid: str, period: ReportPeriod) -> list[PhoneStats]:
    canceled_count = func.sum(case((Transaction.is_canceled.is_(True), 1), else_=0)).label("canceled_count")
    succeeded_count = func.sum(case((Transaction.is_canceled.is_(False), 1), else_=0)).label("succeeded_count")
    canceled_amount = func.coalesce(
        func.sum(case((Transaction.is_canceled.is_(True), Transaction.amount), else_=0)),
        0,
    ).label("canceled_amount")

    statement = (
        select(
            Transaction.phone.label("phone"),
            canceled_count,
            succeeded_count,
            canceled_amount,
        )
        .where(Transaction.uid == uid, Transaction.time >= period.start, Transaction.time < period.end)
        .group_by(Transaction.phone)
        .order_by(Transaction.phone)
    )

    with SessionLocal() as db:
        rows = db.execute(statement).all()

    return [
        PhoneStats(
            phone=row.phone,
            canceled_count=int(row.canceled_count or 0),
            succeeded_count=int(row.succeeded_count or 0),
            canceled_amount=int(row.canceled_amount or 0),
        )
        for row in rows
    ]


def collect_uid_daily_report_message(uid: str, chat_id: str, period: ReportPeriod) -> DailyReportMessage | None:
    phone_stats = build_phone_stats_for_uid(uid, period)
    return build_uid_daily_report_message(uid=uid, chat_id=chat_id, period=period, phone_stats=phone_stats)


def collect_daily_report_messages(period: ReportPeriod) -> list[DailyReportMessage]:
    canceled_count = func.sum(case((Transaction.is_canceled.is_(True), 1), else_=0)).label("canceled_count")
    succeeded_count = func.sum(case((Transaction.is_canceled.is_(False), 1), else_=0)).label("succeeded_count")
    canceled_amount = func.coalesce(
        func.sum(case((Transaction.is_canceled.is_(True), Transaction.amount), else_=0)),
        0,
    ).label("canceled_amount")

    statement = (
        select(
            UidTelegramChat.uid.label("uid"),
            UidTelegramChat.chat_id.label("chat_id"),
            Transaction.phone.label("phone"),
            canceled_count,
            succeeded_count,
            canceled_amount,
        )
        .join(Transaction, Transaction.uid == UidTelegramChat.uid)
        .where(Transaction.time >= period.start, Transaction.time < period.end)
        .group_by(UidTelegramChat.uid, UidTelegramChat.chat_id, Transaction.phone)
        .order_by(UidTelegramChat.uid, Transaction.phone)
    )

    with SessionLocal() as db:
        rows = db.execute(statement).all()

    grouped: dict[str, UidReportAccumulator] = {}

    for row in rows:
        uid = str(row.uid)
        report = grouped.get(uid)
        if report is None:
            report = UidReportAccumulator(
                chat_id=str(row.chat_id),
                phone_stats=[],
                totals=UidStats(canceled_count=0, succeeded_count=0, canceled_amount=0),
            )
            grouped[uid] = report

        stats = PhoneStats(
            phone=row.phone,
            canceled_count=int(row.canceled_count or 0),
            succeeded_count=int(row.succeeded_count or 0),
            canceled_amount=int(row.canceled_amount or 0),
        )
        total_stats = report.totals

        report.phone_stats.append(stats)
        report.totals = UidStats(
            canceled_count=total_stats.canceled_count + stats.canceled_count,
            succeeded_count=total_stats.succeeded_count + stats.succeeded_count,
            canceled_amount=total_stats.canceled_amount + stats.canceled_amount,
        )

    messages: list[DailyReportMessage] = []
    for uid, report in grouped.items():
        message = build_uid_daily_report_message(
            uid=uid,
            chat_id=report.chat_id,
            period=period,
            phone_stats=report.phone_stats,
            total_stats=report.totals,
        )
        if message is not None:
            messages.append(message)

    return messages


async def send_daily_reports(bot: Bot | None, period: ReportPeriod) -> None:
    if bot is None:
        return

    messages = await asyncio.to_thread(collect_daily_report_messages, period)
    for message in messages:
        try:
            await bot.send_message(chat_id=message.chat_id, text=message.text, parse_mode=ParseMode.HTML)
        except Exception:
            logger.exception("Failed to send daily report", extra={"uid": message.uid, "uid_chat_id": message.chat_id})


async def run_daily_report_scheduler(bot: Bot | None) -> None:
    if bot is None:
        return

    while True:
        next_run = get_next_moscow_midnight()
        sleep_for = max((next_run - datetime.now(MOSCOW_TZ)).total_seconds(), 0.0)
        await asyncio.sleep(sleep_for)

        period = get_completed_moscow_day_period(next_run)
        try:
            await send_daily_reports(bot, period)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Daily report scheduler iteration failed",
                extra={"report_period_start": period.start.isoformat(), "report_period_end": period.end.isoformat()},
            )
