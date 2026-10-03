import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


class DocumentData(BaseModel):
    patient_name: str
    insurance_provider: str
    policy_number: str
    referral_date: str  # YYYY-MM-DD, or "" if missing
    doctor: str
    confidence: float


PROMPT = (
    "You read documents for a medical clinic's front desk. Extract: patient_name, "
    "insurance_provider, policy_number, referral_date (YYYY-MM-DD), and doctor. "
    "Use an empty string for any field that is not in the document. Never guess. "
    "Give a confidence from 0 to 1 for how sure you are about all fields together."
)


def extract_document(pdf_bytes: bytes) -> dict:
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(

            model=MODEL,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DocumentData,
                temperature=0,
            ),
        )
        d: DocumentData = response.parsed
        needs_review = (
            d.confidence < 0.9 or not d.patient_name or not d.policy_number
        )
        return {**d.model_dump(), "needs_review": needs_review}
    except Exception as e:
        return {"patient_name": "", "insurance_provider": "", "policy_number": "",
                "referral_date": "", "doctor": "", "confidence": 0.0,
                "needs_review": True, "error": str(e)}