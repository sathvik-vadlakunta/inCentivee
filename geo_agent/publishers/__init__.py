"""Publisher factory for platform-aware content publishing."""

from __future__ import annotations


def get_content_publisher(platform: str, db, customer_id: str, **kwargs):
    """Return the appropriate content publisher for a platform.

    Returns None for platforms that only support DOCX download.
    """
    if platform == "webflow":
        from geo_agent.publishers.webflow import WebflowPublisher
        from geo_agent.publishers.webflow_content import WebflowContentPublisher
        publisher = WebflowPublisher(
            api_key=kwargs.get("api_key", ""),
            site_id=kwargs.get("site_id", ""),
        )
        return WebflowContentPublisher(publisher, db, customer_id)
    elif platform == "squarespace":
        from geo_agent.publishers.squarespace_content import SquarespaceContentPublisher
        return SquarespaceContentPublisher(
            db=db,
            customer_id=customer_id,
            email=kwargs.get("email", ""),
            password_encrypted=kwargs.get("password_encrypted", ""),
            site_url=kwargs.get("site_url", ""),
        )
    return None
