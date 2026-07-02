"""Patient outcomes — turn tracked conversions into the number a client renews for.

The weekly report already pulls organic conversions into ``conversions_daily`` via
``ga4_client.track_conversions`` (fed by the ``lead_tracking`` snippet's
``phone_click`` / ``form_submit`` / ``appointment_request`` events). This module
rolls those into the headline outcome:

    inquiries          = calls + forms + booking-CTA clicks (organic)
    estimated patients = inquiries × close_rate
    estimated value    = estimated patients × avg_case_value

Everything downstream (report hero, exec summary, dashboard column) reads
``patient_outcomes()`` so the math lives in exactly one place.
"""

from __future__ import annotations

# The three organic-conversion events that represent a real new-patient inquiry.
INQUIRY_EVENTS = ("phone_click", "form_submit", "appointment_request")
DEFAULT_CLOSE_RATE = 0.35  # conservative inquiry → booked-patient rate when unset


def _inquiries(conv: dict) -> int:
    """Sum the inquiry events from a get_conversions() {event_name: count} map."""
    return int(sum(int(conv.get(e, 0) or 0) for e in INQUIRY_EVENTS))


def patient_outcomes(db, customer_id: str, start: str, end: str,
                     prev_start: str | None = None, prev_end: str | None = None) -> dict | None:
    """Outcome metrics for [start, end] (ISO dates), organic channel.

    Returns None when the practice has no tracked conversions in the window (so the
    report simply omits the band rather than showing a hollow $0). ``estimated_value``
    and ``estimated_patients`` are None until Dan sets ``avg_case_value`` — inquiries
    still render on their own.
    """
    cust = db.get_customer(customer_id) or {}
    conv = db.get_conversions(customer_id, start, end, channel="organic")
    inquiries = _inquiries(conv)
    if inquiries == 0 and not conv:
        return None

    acv = cust.get("avg_case_value")  # whole dollars, or None
    close_rate = cust.get("close_rate")
    close_rate = DEFAULT_CLOSE_RATE if close_rate is None else float(close_rate)

    est_patients = round(inquiries * close_rate, 1) if close_rate else None
    est_value = int(round(est_patients * acv)) if (acv and est_patients is not None) else None

    prev_inquiries = None
    if prev_start and prev_end:
        prev_inquiries = _inquiries(
            db.get_conversions(customer_id, prev_start, prev_end, channel="organic")
        )

    return {
        "inquiries": inquiries,
        "breakdown": {
            "calls": int(conv.get("phone_click", 0) or 0),
            "forms": int(conv.get("form_submit", 0) or 0),
            "bookings": int(conv.get("appointment_request", 0) or 0),
        },
        "estimated_patients": est_patients,
        "estimated_value": est_value,          # dollars, or None
        "avg_case_value": acv,                 # dollars, or None
        "close_rate": close_rate,
        "prev_inquiries": prev_inquiries,      # int or None
        "configured": acv is not None,         # has Dan set a case value?
    }


def inquiries_in_window(db, customer_id: str, start: str, end: str) -> int:
    """Cheap count of organic new-patient inquiries in a window (dashboard column)."""
    return _inquiries(db.get_conversions(customer_id, start, end, channel="organic"))
