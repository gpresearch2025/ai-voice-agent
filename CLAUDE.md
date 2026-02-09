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
├── main.py              # FastAPI entry point, lifespan, routers, stale call cleanup task
├── config.py            # Pydantic settings from .env
├── models.py            # CallRecord, CallStatus, ConfigUpdate
├── database.py          # Async PostgreSQL CRUD (asyncpg/Neon), stale call cleanup
├── routes/
│   ├── voice.py         # 5 Twilio webhook endpoints (incoming, respond, transfer, voicemail, status)
│   └── api.py           # 7 REST API endpoints (health cached, stats, auth on config)
├── services/
│   ├── agent.py         # Groq AI + sales/support transfer detection
│   ├── call_manager.py  # In-memory conversation state
│   └── hours.py         # Business hours checking (timezone-aware)
├── static/
│   ├── index.html       # Dashboard page (single-page, no framework)
│   ├── style.css        # CSS custom properties for light/dark themes
│   └── app.js           # Dashboard logic: stats, theme toggle, CSV export, auto-refresh
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
- `SALES_PHONE_NUMBER` — Braydon's number, must include country code (+1...)
- `SUPPORT_PHONE_NUMBER` — Phong's number, must include country code (+1...), leave empty to disable
- `BUSINESS_HOURS_START/END` — 24h format (e.g. 09:00, 17:00)
- `BUSINESS_TIMEZONE` — e.g. America/Chicago
- `DASHBOARD_TOKEN` — protects `PUT /api/config` (leave empty for open access)
- `DATABASE_URL` — Neon PostgreSQL connection string (`postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`)
- `PORT` — default 8001 (8000 conflicts with Laragon)

## API Endpoints
- `GET /api/health` — system health + Groq connectivity (cached 60s)
- `GET /api/calls?limit=&offset=&status=&search=` — paginated call logs with filtering (returns `total` count)
- `GET /api/calls/active` — currently active calls
- `GET /api/calls/stats` — summary stats (today, total, transferred, voicemail, avg duration)
- `GET /api/calls/{call_sid}` — single call detail with transcript
- `GET /api/config` — current configuration (includes `auth_required` flag)
- `PUT /api/config` — update business hours, transfer numbers (requires `DASHBOARD_TOKEN` if set)
- `GET /docs` — Swagger UI

## Web Dashboard
- **URL:** `/` redirects to `/dashboard/` (served as static files from `static/`)
- **Sections:** stats row, system status, config editor, call log table, transcript viewer modal
- **Features:**
  - Light/dark theme toggle (persisted in localStorage, inline script prevents flash)
  - Summary stats row: Today, All Time, Transferred, Voicemail, Avg Duration
  - Auto-refresh: health every 10s, calls + stats every 15s
  - Search by phone number, filter by call status
  - "Transferred To" column in call log (maps numbers to agent names: Braydon/Phong)
  - Live elapsed timer for active calls (pulsing blue dot)
  - Transcript modal with: meta info bar, voicemail audio playback, chat bubbles
  - CSV export button (exports current page of calls)
  - Pagination with "Page X of Y" total count
  - Empty state with icon when no calls match
  - Mobile responsive: card-style table layout with `data-label` attributes
  - Config form in 2-column grid layout
  - "Last updated" timestamp in header
  - Auth modal prompts for token on config save (if `DASHBOARD_TOKEN` is set)
  - Branded SVG favicon (teal rounded rect with microphone)
  - All user data escaped to prevent XSS
