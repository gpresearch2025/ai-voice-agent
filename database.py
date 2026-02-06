import json
import aiosqlite
from models import CallRecord, CallStatus
from config import settings

DB_PATH = settings.database_path


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                call_sid TEXT PRIMARY KEY,
                from_number TEXT NOT NULL,
                to_number TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                started_at TEXT NOT NULL,
                ended_at TEXT,
                transcript TEXT DEFAULT '[]',
                voicemail_url TEXT,
                transferred_to TEXT
            )
        """)
        await db.commit()


async def save_call(record: CallRecord):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO calls
               (call_sid, from_number, to_number, status, started_at, ended_at,
                transcript, voicemail_url, transferred_to)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            record.to_db_row(),
        )
        await db.commit()


async def get_call(call_sid: str) -> CallRecord | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM calls WHERE call_sid = ?", (call_sid,))
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_record(row)


async def get_calls(limit: int = 50, offset: int = 0) -> list[CallRecord]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM calls ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_record(row) for row in rows]


async def get_active_calls() -> list[CallRecord]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM calls WHERE status = ?", (CallStatus.ACTIVE.value,)
        )
        rows = await cursor.fetchall()
        return [_row_to_record(row) for row in rows]


async def update_call_status(call_sid: str, status: CallStatus, ended_at: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if ended_at:
            await db.execute(
                "UPDATE calls SET status = ?, ended_at = ? WHERE call_sid = ?",
                (status.value, ended_at, call_sid),
            )
        else:
            await db.execute(
                "UPDATE calls SET status = ? WHERE call_sid = ?",
                (status.value, call_sid),
            )
        await db.commit()


async def update_call_transcript(call_sid: str, transcript: list[dict]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE calls SET transcript = ? WHERE call_sid = ?",
            (json.dumps(transcript), call_sid),
        )
        await db.commit()


async def update_call_voicemail(call_sid: str, voicemail_url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE calls SET voicemail_url = ?, status = ? WHERE call_sid = ?",
            (voicemail_url, CallStatus.VOICEMAIL.value, call_sid),
        )
        await db.commit()


def _row_to_record(row) -> CallRecord:
    return CallRecord(
        call_sid=row["call_sid"],
        from_number=row["from_number"],
        to_number=row["to_number"],
        status=CallStatus(row["status"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        transcript=json.loads(row["transcript"]) if row["transcript"] else [],
        voicemail_url=row["voicemail_url"],
        transferred_to=row["transferred_to"],
    )
