from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class CallStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    VOICEMAIL = "voicemail"
    TRANSFERRED = "transferred"


class CallRecord(BaseModel):
    call_sid: str
    from_number: str
    to_number: str
    status: CallStatus = CallStatus.ACTIVE
    started_at: str = ""
    ended_at: str | None = None
    transcript: list[dict] = []
    voicemail_url: str | None = None
    transferred_to: str | None = None

    def to_db_row(self) -> tuple:
        import json
        return (
            self.call_sid,
            self.from_number,
            self.to_number,
            self.status.value,
            self.started_at or datetime.utcnow().isoformat(),
            self.ended_at,
            json.dumps(self.transcript),
            self.voicemail_url,
            self.transferred_to,
        )


class ConversationTurn(BaseModel):
    role: str  # "caller" or "assistant"
    content: str
    timestamp: str = ""


class ConfigUpdate(BaseModel):
    business_hours_start: str | None = None
    business_hours_end: str | None = None
    business_timezone: str | None = None
    sales_phone_number: str | None = None
