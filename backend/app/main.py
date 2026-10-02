from datetime import date, datetime
from fastapi import HTTPException
from app.ai.scheduler import find_free_slots, book_slot
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import log_action
from app.ai.classifier import classify_message
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

class BookingIn(BaseModel):
    patient_id: int
    doctor: str
    start_time: datetime


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