import json
from datetime import datetime, timezone
import asyncpg
from models import CallRecord, CallStatus


def _parse_dt(value: str | None) -> datetime | None:
    """Convert ISO string to datetime for asyncpg TIMESTAMPTZ columns."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)

# Module-level pool, set during app startup
_pool: asyncpg.Pool | None = None


async def init_db(pool: asyncpg.Pool):
    global _pool
    _pool = pool
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                call_sid VARCHAR(64) PRIMARY KEY,
                from_number VARCHAR(20) NOT NULL,
                to_number VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                started_at TIMESTAMPTZ NOT NULL,
                ended_at TIMESTAMPTZ,
                transcript JSONB DEFAULT '[]'::jsonb,
                voicemail_url TEXT,
                transferred_to VARCHAR(20)
            )
        """)


async def save_call(record: CallRecord):
    row = record.to_db_row()
    # Convert ISO strings to datetime objects for TIMESTAMPTZ columns
    row_list = list(row)
    row_list[4] = _parse_dt(row_list[4])  # started_at
    row_list[5] = _parse_dt(row_list[5])  # ended_at
    await _pool.execute(
        """INSERT INTO calls
           (call_sid, from_number, to_number, status, started_at, ended_at,
            transcript, voicemail_url, transferred_to)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
           ON CONFLICT (call_sid) DO UPDATE SET
            from_number = EXCLUDED.from_number,
            to_number = EXCLUDED.to_number,
            status = EXCLUDED.status,
            started_at = EXCLUDED.started_at,
            ended_at = EXCLUDED.ended_at,
            transcript = EXCLUDED.transcript,
            voicemail_url = EXCLUDED.voicemail_url,
            transferred_to = EXCLUDED.transferred_to""",
        *row_list,
    )


async def get_call(call_sid: str) -> CallRecord | None:
    row = await _pool.fetchrow("SELECT * FROM calls WHERE call_sid = $1", call_sid)
    if not row:
        return None
    return _row_to_record(row)


async def get_calls(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    search: str | None = None,
) -> list[CallRecord]:
    query = "SELECT * FROM calls"
    params: list = []
    conditions = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if search:
        conditions.append(f"from_number LIKE ${idx}")
        params.append(f"%{search}%")
        idx += 1

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += f" ORDER BY started_at DESC LIMIT ${idx} OFFSET ${idx + 1}"
    params.extend([limit, offset])

    rows = await _pool.fetch(query, *params)
    return [_row_to_record(row) for row in rows]


async def count_calls(
    status: str | None = None,
    search: str | None = None,
) -> int:
    query = "SELECT COUNT(*) FROM calls"
    params: list = []
    conditions = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if search:
        conditions.append(f"from_number LIKE ${idx}")
        params.append(f"%{search}%")
        idx += 1

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    return await _pool.fetchval(query, *params)


async def get_call_stats() -> dict:
    """Get summary stats for the dashboard."""
    rows = await _pool.fetch("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE started_at::date = CURRENT_DATE) AS today,
            COUNT(*) FILTER (WHERE status = 'transferred') AS transferred,
            COUNT(*) FILTER (WHERE status = 'voicemail') AS voicemail,
            AVG(EXTRACT(EPOCH FROM (ended_at - started_at)))
                FILTER (WHERE ended_at IS NOT NULL AND started_at IS NOT NULL) AS avg_duration
        FROM calls
    """)
    row = rows[0]
    return {
        "total_calls": row["total"],
        "today_calls": row["today"],
        "transferred": row["transferred"],
        "voicemail": row["voicemail"],
        "avg_duration_seconds": round(row["avg_duration"] or 0),
    }


async def get_active_calls() -> list[CallRecord]:
    rows = await _pool.fetch(
        "SELECT * FROM calls WHERE status = $1", CallStatus.ACTIVE.value
    )
    return [_row_to_record(row) for row in rows]


async def update_call_status(call_sid: str, status: CallStatus, ended_at: str | None = None):
    if ended_at:
        await _pool.execute(
            "UPDATE calls SET status = $1, ended_at = $2 WHERE call_sid = $3",
            status.value, _parse_dt(ended_at), call_sid,
        )
    else:
        await _pool.execute(
            "UPDATE calls SET status = $1 WHERE call_sid = $2",
            status.value, call_sid,
        )


async def update_call_transcript(call_sid: str, transcript: list[dict]):
    await _pool.execute(
        "UPDATE calls SET transcript = $1 WHERE call_sid = $2",
        json.dumps(transcript), call_sid,
    )


async def update_call_transferred_to(call_sid: str, transferred_to: str):
    await _pool.execute(
        "UPDATE calls SET transferred_to = $1 WHERE call_sid = $2",
        transferred_to, call_sid,
    )


async def close_stale_calls(max_age_minutes: int = 15) -> int:
    """Auto-close calls stuck as 'active' longer than max_age_minutes.
    Returns the number of calls closed."""
    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(minutes=max_age_minutes)
    result = await _pool.execute(
        "UPDATE calls SET status = $1, ended_at = $2 WHERE status = $3 AND started_at < $4",
        CallStatus.COMPLETED.value, datetime.now(timezone.utc), CallStatus.ACTIVE.value, cutoff,
    )
    # result looks like "UPDATE 3"
    count = int(result.split()[-1])
    return count


async def update_call_voicemail(call_sid: str, voicemail_url: str):
    await _pool.execute(
        "UPDATE calls SET voicemail_url = $1, status = $2 WHERE call_sid = $3",
        voicemail_url, CallStatus.VOICEMAIL.value, call_sid,
    )


def _row_to_record(row) -> CallRecord:
    transcript = row["transcript"]
    if isinstance(transcript, str):
        transcript = json.loads(transcript)

    started_at = row["started_at"]
    if hasattr(started_at, "isoformat"):
        started_at = started_at.isoformat()

    ended_at = row["ended_at"]
    if hasattr(ended_at, "isoformat"):
        ended_at = ended_at.isoformat()

    return CallRecord(
        call_sid=row["call_sid"],
        from_number=row["from_number"],
        to_number=row["to_number"],
        status=CallStatus(row["status"]),
        started_at=started_at,
        ended_at=ended_at,
        transcript=transcript,
        voicemail_url=row["voicemail_url"],
        transferred_to=row["transferred_to"],
    )
