from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.ai.scheduler import find_free_slots, book_slot, reschedule_appointment


@pytest.fixture()
def db():
    """A fresh in-memory database for every test, so your real clinicops.db is never touched."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    patient = models.Patient(name="Test Patient", email="test@example.com")
    session.add(patient)
    session.commit()
    yield session
    session.close()


def next_weekday(days_ahead=7):
    """A future Monday-Friday date, so tests don't fail on weekends or in the past."""
    d = date.today() + timedelta(days=days_ahead)

    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute)


def test_find_slots_returns_three_in_afternoon(db):
    slots = find_free_slots(db, next_weekday(), "afternoon")
    assert len(slots) == 3
    assert slots[0]["start_time"].endswith("12:00:00")


def test_weekend_has_no_slots(db):
    d = date.today() + timedelta(days=1)
    while d.weekday() != 5:  # find a Saturday
        d += timedelta(days=1)
    assert find_free_slots(db, d) == []


def test_booking_removes_slot_for_that_doctor(db):
    day = next_weekday()
    book_slot(db, 1, "Dr. Rao", at(day, 12))
    first = find_free_slots(db, day, "afternoon")[0]
    assert first["doctor"] == "Dr. Mehta"  # Dr. Rao is busy at 12:00


def test_double_booking_is_refused(db):
    day = next_weekday()
    book_slot(db, 1, "Dr. Rao", at(day, 12))

    with pytest.raises(ValueError, match="already booked"):
        book_slot(db, 1, "Dr. Rao", at(day, 12))


def test_booking_in_the_past_is_refused(db):
    with pytest.raises(ValueError, match="past"):
        book_slot(db, 1, "Dr. Rao", datetime(2020, 1, 6, 10, 0))


def test_booking_outside_hours_is_refused(db):
    day = next_weekday()
    with pytest.raises(ValueError, match="clinic hours"):
        book_slot(db, 1, "Dr. Rao", at(day, 20))


def test_reschedule_cancels_old_and_books_new(db):
    day = next_weekday()
    old = book_slot(db, 1, "Dr. Rao", at(day, 12))
    old_id = old.id
    _, new = reschedule_appointment(db, old_id, "Dr. Rao", at(day, 14))
    assert db.get(models.Appointment, old_id).status == "cancelled"
    assert new.status == "scheduled"
    assert find_free_slots(db, day, "afternoon")[0]["doctor"] == "Dr. Rao"  # 12:00 is free again


def test_cannot_reschedule_a_cancelled_appointment(db):
    day = next_weekday()
    old = book_slot(db, 1, "Dr. Rao", at(day, 12))
    old_id = old.id
    reschedule_appointment(db, old_id, "Dr. Rao", at(day, 14))
    with pytest.raises(ValueError, match="not active"):
        reschedule_appointment(db, old_id, "Dr. Rao", at(day, 15))