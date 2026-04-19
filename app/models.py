from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Identity, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(start=1), primary_key=True)
    client_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    device_id: Mapped[str] = mapped_column(Text, nullable=False)
    uid: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_canceled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)


class UidAmountSetting(Base):
    __tablename__ = "uid_amount_settings"

    uid: Mapped[str] = mapped_column(Text, primary_key=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
