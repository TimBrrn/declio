from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from backend.src.api.dependencies import get_db_session
# from backend.src.api.middleware.auth import get_current_user  # TODO: réactiver après PoC
from backend.src.infrastructure.persistence.models import ApiUsageModel, CallRecordModel

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("/")
def list_calls(
    cabinet_id: str | None = Query(default=None),
    scenario: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
):
    statement = select(CallRecordModel)
    if cabinet_id:
        statement = statement.where(CallRecordModel.cabinet_id == cabinet_id)
    if scenario:
        statement = statement.where(CallRecordModel.scenario == scenario)
    if date_from:
        dt_from = datetime.fromisoformat(date_from)
        statement = statement.where(CallRecordModel.started_at >= dt_from)
    if date_to:
        dt_to = datetime.fromisoformat(date_to)
        statement = statement.where(CallRecordModel.started_at <= dt_to)
    statement = statement.order_by(CallRecordModel.started_at.desc())
    calls = session.exec(statement).all()
    return calls


@router.get("/{call_id}/usage")
def call_usage(
    call_id: str,
    session: Session = Depends(get_db_session),
):
    """Return per-turn API usage breakdown for a specific call."""
    statement = (
        select(ApiUsageModel)
        .where(ApiUsageModel.call_record_id == call_id)
        .order_by(ApiUsageModel.service, ApiUsageModel.turn_index)
    )
    rows = session.exec(statement).all()
    return rows
