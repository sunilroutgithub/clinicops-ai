from pathlib import Path
from fastapi.responses import FileResponse
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from app.ai.extractor import extract_document
from datetime import date, datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.classifier import classify_message
from app.ai.scheduler import find_free_slots, book_slot, parse_slot_request, reschedule_appointment
from app.audit import log_action
from app.database import Base, engine, get_db
from app import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ClinicOps AI")


class PatientCreate(BaseModel):
    name: str
    email: str
    phone: str | None = None


class MessageIn(BaseModel):
    sender: str
    body: str


class BookingIn(BaseModel):
    patient_id: int
    doctor: str
    start_time: datetime



class ProposeIn(BaseModel):
    patient_id: int
    message: str

class RescheduleIn(BaseModel):
    appointment_id: int
    doctor: str
    start_time: datetime

class ReviewIn(BaseModel):
    decision: str  # "approved" or "rejected"
    note: str | None = None
    reviewer: str = "staff"    

@app.get("/")
def health():
    return {"status": "ok", "app": "ClinicOps AI"}


@app.post("/patients")
def create_patient(data: PatientCreate, db: Session = Depends(get_db)):
    patient = models.Patient(**data.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    log_action(db, "system", "patient_created", f"Patient id={patient.id}, name={patient.name}")
    return {"id": patient.id, "name": patient.name, "email": patient.email}


@app.get("/patients")
def list_patients(db: Session = Depends(get_db)):
    patients = db.query(models.Patient).all()
    return [{"id": p.id, "name": p.name, "email": p.email} for p in patients]


@app.post("/messages")
def receive_message(data: MessageIn, db: Session = Depends(get_db)):
    msg = models.Message(sender=data.sender, body=data.body)
    db.add(msg)

    db.commit()
    db.refresh(msg)
    log_action(db, "system", "message_received", f"Message id={msg.id} from {msg.sender}")

    result = classify_message(data.body)
    msg.category = result["category"]
    msg.confidence = result["confidence"]
    msg.status = "needs_review" if result["needs_review"] else "done"
    db.commit()

    log_action(
        db, "ai", "message_classified",
        f"Message id={msg.id}: {result['category']} ({result['confidence']}) - {result['reason']}",
    )

    if result["needs_review"]:
        log_action(db, "system", "sent_to_human_review", f"Message id={msg.id}")

    return {
        "id": msg.id,
        "category": msg.category,
        "confidence": msg.confidence,
        "status": msg.status,
        "reason": result["reason"],
    }


@app.get("/messages")
def list_messages(db: Session = Depends(get_db)):
    msgs = db.query(models.Message).order_by(models.Message.id.desc()).all()
    return [
        {"id": m.id, "sender": m.sender, "body": m.body,

         "category": m.category, "confidence": m.confidence, "status": m.status}
        for m in msgs
    ]


@app.get("/audit")
def list_audit(db: Session = Depends(get_db)):
    logs = db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).all()
    return [
        {"time": l.timestamp, "actor": l.actor, "action": l.action, "details": l.details}
        for l in logs
    ]


@app.get("/slots")
def get_slots(day: date, part: str = "any", db: Session = Depends(get_db)):
    if part not in ("morning", "afternoon", "any"):
        raise HTTPException(400, "part must be morning, afternoon or any")
    return find_free_slots(db, day, part)


@app.post("/appointments")
def create_appointment(data: BookingIn, db: Session = Depends(get_db)):
    try:
        appt = book_slot(db, data.patient_id, data.doctor, data.start_time)
    except ValueError as e:
        raise HTTPException(400, str(e))
    log_action(db, "system", "appointment_booked",
               f"Appointment id={appt.id}, patient={appt.patient_id}, {appt.doctor} at {appt.start_time}")
    return {"id": appt.id, "doctor": appt.doctor, "start_time": appt.start_time}



@app.post("/propose-slots")
def propose_slots(data: ProposeIn, db: Session = Depends(get_db)):
    if not db.get(models.Patient, data.patient_id):
        raise HTTPException(404, "Patient not found")

    req = parse_slot_request(data.message)
    log_action(db, "ai", "slot_request_parsed",
               f"patient={data.patient_id}, day={req['day']}, part={req['part']}, "
               f"confidence={req['confidence']}")

    if req["needs_review"]:
        log_action(db, "system", "sent_to_human_review",
                   f"Unclear scheduling request from patient {data.patient_id}")
        return {"status": "needs_review", "slots": []}

    slots = find_free_slots(db, req["day"], req["part"])
    log_action(db, "system", "slots_proposed", f"{len(slots)} slots for {req['day']}")
    return {"status": "proposed", "day": req["day"], "part": req["part"], "slots": slots}

@app.post("/reschedule")
def reschedule(data: RescheduleIn, db: Session = Depends(get_db)):
    try:
        old, new = reschedule_appointment(db, data.appointment_id, data.doctor, data.start_time)
    except ValueError as e:
        raise HTTPException(400, str(e))
    log_action(db, "system", "appointment_rescheduled",
               f"Appointment id={old.id} cancelled, new appointment id={new.id} "
               f"with {new.doctor} at {new.start_time}")
    return {"cancelled_id": old.id, "new_id": new.id,
            "doctor": new.doctor, "start_time": new.start_time}   


@app.get("/review")
def review_queue(db: Session = Depends(get_db)):
    msgs = (
        db.query(models.Message)
        .filter(models.Message.status == "needs_review")
        .order_by(models.Message.id)
        .all()
    )
    return [
        {"id": m.id, "sender": m.sender, "body": m.body,
         "category": m.category, "confidence": m.confidence}
        for m in msgs
    ]


@app.post("/review/{message_id}")
def review_message(message_id: int, data: ReviewIn, db: Session = Depends(get_db)):
    if data.decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be approved or rejected")

    msg = db.get(models.Message, message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.status != "needs_review":
        raise HTTPException(400, "Message is not waiting for review")

    msg.status = data.decision
    db.commit()
    log_action(db, "human", f"review_{data.decision}",
               f"Message id={msg.id} by {data.reviewer}. Note: {data.note or '-'}")
    return {"id": msg.id, "status": msg.status}


@app.post("/documents")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 5 MB)")

    result = extract_document(pdf_bytes)
    doc = models.ExtractedDocument(
        filename=file.filename,
        patient_name=result["patient_name"],
        insurance_provider=result["insurance_provider"],
        policy_number=result["policy_number"],
        referral_date=result["referral_date"],
        doctor=result["doctor"],
        confidence=result["confidence"],
        status="needs_review" if result["needs_review"] else "done",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_action(db, "ai", "document_extracted",
               f"Document id={doc.id} ({doc.filename}), confidence={doc.confidence}")
    if result["needs_review"]:
        log_action(db, "system", "sent_to_human_review", f"Document id={doc.id}")

    return {"id": doc.id, "patient_name": doc.patient_name,
            "insurance_provider": doc.insurance_provider,
            "policy_number": doc.policy_number, "referral_date": doc.referral_date,
            "doctor": doc.doctor, "confidence": doc.confidence, "status": doc.status}


@app.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(models.ExtractedDocument).order_by(models.ExtractedDocument.id.desc()).all()
    return [{"id": d.id, "filename": d.filename, "patient_name": d.patient_name,
             "policy_number": d.policy_number, "status": d.status} for d in docs]    

@app.get("/ui")
def ui():
    return FileResponse(Path(__file__).parent / "static" / "index.html")             