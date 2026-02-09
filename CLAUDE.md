# AI Voice Agent

## Overview
AI-powered phone agent prototype. Handles incoming calls via Twilio, uses Groq (Llama 3.3 70B) for conversation, and routes callers appropriately.

## Deployment
- **Production:** https://ai-voice-agent-a4bq.onrender.com (Render, free tier)
- **GitHub:** https://github.com/gpresearch2025/ai-voice-agent (public)
- **Local dev:** `python main.py` → http://localhost:8001

## Tech Stack
- **Python 3.13** / **FastAPI** / **uvicorn**
- **Groq** (Llama 3.3 70B) — AI brain (free tier)
- **Twilio** — telephony (trial account, number: +18555380806)
- **asyncpg** — call logging (Neon PostgreSQL)
- **pydantic-settings** — config from `.env`

## Project Structure
```
ai-voice-agent/
├── main.py              # FastAPI entry point, lifespan, routers, static mount
├── config.py            # Pydantic settings from .env
├── models.py            # CallRecord, CallStatus, ConfigUpdate
├── database.py          # Async PostgreSQL CRUD (asyncpg/Neon) with search/filter
├── routes/
│   ├── voice.py         # 4 Twilio webhook endpoints
│   └── api.py           # 6 REST API endpoints (health cached, auth on config)
├── services/
│   ├── agent.py         # Groq AI + sales intent detection
│   ├── call_manager.py  # In-memory conversation state
│   └── hours.py         # Business hours checking (timezone-aware)
├── static/
│   ├── index.html       # Dashboard page (single-page, no framework)
│   ├── style.css        # Dark theme styles
│   └── app.js           # Fetch API data, render UI, auto-refresh
├── render.yaml          # Render deployment blueprint
├── requirements.txt
└── .env                 # API keys + DATABASE_URL (DO NOT commit)
```

## Running Locally
```bash
pip install -r requirements.txt
python main.py  # Starts on port 8001
```
For local testing with Twilio: `ngrok http 8001`

## Key Configuration (.env)
- `GROQ_API_KEY` — from console.groq.com (free)
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- `SALES_PHONE_NUMBER` — must include country code (+1...)
- `BUSINESS_HOURS_START/END` — 24h format (e.g. 09:00, 17:00)
- `BUSINESS_TIMEZONE` — e.g. America/Chicago
- `DASHBOARD_TOKEN` — protects `PUT /api/config` (leave empty for open access)
- `DATABASE_URL` — Neon PostgreSQL connection string (`postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`)
- `PORT` — default 8001 (8000 conflicts with Laragon)

## API Endpoints
- `GET /api/health` — system health + Groq connectivity (cached 60s)
- `GET /api/calls?limit=&offset=&status=&search=` — paginated call logs with filtering
- `GET /api/calls/active` — currently active calls
- `GET /api/calls/{call_sid}` — single call detail with transcript
- `GET /api/config` — current configuration (includes `auth_required` flag)
- `PUT /api/config` — update business hours, transfer numbers (requires `DASHBOARD_TOKEN` if set)
- `GET /docs` — Swagger UI

## Web Dashboard
- **URL:** `/` redirects to `/dashboard/` (served as static files from `static/`)
- **Sections:** system status, config editor, call log table, transcript viewer modal
- **Features:**
  - Auto-refresh: health every 10s, calls every 15s
  - Search by phone number, filter by call status
  - Live elapsed timer for active calls (pulsing blue dot)
  - "Last updated" timestamp in header
  - Auth modal prompts for token on config save (if `DASHBOARD_TOKEN` is set)
  - All user data escaped to prevent XSS
- **Tech:** Plain HTML/CSS/JS, no framework, dark theme (#1a1a2e background, #0f9d8c teal accent)

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
- **ngrok free tier** changes URLs on restart — must update Twilio webhooks each time (not needed with Render)
- `.env` changes require server restart (auto-reload only catches .py file changes)
- **Delete `__pycache__` folders** if code changes aren't reflected after restart
- Sales phone number must include country code: `+18326963009` not `+8326963009`
- **Render free tier** has cold starts (~30s) if the service hasn't been called recently
- **Database** is Neon PostgreSQL (free tier) — call logs persist across Render deploys

## Twilio Webhook Config (Production)
- A call comes in: `https://ai-voice-agent-a4bq.onrender.com/voice/incoming` (POST)
- Call status changes: `https://ai-voice-agent-a4bq.onrender.com/voice/status` (POST)
- Primary handler fails (optional): TwiML Bin with fallback message

## TODO: Next Tasks
- [x] ~~Build web dashboard~~ — done (plain HTML/CSS/JS served from FastAPI)
- [ ] Set up TwiML Bin fallback for server-down scenario
- [ ] Test after-hours voicemail flow
- [x] ~~Upgrade to persistent database (PostgreSQL) for Render~~ — done (Neon free tier, asyncpg)
- [ ] Add more natural TTS voice (ElevenLabs or Deepgram)
- [ ] Add dashboard auth for read endpoints (currently only config PUT is protected)
