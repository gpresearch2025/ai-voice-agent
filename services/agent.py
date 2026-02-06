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
3. TRANSFER RULE — This is MANDATORY: When the caller mentions ANY of the following topics:
   pricing, purchasing, buying, cost, sales, demo, trial, contract, quote, order, plans,
   or asks to speak with a sales representative or human agent,
   you MUST start your response with the EXACT text [TRANSFER_SALES] followed by a space
   and then a brief transition message.

   Correct example: [TRANSFER_SALES] Great, let me connect you with our sales team right away.
   Correct example: [TRANSFER_SALES] I'll transfer you to a sales representative who can help with pricing.

   You MUST include [TRANSFER_SALES] at the very beginning. Do NOT skip it.

4. For general questions (support, hours, directions, FAQs), answer directly WITHOUT the prefix.
5. If you don't know the answer, say so honestly and offer to connect them with a human.
6. Keep responses under 3 sentences when possible — callers are listening, not reading.
7. Never mention that you are an AI unless directly asked.
"""

TRANSFER_PREFIX = "[TRANSFER_SALES]"

# Fallback keywords for detecting sales intent if the AI forgets the prefix
SALES_KEYWORDS = re.compile(
    r"\b(transfer you|connect you with.*(sales|representative|agent)|"
    r"let me (transfer|connect|put you through))\b",
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


def is_sales_transfer(response: str) -> bool:
    """Check if response indicates a sales transfer — by prefix or keyword fallback."""
    if response.startswith(TRANSFER_PREFIX):
        return True
    # Fallback: AI forgot the prefix but is clearly trying to transfer
    if SALES_KEYWORDS.search(response):
        logger.info("Sales transfer detected via keyword fallback")
        return True
    return False


def strip_transfer_prefix(response: str) -> str:
    return response.removeprefix(TRANSFER_PREFIX).strip()
