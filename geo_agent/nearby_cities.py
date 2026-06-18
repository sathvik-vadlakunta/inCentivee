"""Nearby-cities / service-area helper for the Local Relevancy Engine.

Given a customer's city, find nearby towns within a ~25-minute drive (proxied by
a straight-line radius) ranked by population — the candidate cities for
service-area pages and GBP service-area config.

Design: the ranking/filtering core is pure and fully tested. The two network
steps (geocode the city, fetch candidate places) are thin and mockable:
  - geocode: OpenStreetMap Nominatim (no key).
  - candidates: GeoNames (free, needs GEONAMES_USERNAME) — returns nearby
    populated places with population. Without it, this returns [] and the engine
    falls back to any service_areas already set on the customer.

~25-min drive ≈ 15-20 mi in mixed suburban driving; default radius 18 mi.
A drive-time matrix can replace the radius later without changing callers.
"""

from __future__ import annotations

import logging
import math
import os

import httpx

logger = logging.getLogger(__name__)

DEFAULT_RADIUS_MILES = 18.0
DEFAULT_LIMIT = 8
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_GEONAMES = "http://api.geonames.org/findNearbyPlaceNameJSON"
_UA = "PracticeRank/1.0 (local-relevancy)"


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two lat/lng points."""
    r = 3958.8  # earth radius, miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def filter_rank_cities(
    center_lat: float,
    center_lon: float,
    candidates: list[dict],
    *,
    origin_name: str = "",
    max_miles: float = DEFAULT_RADIUS_MILES,
    limit: int = DEFAULT_LIMIT,
) -> list[str]:
    """Pure: filter candidates within radius, drop the origin, rank by population.

    Each candidate: {"name", "lat", "lon", "population"}. Returns city names.
    """
    origin = origin_name.strip().lower()
    scored = []
    seen: set[str] = set()
    for c in candidates:
        name = (c.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key == origin or key in seen:
            continue
        try:
            dist = haversine_miles(center_lat, center_lon, float(c["lat"]), float(c["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        if dist > max_miles:
            continue
        seen.add(key)
        scored.append((int(c.get("population") or 0), -dist, name))
    # Highest population first; closer breaks ties.
    scored.sort(reverse=True)
    return [name for _, _, name in scored[:limit]]


def geocode_city(city: str, state: str = "", *, client: httpx.Client | None = None) -> tuple[float, float] | None:
    """Geocode "City, State" via Nominatim. Returns (lat, lon) or None."""
    if not city:
        return None
    q = ", ".join(p for p in (city, state, "USA") if p)
    owns = client is None
    client = client or httpx.Client(timeout=15.0, headers={"User-Agent": _UA})
    try:
        resp = client.get(_NOMINATIM, params={"q": q, "format": "json", "limit": 1})
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as exc:  # noqa: BLE001
        logger.info("geocode failed for %r: %s", q, exc)
        return None
    finally:
        if owns:
            client.close()


def fetch_nearby_candidates(
    lat: float, lon: float, radius_miles: float = DEFAULT_RADIUS_MILES,
    *, client: httpx.Client | None = None,
) -> list[dict]:
    """Fetch nearby populated places via GeoNames. [] if GEONAMES_USERNAME unset."""
    username = os.environ.get("GEONAMES_USERNAME", "")
    if not username:
        logger.info("GEONAMES_USERNAME not set — nearby-city discovery disabled")
        return []
    owns = client is None
    client = client or httpx.Client(timeout=15.0, headers={"User-Agent": _UA})
    try:
        resp = client.get(_GEONAMES, params={
            "lat": lat, "lng": lon,
            "radius": min(round(radius_miles * 1.60934), 300),  # km, GeoNames caps at 300
            "maxRows": 50, "cities": "cities1000",
            "username": username,
        })
        resp.raise_for_status()
        out = []
        for g in resp.json().get("geonames", []):
            out.append({
                "name": g.get("name") or g.get("toponymName"),
                "lat": g.get("lat"), "lon": g.get("lng"),
                "population": g.get("population") or 0,
            })
        return out
    except Exception as exc:  # noqa: BLE001
        logger.info("GeoNames lookup failed: %s", exc)
        return []
    finally:
        if owns:
            client.close()


def nearby_cities(
    city: str, state: str = "",
    *, limit: int = DEFAULT_LIMIT, max_miles: float = DEFAULT_RADIUS_MILES,
) -> list[str]:
    """End-to-end: geocode the city, fetch candidates, filter+rank. [] on any miss."""
    geo = geocode_city(city, state)
    if not geo:
        return []
    lat, lon = geo
    candidates = fetch_nearby_candidates(lat, lon, max_miles)
    return filter_rank_cities(lat, lon, candidates, origin_name=city, max_miles=max_miles, limit=limit)


def ensure_service_areas(db, customer_id: str) -> list[str]:
    """Return the customer's service-area cities, computing + persisting if empty.

    If the customer already has service_areas, returns them unchanged. Otherwise
    tries to discover them from the city; persists whatever it finds (may be []).
    """
    import json

    customer = db.get_customer(customer_id)
    if not customer:
        return []
    existing = customer.get("service_areas") or []
    if existing:
        return existing
    discovered = nearby_cities(customer.get("city", ""), customer.get("state", ""))
    if discovered:
        db.update_customer(customer_id, service_areas=json.dumps(discovered))
    return discovered
