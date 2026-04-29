"""Finite State Machine for customer lifecycle and pipeline runs.

Enforces valid state transitions and prevents conflicting concurrent operations.

Customer Lifecycle:
    onboarding → active → paused → active (can re-activate)
                        → churned (terminal)

Pipeline Run:
    pending → running → staged → approved → published (happy path)
                      → failed (can retry → running)

Pipeline Steps:
    pending → running → success
                      → failed (can retry → pending → running)
                      → skipped
"""

from __future__ import annotations


class InvalidTransition(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, entity: str, current: str, target: str):
        self.entity = entity
        self.current = current
        self.target = target
        super().__init__(f"{entity}: cannot transition from '{current}' to '{target}'")


# --- Customer Lifecycle ---

CUSTOMER_TRANSITIONS: dict[str, set[str]] = {
    "onboarding": {"active", "paused", "archived", "churned"},
    "active":     {"paused", "archived", "churned"},
    "paused":     {"active", "archived", "churned"},
    "archived":   {"onboarding", "active"},  # can restore
    "churned":    set(),  # terminal state
}

def validate_customer_transition(current: str, target: str) -> bool:
    allowed = CUSTOMER_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransition("customer", current, target)
    return True


# --- Pipeline Run ---

RUN_TRANSITIONS: dict[str, set[str]] = {
    "pending":   {"running"},
    "running":   {"staged", "failed", "dry_run"},
    "staged":    {"approved", "running"},   # running = retry
    "approved":  {"published", "running"},  # running = re-publish
    "published": {"running"},               # running = re-run next month
    "failed":    {"running"},               # running = retry
    "dry_run":   {"running"},               # running = real run
}

def validate_run_transition(current: str, target: str) -> bool:
    allowed = RUN_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransition("run", current, target)
    return True


# --- Pipeline Step ---

STEP_TRANSITIONS: dict[str, set[str]] = {
    "pending":  {"running", "skipped"},
    "running":  {"success", "failed"},
    "success":  {"pending"},   # pending = re-run (retry resets to pending first)
    "failed":   {"pending"},   # pending = retry (reset then re-run)
    "skipped":  {"pending"},   # pending = un-skip
}

def validate_step_transition(current: str, target: str) -> bool:
    allowed = STEP_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransition("step", current, target)
    return True


# --- Concurrency Guard ---

def check_no_active_run(db, customer_id: str) -> bool:
    """Ensure no other run is currently active for this customer.

    Raises InvalidTransition if a run is already in progress.
    Returns True if safe to proceed.
    """
    cur = db.conn.execute(
        "SELECT id, status FROM runs WHERE customer_id = ? AND status = 'running' LIMIT 1",
        (customer_id,),
    )
    row = cur.fetchone()
    if row:
        raise InvalidTransition(
            f"customer:{customer_id}",
            f"run #{row['id']} is running",
            "new run",
        )
    return True