- **Tech:** Plain HTML/CSS/JS, no framework, CSS custom properties for theming
- **Theme colors:** Dark (#1a1a2e bg), Light (#f0f2f5 bg), Accent (#0f9d8c teal)

## Call Flow
1. **Normal call:** Twilio → `/voice/incoming` → check hours → greeting → `/voice/respond` loop (Groq generates replies)
2. **After hours:** `/voice/incoming` → hours check fails → closed message → `<Record>` voicemail
3. **Transfer (both numbers set):** caller mentions sales/support topic → Groq returns `[TRANSFER_SALES]` or `[TRANSFER_SUPPORT]` → DTMF menu "Press 1 for Braydon in Sales. Press 2 for Phong in Support." → `/voice/transfer` dials chosen department
4. **Transfer (one number set):** direct `<Dial>` to whichever number is configured
5. **Transfer (neither set):** apologize and hang up
6. **Server down:** Twilio falls back to TwiML Bin (static XML)

## Transfer Detection
Two-layer detection in `services/agent.py`:
1. **Prefix-based:** System prompt instructs Groq to prefix with `[TRANSFER_SALES]` or `[TRANSFER_SUPPORT]`
2. **Keyword fallback:** Regex catches phrases like "transfer you to sales/support" if AI forgets the prefix

### Transfer Edge Cases
| Scenario | Behavior |
|----------|----------|
| Both numbers set | DTMF menu: "Press 1 for Braydon in Sales, Press 2 for Phong in Support" |
| Only sales set | Direct dial to Braydon (sales) |
| Only support set | Direct dial to Phong (support) |
| Neither set | Apologize message |
| Invalid digit | Replay menu once, then default to Braydon (sales) |
| No digit (timeout 5s) | Default to detected department |

## Important Notes
- **Port 8000 is used by Laragon** — this project runs on port 8001
- **Twilio trial** can only `<Dial>` to Verified Caller IDs — **both callers AND transfer targets** must be verified (console.twilio.com → Verified Caller IDs). Inbound calls from unverified numbers get error 21264.
- **ngrok free tier** changes URLs on restart — must update Twilio webhooks each time (not needed with Render)
- `.env` changes require server restart (auto-reload only catches .py file changes)
- **Delete `__pycache__` folders** if code changes aren't reflected after restart
- Phone numbers must include country code: `+18326963009` not `+8326963009`
- **asyncpg requires `datetime` objects** for `TIMESTAMPTZ` columns — never pass ISO strings directly. Use `_parse_dt()` helper in `database.py`.
- **Stale call cleanup:** Background task in `main.py` runs every 2 minutes. Calls stuck as "active" for 15+ minutes are auto-closed to "completed". Prevents ghost calls when Twilio status callbacks fail (server restarts, 500 errors, test/curl calls).
- **Render free tier** has cold starts (~30s) if the service hasn't been called recently
- **Database** is Neon PostgreSQL (free tier) — call logs persist across Render deploys

## Twilio Webhook Config (Production)
- A call comes in: `https://ai-voice-agent-a4bq.onrender.com/voice/incoming` (POST)
- Call status changes: `https://ai-voice-agent-a4bq.onrender.com/voice/status` (POST)
- Primary handler fails (optional): TwiML Bin with fallback message

## Agents
| Agent | Department | Phone | Env Var |
|-------|-----------|-------|---------|
| Braydon | Sales | +18326963009 | `SALES_PHONE_NUMBER` |
| Phong | Support | +18326412959 | `SUPPORT_PHONE_NUMBER` |

## TODO: Next Tasks
- [x] ~~Build web dashboard~~ — done (plain HTML/CSS/JS served from FastAPI)
- [x] ~~Upgrade to persistent database (PostgreSQL) for Render~~ — done (Neon free tier, asyncpg)
- [x] ~~Add sales + support transfer with DTMF menu~~ — done (Braydon/Phong)
- [x] ~~Fix stale "active" calls~~ — done (background cleanup every 2min + asyncpg datetime fix)
- [x] ~~Dashboard overhaul~~ — done (light/dark theme, stats row, transferred column, CSV export, voicemail playback, responsive mobile, empty states, pagination totals, branded favicon)
- [ ] Set up TwiML Bin fallback for server-down scenario
- [ ] Test after-hours voicemail flow
- [ ] Add more natural TTS voice (ElevenLabs or Deepgram)
- [ ] Add dashboard auth for read endpoints (currently only config PUT is protected)
