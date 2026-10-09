import os
from datetime import date

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()
DAILY_LIMIT = int(os.getenv("DAILY_AI_LIMIT", "15"))
_state = {"day": date.today(), "count": 0}


def check_ai_budget():
    """Call before any Gemini request. Raises 429 once the daily cap is reached."""
    today = date.today()
    if _state["day"] != today:
        _state["day"] = today
        _state["count"] = 0
    if _state["count"] >= DAILY_LIMIT:
        raise HTTPException(429, "Daily AI request limit reached. Try again tomorrow.")
    _state["count"] += 1
    