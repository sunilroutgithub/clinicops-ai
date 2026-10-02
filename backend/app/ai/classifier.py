import os
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
CONFIDENCE_THRESHOLD = 0.95

Category = Literal[
    "appointment",
    "billing",
    "insurance",
    "referral",
    "prescription",
    "patient_question",
    "emergency",
]


class Classification(BaseModel):
    category: Category
    confidence: float  # 0.0 to 1.0
    reason: str


SYSTEM_PROMPT = """You sort incoming messages for a small medical clinic's front desk.
Classify each message into exactly one category:
- appointment: booking, rescheduling, cancelling visits
- billing: invoices, payments, charges
- insurance: coverage, policy, claims, insurance documents
- referral: referrals to or from other doctors
- prescription: refills or medication requests
- patient_question: general questions that fit none of the above
- emergency: any mention of urgent symptoms, severe pain, chest pain, trouble breathing, suicidal thoughts, or anything that sounds like an emergency
Give a confidence from 0 to 1 and a one-sentence reason.
If unsure, use a lower confidence. Never give medical advice."""


def classify_message(body: str) -> dict:
    """Returns category, confidence, reason, and whether a human must review it."""
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=MODEL,
            contents=body,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=Classification,
                temperature=0,
            ),
        )
        result: Classification = response.parsed
        needs_review = (
            result.category == "emergency"
            or result.confidence < CONFIDENCE_THRESHOLD
        )
        return {
            "category": result.category,
            "confidence": result.confidence,
            "reason": result.reason,
            "needs_review": needs_review,
        }
    except Exception as e:
        # If the AI fails, never guess: send it to a human.
        return {
            "category": None,
            "confidence": 0.0,
            "reason": f"AI error: {e}",
            "needs_review": True,
        }