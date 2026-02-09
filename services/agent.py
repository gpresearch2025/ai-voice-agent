import asyncio
import logging
import re
from groq import AsyncGroq
from config import settings

logger = logging.getLogger(__name__)

client = AsyncGroq(api_key=settings.groq_api_key)

SYSTEM_PROMPT = """You are a friendly and professional AI phone assistant for our company.
Your job is to help callers with their questions and route them appropriately.

CRITICAL RULES:
1. Be concise. Phone conversations should use short, clear sentences.
2. Be warm and professional. Greet callers politely.
3. TRANSFER RULES — These are MANDATORY:

   a) SALES TRANSFER: When the caller mentions ANY of the following topics:
      pricing, purchasing, buying, cost, sales, demo, trial, contract, quote, order, plans,
      or asks to speak with a sales representative,
      you MUST start your response with the EXACT text [TRANSFER_SALES] followed by a space
      and then a brief transition message.

      Correct example: [TRANSFER_SALES] Great, let me connect you with our sales team right away.

   b) SUPPORT TRANSFER: When the caller mentions ANY of the following topics:
      help, technical issue, support, troubleshoot, bug, error, problem, broken, not working,
      fix, repair, account issue, password reset, login issue,
      or asks to speak with a support representative or technician,
      you MUST start your response with the EXACT text [TRANSFER_SUPPORT] followed by a space
      and then a brief transition message.

      Correct example: [TRANSFER_SUPPORT] Let me connect you with our support team to help with that.

   You MUST include the correct prefix at the very beginning. Do NOT skip it.

4. For general questions (hours, directions, FAQs), answer directly WITHOUT any prefix.
5. If you don't know the answer, say so honestly and offer to connect them with a human.
6. Keep responses under 3 sentences when possible — callers are listening, not reading.
7. Never mention that you are an AI unless directly asked.
"""

TRANSFER_SALES_PREFIX = "[TRANSFER_SALES]"
TRANSFER_SUPPORT_PREFIX = "[TRANSFER_SUPPORT]"

# Fallback keywords for detecting transfer intent if the AI forgets the prefix
SALES_KEYWORDS = re.compile(
    r"\b(transfer you|connect you with.*(sales|representative|agent|pricing)|"
    r"let me (transfer|connect|put you through).*(sales|pricing))\b",
    re.IGNORECASE,
)

SUPPORT_KEYWORDS = re.compile(
    r"\b(connect you with.*(support|technician|technical|tech team)|"
    r"let me (transfer|connect|put you through).*(support|technical|tech team))\b",
    re.IGNORECASE,
)


async def get_ai_response(conversation_messages: list[dict]) -> str:
    """Get a response from Groq/Llama given conversation history."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_messages

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=150,
                temperature=0.7,
            ),
            timeout=8.0,
        )
        return response.choices[0].message.content.strip()

    except asyncio.TimeoutError:
        logger.error("Groq request timed out after 8 seconds")
        return (
            "I apologize, but I'm having a little trouble right now. "
            "Could you please repeat that, or I can connect you with a team member?"
        )
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return (
            "I'm sorry, I'm experiencing a technical issue at the moment. "
            "Please hold while I connect you with a team member, "
            "or you can call back in a few minutes."
        )


def detect_transfer(response: str) -> str | None:
    """Check if response indicates a transfer request.

    Returns 'sales', 'support', or None.
    """
    if response.startswith(TRANSFER_SALES_PREFIX):
        return "sales"
    if response.startswith(TRANSFER_SUPPORT_PREFIX):
        return "support"
    # Fallback: AI forgot the prefix but is clearly trying to transfer
    if SUPPORT_KEYWORDS.search(response):
        logger.info("Support transfer detected via keyword fallback")
        return "support"
    if SALES_KEYWORDS.search(response):
        logger.info("Sales transfer detected via keyword fallback")
        return "sales"
    return None


def strip_transfer_prefix(response: str) -> str:
    return (
        response
        .removeprefix(TRANSFER_SALES_PREFIX)
        .removeprefix(TRANSFER_SUPPORT_PREFIX)
        .strip()
    )
