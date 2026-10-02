from datetime import date, datetime, time, timedelta
from sqlalchemy.orm import Session

from app import models

DOCTORS = ["Dr. Rao", "Dr. Mehta"]  # fake doctors
SLOT_MINUTES = 30
PARTS = {"morning": (9, 12), "afternoon": (12, 17), "any": (9, 17)}


def find_free_slots(db: Session, day: date, part: str = "any", limit: int = 3) -> list[dict]:
    """Return up to `limit` free slots on `day`, one doctor per time."""
    if day.weekday() >= 5:  # Saturday/Sunday: clinic closed
        return []

    start_h, end_h = PARTS[part]
    day_start = datetime.combine(day, time.min)
    day_end = day_start + timedelta(days=1)

    booked = {
        (a.doctor, a.start_time)
        for a in db.query(models.Appointment).filter(
            models.Appointment.status == "scheduled",
            models.Appointment.start_time >= day_start,
            models.Appointment.start_time < day_end,
        )
    }

    slots = []
    current = datetime.combine(day, time(start_h))
    end = datetime.combine(day, time(end_h))
    while current < end and len(slots) < limit:

        for doctor in DOCTORS:
            if (doctor, current) not in booked:
                slots.append({"doctor": doctor, "start_time": current.isoformat()})
                break  # one doctor per time, so options are different times
        current += timedelta(minutes=SLOT_MINUTES)
    return slots


def book_slot(db: Session, patient_id: int, doctor: str, start_time: datetime) -> models.Appointment:
    """Book a slot. Raises ValueError if it is invalid or already taken."""
    if not db.get(models.Patient, patient_id):
        raise ValueError("Patient not found")
    if doctor not in DOCTORS:
        raise ValueError("Unknown doctor")
    if start_time < datetime.now():
        raise ValueError("Cannot book a time in the past")
    if start_time.weekday() >= 5 or not (9 <= start_time.hour < 17) or start_time.minute % SLOT_MINUTES:
        raise ValueError("Outside clinic hours")

    taken = db.query(models.Appointment).filter_by(
        doctor=doctor, start_time=start_time, status="scheduled"
    ).first()
    if taken:
        raise ValueError("That slot is already booked")

    appt = models.Appointment(patient_id=patient_id, doctor=doctor, start_time=start_time)
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt