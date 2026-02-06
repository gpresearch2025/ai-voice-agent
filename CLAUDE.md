# AI Voice Agent

## Overview
AI-powered phone agent prototype. Handles incoming calls via Twilio, uses Groq (Llama 3.3 70B) for conversation, and routes callers appropriately.

## Tech Stack
- **Python 3.10+** / **FastAPI** / **uvicorn**
- **Groq** (Llama 3.3 70B) — AI brain (free tier)
- **Twilio** — telephony (trial account)
- **aiosqlite** — call logging
- **pydantic-settings** — config from `.env`

## Project Structure
```
ai-voice-agent/
├── main.py              # FastAPI entry point, lifespan, routers
├── config.py            # Pydantic settings from .env
├── models.py            # CallRecord, CallStatus, ConfigUpdate
├── database.py          # Async SQLite CRUD (aiosqlite)
├── routes/
│   ├── voice.py         # 4 Twilio webhook endpoints
│   └── api.py           # 6 REST API endpoints
├── services/
│   ├── agent.py         # Groq AI + sales intent detection
│   ├── call_manager.py  # In-memory conversation state
│   └── hours.py         # Business hours checking (timezone-aware)
├── requirements.txt
├── .env                 # API keys (DO NOT commit)
└── calls.db             # SQLite database (auto-created)
```

## Running
```bash
pip install -r requirements.txt
python main.py  # Starts on port 8001
```
Requires ngrok for Twilio webhooks: `ngrok http 8001`

## Key Configuration (.env)
- `GROQ_API_KEY` — from console.groq.com (free)
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- `SALES_PHONE_NUMBER` — must include country code (+1...)
- `BUSINESS_HOURS_START/END` — 24h format (e.g. 09:00, 17:00)
- `BUSINESS_TIMEZONE` — e.g. America/Chicago
- `PORT` — default 8001 (8000 conflicts with Laragon)

## API Endpoints
- `GET /api/health` — system health + Groq connectivity
- `GET /api/calls` — paginated call logs with transcripts
- `GET /api/calls/active` — currently active calls
- `GET /api/calls/{call_sid}` — single call detail
- `GET /api/config` — current configuration
- `PUT /api/config` — update business hours, transfer numbers at runtime
- `GET /docs` — Swagger UI

## Call Flow
1. **Normal call:** Twilio → `/voice/incoming` → check hours → greeting → `/voice/respond` loop (Groq generates replies)
2. **After hours:** `/voice/incoming` → hours check fails → closed message → `<Record>` voicemail
3. **Sales transfer:** caller mentions pricing/sales → Groq returns `[TRANSFER_SALES]` prefix (or keyword fallback detects intent) → `<Dial>` to sales number
4. **Server down:** Twilio falls back to TwiML Bin (static XML)

## Sales Transfer Detection
Two-layer detection in `services/agent.py`:
1. **Prefix-based:** System prompt instructs Groq to prefix with `[TRANSFER_SALES]`
2. **Keyword fallback:** Regex catches phrases like "transfer you", "connect you with sales" if AI forgets the prefix

## Important Notes
- **Port 8000 is used by Laragon** — this project runs on port 8001
- **Twilio trial** can only `<Dial>` to Verified Caller IDs (console.twilio.com → Verified Caller IDs)
- **ngrok free tier** changes URLs on restart — must update Twilio webhooks each time
- `.env` changes require server restart (auto-reload only catches .py file changes)
- **Delete `__pycache__` folders** if code changes aren't reflected after restart
- Sales phone number must include country code: `+18326963009` not `+8326963009`

## Twilio Webhook Config
- A call comes in: `https://<ngrok-url>/voice/incoming` (POST)
- Call status changes: `https://<ngrok-url>/voice/status` (POST)
- Primary handler fails (optional): TwiML Bin with fallback message
