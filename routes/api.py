import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from groq import AsyncGroq

from config import settings
from models import ConfigUpdate
from database import get_calls, get_call, get_active_calls, count_calls, get_call_stats
from services.call_manager import call_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["REST API"])

# --- Health cache (avoid hammering Groq) ---
_health_cache: dict = {"result": None, "timestamp": 0}
HEALTH_CACHE_TTL = 60  # seconds


def _require_token(authorization: str | None = Header(None)):
    """Dependency: verify dashboard token on protected endpoints."""
    token = settings.dashboard_token
    if not token:
        return  # no token configured = open access
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    if authorization[7:] != token:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/health")
async def health_check():
    """System health check with cached Groq connectivity."""
    now = time.time()
    groq_result = None

    # Use cached Groq result if fresh
    if _health_cache["result"] and (now - _health_cache["timestamp"]) < HEALTH_CACHE_TTL:
        groq_result = _health_cache["result"]
    else:
        try:
            client = AsyncGroq(api_key=settings.groq_api_key)
            await client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            groq_result = "connected"
        except Exception as e:
            groq_result = f"error: {str(e)}"

        _health_cache["result"] = groq_result
        _health_cache["timestamp"] = now

    health = {
        "status": "healthy" if groq_result == "connected" else "degraded",
        "groq": groq_result,
        "twilio_configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
        "active_calls": len(call_manager.get_active_call_sids()),
    }

    return health


@router.get("/calls")
async def list_calls(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    search: str | None = Query(None),
):
    """Paginated list of call records with optional filters."""
    calls = await get_calls(limit=limit, offset=offset, status=status, search=search)
    total = await count_calls(status=status, search=search)
    return {
        "calls": [call.model_dump() for call in calls],
        "limit": limit,
        "offset": offset,
        "count": len(calls),
        "total": total,
    }


@router.get("/calls/active")
async def list_active_calls():
    """Currently active calls."""
    calls = await get_active_calls()
    return {
        "active_calls": [call.model_dump() for call in calls],
        "count": len(calls),
    }


@router.get("/calls/stats")
async def call_stats():
    """Summary statistics for the dashboard."""
    return await get_call_stats()


@router.get("/calls/{call_sid}")
async def get_call_detail(call_sid: str):
    """Single call detail by SID."""
    call = await get_call(call_sid)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call.model_dump()


@router.get("/config")
async def get_config():
    """Current system configuration (sensitive fields masked)."""
    return {
        "business_hours_start": settings.business_hours_start,
        "business_hours_end": settings.business_hours_end,
        "business_timezone": settings.business_timezone,
        "sales_phone_number": settings.sales_phone_number,
        "support_phone_number": settings.support_phone_number,
        "twilio_phone_number": settings.twilio_phone_number,
        "groq_key_set": bool(settings.groq_api_key),
        "twilio_configured": bool(settings.twilio_account_sid),
        "auth_required": bool(settings.dashboard_token),
    }


@router.put("/config")
async def update_config(
    update: ConfigUpdate,
    _=Depends(_require_token),
):
    """Update runtime configuration (protected by dashboard token)."""

    updated_fields = {}

    if update.business_hours_start is not None:
        settings.business_hours_start = update.business_hours_start
        updated_fields["business_hours_start"] = update.business_hours_start

    if update.business_hours_end is not None:
        settings.business_hours_end = update.business_hours_end
        updated_fields["business_hours_end"] = update.business_hours_end

    if update.business_timezone is not None:
        settings.business_timezone = update.business_timezone
        updated_fields["business_timezone"] = update.business_timezone

    if update.sales_phone_number is not None:
        settings.sales_phone_number = update.sales_phone_number
        updated_fields["sales_phone_number"] = update.sales_phone_number

    if update.support_phone_number is not None:
        settings.support_phone_number = update.support_phone_number
        updated_fields["support_phone_number"] = update.support_phone_number

    if not updated_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    logger.info(f"Config updated: {updated_fields}")
    return {"updated": updated_fields}
