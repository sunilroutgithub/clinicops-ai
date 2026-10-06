# ClinicOps AI

An AI assistant that removes administrative work for small clinics: it sorts incoming messages, proposes appointment slots, extracts data from insurance documents, and sends anything uncertain to a human. It does not diagnose or give medical advice.

**Uses synthetic data only. Not HIPAA-compliant. Do not use with real patient data.**

## What it does

- **AI inbox:** classifies messages (appointment, billing, insurance, referral, prescription, question, emergency)
- **Scheduling agent:** reads "Thursday afternoon", proposes slots, books and reschedules, prevents double-booking
- **Document extraction:** reads a PDF and extracts patient, insurer, policy number, referral date, doctor
- **Human-in-the-loop:** emergencies, low-confidence results and AI errors go to a review queue
- **Audit trail:** every action is logged with actor (ai / system / human) and timestamp

## Flow

```
Message / PDF -> AI (Gemini, structured output) -> confident? 
    yes -> action (classify / propose slots / save fields)
    no  -> human review queue -> approve / reject
Every step -> audit log
```

## Tech stack

Python, FastAPI, SQLAlchemy, SQLite, Gemini API (free tier), pytest

## Run locally

```bash
cd backend
python -m venv venv

venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs

## Tests

```bash
cd backend
python -m pytest tests -v
```

## Evaluation

Classifier tested on 28 synthetic messages (4 per category, 7 categories) using `gemini-3.5-flash-lite`:

- Accuracy: 28/28
- Emergencies (4/4) were correctly classified and routed to human review
- Caveat: small, clean, synthetic set. Real messages will be messier, so a larger set is planned.

Run it yourself: `cd backend && python eval_classifier.py` (results are cached, so it resumes after a quota stop).

Note: free-tier API limits are tight (about 20 requests/day on one model when tested), so API errors are treated as "send to human review" rather than guessed.


## Roadmap

- Frontend dashboard for the review queue
- Email inbox integration
- Evaluation set to measure classifier accuracy
- Deployment