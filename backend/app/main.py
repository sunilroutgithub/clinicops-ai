from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import Base, engine, get_db
from app import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ClinicOps AI")


class PatientCreate(BaseModel):
    name: str
    email: str
    phone: str | None = None


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


@app.get("/audit")
def list_audit(db: Session = Depends(get_db)):
    logs = db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).all()
    return [
        {"time": l.timestamp, "actor": l.actor, "action": l.action, "details": l.details}
        for l in logs
    ]