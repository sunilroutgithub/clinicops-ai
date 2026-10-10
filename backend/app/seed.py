from app import models
from app.audit import log_action
from app.database import SessionLocal


def seed_demo_data():
    """Add fake demo records, but only if the database is empty."""
    db = SessionLocal()
    try:
        if db.query(models.Patient).count() > 0:
            return
        db.add_all([
            models.Patient(name="John Smith", email="john@example.com"),
            models.Patient(name="Jane Doe", email="jane@example.com"),
        ])
        db.add_all([
            models.Message(sender="amy@example.com",
                           body="I have chest pain and it is getting worse.",
                           category="emergency", confidence=1.0, status="needs_review"),
            models.Message(sender="jane@example.com",
                           body="I need to see the doctor sometime soon.",
                           category="appointment", confidence=0.1, status="needs_review"),
        ])
        db.add(models.ExtractedDocument(
            filename="incomplete_insurance.pdf", patient_name="Jane Doe",
            insurance_provider="Sample Health Insurance Co.", policy_number="",
            referral_date="", doctor="", confidence=0.5, status="needs_review"))
        db.commit()
        log_action(db, "system", "demo_data_loaded", "Fake demo records created")
    finally:
        db.close()