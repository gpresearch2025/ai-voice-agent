import logging
from fastapi import APIRouter, HTTPException, Query
from groq import AsyncGroq

from config import settings
from models import ConfigUpdate
from database import get_calls, get_call, get_active_calls
from services.call_manager import call_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["REST API"])


@router.get("/health")
async def health_check():
    """System health check with connectivity status."""
    health = {
        "status": "healthy",
        "groq": "unknown",
        "twilio_configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
        "active_calls": len(call_manager.get_active_call_sids()),
    }

    # Check Groq connectivity
    try:
        client = AsyncGroq(api_key=settings.groq_api_key)
        await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        health["groq"] = "connected"
    except Exception as e:
        health["groq"] = f"error: {str(e)}"
        health["status"] = "degraded"

    return health


@router.get("/calls")
async def list_calls(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Paginated list of call records."""
    calls = await get_calls(limit=limit, offset=offset)
    return {
        "calls": [call.model_dump() for call in calls],
        "limit": limit,
        "offset": offset,
        "count": len(calls),
    }


@router.get("/calls/active")
async def list_active_calls():
    """Currently active calls."""
    calls = await get_active_calls()
    return {
        "active_calls": [call.model_dump() for call in calls],
        "count": len(calls),
    }


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
        "twilio_phone_number": settings.twilio_phone_number,
        "groq_key_set": bool(settings.groq_api_key),
        "twilio_configured": bool(settings.twilio_account_sid),
    }


@router.put("/config")
async def update_config(update: ConfigUpdate):
    """Update runtime configuration (business hours, transfer numbers)."""
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

    if not updated_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    logger.info(f"Config updated: {updated_fields}")
    return {"updated": updated_fields}
