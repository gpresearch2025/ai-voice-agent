import logging
from contextlib import asynccontextmanager
import asyncpg
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from config import settings
from database import init_db
from routes.voice import router as voice_router
from routes.api import router as api_router

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to PostgreSQL...")
    pool = await asyncpg.create_pool(settings.database_url, ssl="require")
    await init_db(pool)
    app.state.pool = pool
    logger.info("AI Voice Agent ready")
    logger.info(f"Business hours: {settings.business_hours_start}-{settings.business_hours_end} ({settings.business_timezone})")
    logger.info(f"Sales transfer: {settings.sales_phone_number}")
    yield
    await pool.close()
    logger.info("Database pool closed")


app = FastAPI(
    title="AI Voice Agent",
    description="AI-powered phone agent with Twilio + Groq",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount routers
app.include_router(voice_router)
app.include_router(api_router)


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard/")


# Mount static files AFTER routers so /api/* and /voice/* take priority
app.mount("/dashboard", StaticFiles(directory="static", html=True), name="dashboard")


# Fallback TwiML for when server is reachable but encounters unhandled errors
@app.exception_handler(500)
async def fallback_handler(request, exc):
    from fastapi.responses import Response
    logger.error(f"Internal error: {exc}")
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">We are experiencing technical difficulties. Please try your call again in a few minutes. Goodbye.</Say>
    <Hangup/>
</Response>"""
    return Response(content=twiml, media_type="application/xml", status_code=500)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", settings.port))
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=port,
        reload=os.environ.get("RENDER") is None,  # Only reload locally
    )
