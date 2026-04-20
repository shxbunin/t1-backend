from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Transaction, UidAmountSetting
from ..schemas import TransactionCreate, TransactionRead, UidAmountSettingRead

router = APIRouter()


@router.post("/transactions", response_model=TransactionRead)
def create_transaction(
    payload: TransactionCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> Transaction:
    existing = db.scalar(select(Transaction).where(Transaction.client_key == payload.client_key))
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    transaction = Transaction(
        client_key=payload.client_key,
        device_id=payload.device_id,
        uid=payload.uid,
        phone=payload.phone,
        message_text=payload.message_text,
        is_canceled=payload.is_canceled,
        amount=payload.amount,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    response.status_code = status.HTTP_201_CREATED
    return transaction


@router.get("/uid-settings/{uid}", response_model=UidAmountSettingRead)
def get_uid_setting(uid: str, db: Session = Depends(get_db)) -> UidAmountSetting:
    setting = db.scalar(select(UidAmountSetting).where(UidAmountSetting.uid == uid))
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UID setting not found")
    return setting
