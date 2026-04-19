from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TransactionCreate(BaseModel):
    client_key: str
    device_id: str
    uid: str
    message_text: str
    is_canceled: bool
    amount: int


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_key: str
    device_id: str
    uid: str
    message_text: str
    time: datetime
    is_canceled: bool
    amount: int


class UidAmountSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    amount: int
