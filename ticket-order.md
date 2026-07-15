# Client Portal — Ticket Execution Order

Derived from the dependency table in `tickets.md`. Tickets 1 and 2 are already
marked complete, so this file shows what's unblocked *now* and how the rest
sequences from there.

## Status quo

- ✅ Ticket 1 — data-layer methods (`geo_agent/db.py`)
- ✅ Ticket 2 — client auth/session + portal shell

## Wave 1 — start now, fully parallel (4 tracks)

These have no unmet dependencies (1 and 2 are already done) and don't touch
each other's files, so all four can run at the same time:

| Ticket | Track | Why it's unblocked |
|---|---|---|
| 3 | Copy | Depends on nothing |
| 7 | Action Items | Depends only on 1, 2 |
| 10 | Full Reports | Depends only on 1, 2 |
| 11 | Admin invite panel | Depends only on 1 |

**Ticket 2a** (CSRF/cookie hardening) is also technically unblocked (depends
only on 2), but its status is "to be reviewed later, not yet approved for
build" — leave it out of active sequencing until that approval happens.

## Wave 2 — unlocked as each Wave-1 ticket lands (not a hard barrier)

Each of these only needs its *specific* predecessor, not all of Wave 1 — start
as soon as that one ticket is done rather than waiting for the whole wave:

| Ticket | Waits on | Can run parallel with |
|---|---|---|
| 4 | 3 | 8, 9, 12 |
| 8 | 7 | 4, 9, 12 |
| 9 | 7 | 4, 8, 12 (note: 9 depends on 7 only, *not* on 8 — the two can proceed independently of each other) |
| 12 | 11 | 4, 8, 9 |

## Wave 3 — pillar detail pages

| Ticket | Waits on | Can run parallel with |
|---|---|---|
| 5 | 4 | 6 |
| 6 | 4 | 5 |

Both 5 and 6 read the same frozen snapshot payload and only need 4 to be
done first — they don't depend on each other and can be built side-by-side
(different templates: `portal_pillar.html` variants for 4 pillars vs. the
AI Visibility page).

## Wave 4 — closing gate

| Ticket | Waits on |
|---|---|
| 13 | Everything, 2 through 12 |

Ticket 13 is a verification pass, not new feature work — it can't start
until all of 2–12 (every portal-facing ticket) is merged, including both
pillar-page tracks and the signup flow.

## Critical path

```
3 → 4 → 5 → 13
```

Ticket 5 is the largest single ticket (L) and sits behind both 3 and 4, then
gates 13. This is the longest chain and effectively sets the floor for how
fast the whole ticket set can finish, even with maximum parallelism
elsewhere. Everything off this path (7/8/9, 10, 11/12, and 6) has slack —
it can slip somewhat without delaying the overall finish, as long as it's
done before 13 starts.

## Full dependency graph

```
1 ✅ ──> 2 ✅ ──┬──> 3 ──┬──> 4 ──┬──> 5 ──┐
                │        │        │        │
                │        │        └──> 6 ──┤
                │        │                 │
                ├──> 7 ──┬──> 8 ───────────┤
                │        └──> 9 ───────────┤
                │                          │
                ├──> 10 ──────────────────┤
                │                          │
                └──> 11 ──> 12 ───────────┤
                                           │
                2a (on hold, not gating)   │
                                           v
                                          13
```

## Manual testing checkpoints (if built sequentially, one ticket at a time)

Every ticket already has its own "Manual verification" bullet in
`tickets.md`. The checkpoints below are the handful of spots where it's
worth stopping for a *deliberate*, slightly broader pass before moving on —
each one is a point where a bug would otherwise get baked into everything
built afterward, or where the ticket is a genuine inflection point (first
write path, first cross-cutting change, first full user lifecycle).

1. **After Ticket 2** (already done, but worth restating): confirm the
   session-exclusivity manual steps in `tickets.md:91` before building any
   content on top. Every later page trusts `client_login_required` and
   `session["client_customer_id"]` — a bug here is invisible until it
   silently leaks data across customers much later.

2. **After Ticket 4 (Overview page).** This is the *first* real content
   page and establishes the snapshot-loading pattern (`get_latest_report_snapshot`
   → parse `payload_json` → never recompute) that Tickets 5, 6, 7, and 10
   all copy. Stop here and manually confirm the numbers match the admin
   panel for a real customer before replicating the pattern four more
   times — a mistake in how the snapshot is loaded or fallback cadence is
   picked (weekly → monthly → quarterly) is cheap to fix once, expensive to
   fix in five templates.

3. **After Ticket 6 (all pillar pages done: 4, 5, 6).** Do a dedicated pass
   clicking from each Overview pillar bar into its detail page, for the
   same customer/snapshot, and diff the numbers — especially AI Visibility,
   since Ticket 6's entire point (resolved decision D3) is that it must
   match Overview byte-for-byte with no live re-query. This is the natural
   place to catch drift before Action Items and Reports get layered on.

4. **After Ticket 8 (approve/reject).** This is the *first write path* in
   the portal — everything before it (4, 5, 6, 7, 10) is read-only. Stop
   and cross-check with admin `/content-queue` immediately: confirm a
   portal approve/reject shows up correctly on the admin side and that the
   customer-ownership 404 check actually holds, before adding Ticket 9's
   preview route on top of the same rec-card flow.

5. **After Ticket 11 (admin invite panel), before starting Ticket 12.**
   Ticket 11 produces the signup-link format that Ticket 12 has to consume
   (`/portal/signup/<token>`). Manually generate a link and eyeball its
   shape before writing the page that parses it — cheaper to catch a
   format mismatch here than after both sides are built.

6. **After Ticket 12 (signup flow complete).** Run the full new-user
   lifecycle end to end once, by hand: staff creates a username (11) → copy
   the invite link → open it in a private window → set a password (12) →
   confirm auto-login lands on the now-fully-built `/portal/` (4) →log out
   → log back in → confirm the original invite link is rejected on reuse.
   This is the first point where every non-hardening ticket (1–12 minus 2a)
   has landed, so it's the last natural checkpoint before Ticket 13's
   formal end-to-end pass.

7. **Ticket 13 itself** is already the comprehensive final checkpoint —
   no additional pause needed after it.

If Ticket 2a (CSRF + secure cookies) gets approved and inserted into the
sequence, treat it as its own checkpoint regardless of where it lands: it's
the one ticket that touches *every existing form*, admin and portal alike,
so a dedicated regression pass across old admin pages (not just the new
portal ones) is warranted right after it, before continuing.
