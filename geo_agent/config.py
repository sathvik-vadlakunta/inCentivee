"""Customer configuration loading and validation."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Provider:
    name: str
    credentials: str  # e.g. "DDS", "DMD"
    specialties: list[str] = field(default_factory=list)
    years_experience: int | None = None
    bio: str = ""


@dataclass
class Customer:
    id: str
    name: str
    domain: str
    city: str
    state: str
    address: str = ""
    phone: str = ""
    zip_code: str = ""
    platform: str = "webflow"  # webflow/squarespace/wordpress/generic
    business_type: str = "practice"  # practice/technology/product/service
    webflow_site_id: str = ""
    webflow_api_key: str = ""
    specialties: list[str] = field(default_factory=list)
    brand_voice: str = "Professional and warm"
    providers: list[Provider] = field(default_factory=list)
    competitors: list[str] = field(default_factory=list)
    insurance_accepted: list[str] = field(default_factory=list)
    hours: str = ""
    emergency_available: bool = False
    business_type: str = "practice"  # practice/technology/product/service

    @classmethod
    def from_dict(cls, data: dict) -> Customer:
        providers = [Provider(**p) for p in data.pop("providers", [])]
        customer = cls(**data, providers=providers)
        # Load Webflow API key from secrets manager, NEVER from JSON
        from geo_agent.secrets import get_secrets
        secrets = get_secrets()
        customer.webflow_api_key = secrets.get_customer_secret(customer.id, "WEBFLOW_KEY")
        if customer.webflow_api_key:
            logger.info(f"Loaded Webflow key for {customer.id} from secrets manager")
        else:
            logger.warning(f"No Webflow key found for {customer.id}")
        return customer


def load_customers(config_path: str | None = None) -> list[Customer]:
    """Load customer configs from JSON file.

    SECURITY: Customer JSON contains only non-secret data (name, address, etc).
    All API keys/tokens are loaded from environment variables per customer.
    """
    path = config_path or os.environ.get(
        "CUSTOMER_CONFIG_PATH", "/app/data/customers.json"
    )
    config_file = Path(path)
    if not config_file.exists():
        raise FileNotFoundError(f"Customer config not found: {path}")

    with open(config_file) as f:
        data = json.load(f)

    # Warn if any customer still has a webflow_api_key in JSON (legacy)
    for c in data["customers"]:
        if c.get("webflow_api_key"):
            logger.warning(
                f"SECURITY: Customer '{c['id']}' has webflow_api_key in JSON file! "
                "Remove it and set the WEBFLOW_KEY_* environment variable instead."
            )
            del c["webflow_api_key"]

    return [Customer.from_dict(c) for c in data["customers"]]
