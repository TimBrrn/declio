from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, func, select

from backend.src.api.dependencies import get_db_session
from backend.src.api.middleware.auth import get_current_user
from backend.src.domain.value_objects.token_usage import USD_TO_EUR
from backend.src.infrastructure.persistence.models import CallRecordModel

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/summary")
def usage_summary(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
    _user: dict = Depends(get_current_user),
):
    """Aggregated cost summary across all calls."""
    statement = select(CallRecordModel)
    if date_from:
        statement = statement.where(
            CallRecordModel.started_at >= datetime.fromisoformat(date_from)
        )
    if date_to:
        statement = statement.where(
            CallRecordModel.started_at <= datetime.fromisoformat(date_to)
        )

    calls = session.exec(statement).all()
    total_calls = len(calls)

    if total_calls == 0:
        return {
            "total_calls": 0,
            "total_cost_eur": 0.0,
            "avg_cost_per_call_eur": 0.0,
            "llm_cost_total_eur": 0.0,
            "stt_cost_total_eur": 0.0,
            "tts_cost_total_eur": 0.0,
            "total_tokens": 0,
            "avg_tokens_per_call": 0,
        }

    total_cost_usd = sum(c.total_cost_usd for c in calls)
    llm_total = sum(c.llm_cost_usd for c in calls)
    stt_total = sum(c.stt_cost_usd for c in calls)
    tts_total = sum(c.tts_cost_usd for c in calls)
    total_tokens = sum(c.total_tokens for c in calls)

    return {
        "total_calls": total_calls,
        "total_cost_eur": round(total_cost_usd * USD_TO_EUR, 4),
        "avg_cost_per_call_eur": round(total_cost_usd * USD_TO_EUR / total_calls, 4),
        "llm_cost_total_eur": round(llm_total * USD_TO_EUR, 4),
        "stt_cost_total_eur": round(stt_total * USD_TO_EUR, 4),
        "tts_cost_total_eur": round(tts_total * USD_TO_EUR, 4),
        "total_tokens": total_tokens,
        "avg_tokens_per_call": total_tokens // total_calls if total_calls else 0,
    }
