import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Form, Response
from twilio.twiml.voice_response import VoiceResponse, Gather

from config import settings
from models import CallRecord, CallStatus as CallStatusEnum
from database import save_call, update_call_transcript, update_call_voicemail, update_call_status
from services.hours import is_business_hours, get_closed_message
from services.call_manager import call_manager
from services.agent import get_ai_response, is_sales_transfer, strip_transfer_prefix

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["Voice Webhooks"])

TWIML_CONTENT_TYPE = "application/xml"


@router.post("/incoming")
async def handle_incoming_call(
    CallSid: str = Form(""),
    From: str = Form(""),
    To: str = Form(""),
):
    """Main entry point for incoming Twilio calls."""
    logger.info(f"Incoming call: {CallSid} from {From}")

    # Save call record
    record = CallRecord(
        call_sid=CallSid,
        from_number=From,
        to_number=To,
        status=CallStatusEnum.ACTIVE,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    await save_call(record)
    call_manager.start_call(CallSid)

    response = VoiceResponse()

    # Check business hours
    if not is_business_hours():
        logger.info(f"After-hours call from {From}")
        response.say(get_closed_message(), voice="Polly.Joanna")
        response.record(
            action="/voice/voicemail",
            method="POST",
            max_length=120,
            transcribe=False,
            play_beep=True,
        )
        response.say("We did not receive a recording. Goodbye.")
        return Response(content=str(response), media_type=TWIML_CONTENT_TYPE)

    # Business hours — greet and gather speech
    greeting = "Hello! Thank you for calling. How can I help you today?"
    call_manager.add_turn(CallSid, "assistant", greeting)

    gather = Gather(
        input="speech",
        action="/voice/respond",
        method="POST",
        speech_timeout="auto",
        language="en-US",
    )
    gather.say(greeting, voice="Polly.Joanna")
    response.append(gather)

    # If no input, prompt again
    response.say("I didn't catch that. Let me try again.")
    response.redirect("/voice/incoming", method="POST")

    return Response(content=str(response), media_type=TWIML_CONTENT_TYPE)


@router.post("/respond")
async def handle_response(
    CallSid: str = Form(""),
    SpeechResult: str = Form(""),
):
    """Process caller speech and generate AI response."""
    logger.info(f"Speech from {CallSid}: {SpeechResult}")

    # Record caller's words
    call_manager.add_turn(CallSid, "caller", SpeechResult)

    # Get AI response
    openai_messages = call_manager.get_openai_messages(CallSid)
    ai_text = await get_ai_response(openai_messages)

    response = VoiceResponse()

    # Check for sales transfer
    if is_sales_transfer(ai_text):
        transition_message = strip_transfer_prefix(ai_text)
        call_manager.add_turn(CallSid, "assistant", transition_message)

        # Save transcript before transfer
        transcript = call_manager.end_call(CallSid)
        await update_call_transcript(CallSid, transcript)
        await update_call_status(CallSid, CallStatusEnum.TRANSFERRED)

        response.say(transition_message, voice="Polly.Joanna")
        response.dial(settings.sales_phone_number)

        logger.info(f"Transferring {CallSid} to sales: {settings.sales_phone_number}")
        return Response(content=str(response), media_type=TWIML_CONTENT_TYPE)

    # Normal AI reply — speak and gather more input
    call_manager.add_turn(CallSid, "assistant", ai_text)

    gather = Gather(
        input="speech",
        action="/voice/respond",
        method="POST",
        speech_timeout="auto",
        language="en-US",
    )
    gather.say(ai_text, voice="Polly.Joanna")
    response.append(gather)

    # If no input after AI speaks, say goodbye
    response.say(
        "It seems like you may have stepped away. Thank you for calling. Goodbye!",
        voice="Polly.Joanna",
    )

    return Response(content=str(response), media_type=TWIML_CONTENT_TYPE)


@router.post("/voicemail")
async def handle_voicemail(
    CallSid: str = Form(""),
    RecordingUrl: str = Form(""),
):
    """Save voicemail recording URL."""
    logger.info(f"Voicemail received for {CallSid}: {RecordingUrl}")

    await update_call_voicemail(CallSid, RecordingUrl)

    response = VoiceResponse()
    response.say(
        "Thank you for your message. We'll get back to you as soon as possible. Goodbye!",
        voice="Polly.Joanna",
    )
    response.hangup()

    return Response(content=str(response), media_type=TWIML_CONTENT_TYPE)


@router.post("/status")
async def handle_status_callback(
    CallSid: str = Form(""),
    CallStatus: str = Form(""),
):
    """Twilio status callback — fired when call ends."""
    logger.info(f"Call status update: {CallSid} -> {CallStatus}")

    if CallStatus in ("completed", "busy", "no-answer", "failed", "canceled"):
        # Save any remaining transcript
        transcript = call_manager.end_call(CallSid)
        if transcript:
            await update_call_transcript(CallSid, transcript)
        await update_call_status(
            CallSid,
            status=CallStatusEnum.COMPLETED,
            ended_at=datetime.now(timezone.utc).isoformat(),
        )

    return Response(content="<Response/>", media_type=TWIML_CONTENT_TYPE)
