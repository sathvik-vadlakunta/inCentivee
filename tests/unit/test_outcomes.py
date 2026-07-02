"""Patient-outcomes math: inquiries → estimated patients → estimated production."""

from geo_agent.db import CustomerDB
from geo_agent import outcomes as oc


def _db():
    db = CustomerDB(":memory:")
    db.add_customer("c1", "C One", "c1.com")
    return db


def _seed(db, date, calls=0, forms=0, bookings=0, channel="organic"):
    for ev, n in (("phone_click", calls), ("form_submit", forms),
                  ("appointment_request", bookings)):
        if n:
            db.record_conversion("c1", date, ev, channel, n)


def test_inquiries_sum_and_breakdown():
    db = _db()
    _seed(db, "2026-06-15", calls=8, forms=5, bookings=2)
    o = oc.patient_outcomes(db, "c1", "2026-06-01", "2026-06-30")
    assert o["inquiries"] == 15
    assert o["breakdown"] == {"calls": 8, "forms": 5, "bookings": 2}
    db.close()


def test_estimated_production_when_case_value_set():
    db = _db()
    db.update_customer("c1", avg_case_value=1200, close_rate=0.4)
    _seed(db, "2026-06-15", calls=10, forms=5)  # 15 inquiries
    o = oc.patient_outcomes(db, "c1", "2026-06-01", "2026-06-30")
    assert o["estimated_patients"] == 6.0        # 15 * 0.4
    assert o["estimated_value"] == 7200          # 6 * 1200
    assert o["configured"] is True
    db.close()


def test_inquiries_without_case_value_still_report():
    db = _db()  # avg_case_value unset
    _seed(db, "2026-06-15", calls=4)
    o = oc.patient_outcomes(db, "c1", "2026-06-01", "2026-06-30")
    assert o["inquiries"] == 4
    assert o["estimated_value"] is None
    assert o["configured"] is False
    db.close()


def test_prior_window_delta():
    db = _db()
    _seed(db, "2026-06-15", calls=10)
    _seed(db, "2026-05-15", calls=6)
    o = oc.patient_outcomes(db, "c1", "2026-06-01", "2026-06-30",
                            "2026-05-01", "2026-05-31")
    assert o["inquiries"] == 10
    assert o["prev_inquiries"] == 6
    db.close()


def test_no_conversions_returns_none():
    db = _db()
    assert oc.patient_outcomes(db, "c1", "2026-06-01", "2026-06-30") is None
    db.close()


def test_paid_channel_excluded():
    db = _db()
    _seed(db, "2026-06-15", calls=5, channel="paid")
    _seed(db, "2026-06-15", forms=3, channel="organic")
    o = oc.patient_outcomes(db, "c1", "2026-06-01", "2026-06-30")
    assert o["inquiries"] == 3  # only organic counts
    db.close()
