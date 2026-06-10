"""Smoke tests for content prompt assembly — catches f-string/format bugs."""

from __future__ import annotations

import pytest

from geo_agent.config import Customer
from geo_agent.content_recommender import (
    SYSTEM_PROMPTS,
    _build_user_prompt,
    CONTENT_OUTPUT_SCHEMA,
)


def _customer(bt: str) -> Customer:
    return Customer(
        id="c1", name="Test Biz", domain="t.com", city="Austin", state="TX",
        business_type=bt, services=["thing one", "thing two"],
    )


# Every business type, plus unknown (falls back to the generic prompt).
@pytest.mark.parametrize(
    "bt",
    list(SYSTEM_PROMPTS.keys()) + ["legal", "medical", "ecommerce", "totally_unknown"],
)
def test_build_user_prompt_renders_for_every_business_type(bt):
    """_build_user_prompt must not raise (e.g. f-string format errors) and must
    instruct the model to return the {recommendations: [...]} object."""
    prompt = _build_user_prompt(
        customer=_customer(bt),
        business_type=bt,
        page_summaries=[],
        relevant_stats=[],
        existing_summary="",
        current_month="June 2026",
    )
    assert isinstance(prompt, str) and prompt
    assert '{"recommendations"' in prompt  # literal braces survived the f-string


def test_output_schema_shape():
    props = CONTENT_OUTPUT_SCHEMA["properties"]
    assert props["recommendations"]["type"] == "array"
    item = props["recommendations"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"].keys())
    assert item["properties"]["priority"]["enum"] == [1, 2, 3, 4, 5]
