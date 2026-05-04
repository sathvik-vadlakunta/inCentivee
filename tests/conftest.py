"""Shared fixtures for the GEO Agent test suite."""

from __future__ import annotations

import json
import math

import pytest

from geo_agent.config import Customer, Provider
from geo_agent.crawler import PageData
from geo_agent.google_places import VerifiedBusinessData, CompetitorData


@pytest.fixture
def sample_customer() -> Customer:
    """Hilltop Family Dental — realistic first customer."""
    return Customer(
        id="hilltop-dental",
        name="Hilltop Family Dental",
        domain="hilltopdental.com",
        city="Austin",
        state="TX",
        address="4500 Medical Pkwy, Suite 200",
        phone="(512) 555-0199",
        zip_code="78756",
        webflow_site_id="site_abc123",
        webflow_api_key="wf-key-test",
        specialties=["General Dentistry", "Cosmetic Dentistry", "Dental Implants"],
        brand_voice="Professional and warm, emphasizing patient comfort",
        providers=[
            Provider(
                name="Dr. David Gallup",
                credentials="DDS",
                specialties=["Implants", "Cosmetic"],
                years_experience=27,
                bio="Board-certified with over 27 years of experience in implant and cosmetic dentistry.",
            ),
            Provider(
                name="Dr. Sarah Chen",
                credentials="DMD",
                specialties=["Orthodontics", "Pediatric"],
                years_experience=12,
                bio="Specializes in Invisalign and pediatric dentistry.",
            ),
        ],
        competitors=["waldendental.com", "riverrockdentalfamily.com"],
        insurance_accepted=["Delta Dental", "Aetna", "Cigna", "MetLife"],
        hours="Mon-Fri 8am-5pm, Sat 9am-2pm",
        emergency_available=True,
    )


@pytest.fixture
def second_customer() -> Customer:
    """Bright Smile Dentistry — fictional second practice for multi-customer tests."""
    return Customer(
        id="bright-smile",
        name="Bright Smile Dentistry",
        domain="brightsmile.com",
        city="Denver",
        state="CO",
        address="1200 16th St Mall, Suite 300",
        phone="(303) 555-0234",
        zip_code="80202",
        webflow_site_id="site_def456",
        webflow_api_key="wf-key-test-2",
        specialties=["General Dentistry", "Sedation Dentistry"],
        brand_voice="Friendly and approachable",
        providers=[
            Provider(
                name="Dr. James Wright",
                credentials="DDS",
                specialties=["Sedation", "General"],
                years_experience=15,
            ),
        ],
        competitors=["denversmiles.com"],
        insurance_accepted=["Delta Dental", "United Healthcare"],
        hours="Mon-Fri 9am-6pm",
        emergency_available=False,
    )


@pytest.fixture
def sample_pages() -> list[PageData]:
    """Five realistic PageData objects for testing generators."""
    return [
        PageData(
            id="page-home",
            url="https://hilltopdental.com/",
            title="Hilltop Family Dental",
            content="Welcome to Hilltop Family Dental in Austin TX. We provide comprehensive dental care including general dentistry, cosmetic procedures, and dental implants. Our experienced team led by Dr. David Gallup has been serving the Austin community for over 27 years.",
            category="home",
            slug="",
            html="<h1>Welcome to Hilltop Family Dental</h1><p>We provide comprehensive dental care...</p>",
        ),
        PageData(
            id="page-implants",
            url="https://hilltopdental.com/services/dental-implants",
            title="Dental Implants",
            content="Dental implants are the gold standard for replacing missing teeth. At Hilltop Family Dental, Dr. Gallup has placed over 3,000 implants using the latest guided surgery technology. Single tooth implants start at $3,500. Full arch implant procedures available with same-day temporary teeth.",
            category="service",
            slug="services/dental-implants",
            html="<h1>Dental Implants</h1><p>Dental implants are the gold standard...</p>",
        ),
        PageData(
            id="page-cosmetic",
            url="https://hilltopdental.com/services/cosmetic-dentistry",
            title="Cosmetic Dentistry",
            content="Transform your smile with our cosmetic dentistry services in Austin TX. We offer porcelain veneers, professional teeth whitening, and complete smile makeovers. Dr. Gallup and Dr. Chen create personalized treatment plans for every patient.",
            category="service",
            slug="services/cosmetic-dentistry",
            html="<h1>Cosmetic Dentistry</h1><p>Transform your smile...</p>",
        ),
        PageData(
            id="page-about",
            url="https://hilltopdental.com/about",
            title="About Our Team",
            content="Meet the team at Hilltop Family Dental. Dr. David Gallup DDS has 27 years of experience specializing in implants and cosmetic dentistry. Dr. Sarah Chen DMD brings 12 years of expertise in orthodontics and pediatric care. Together they lead a team dedicated to patient comfort.",
            category="about",
            slug="about",
            html="<h1>About Our Team</h1><p>Meet the team...</p>",
        ),
        PageData(
            id="page-contact",
            url="https://hilltopdental.com/contact",
            title="Contact Us",
            content="Contact Hilltop Family Dental at (512) 555-0199. Located at 4500 Medical Pkwy Suite 200 Austin TX 78756. Office hours Monday through Friday 8am to 5pm and Saturday 9am to 2pm. Walk-ins welcome for emergencies.",
            category="contact",
            slug="contact",
            html="<h1>Contact Us</h1><p>Contact Hilltop Family Dental...</p>",
        ),
    ]


@pytest.fixture
def fake_embedding():
    """Factory returning deterministic 1024-dim vectors from a seed."""
    def _make(seed: int = 0) -> list[float]:
        return [math.sin(seed + i) * 0.1 for i in range(1024)]
    return _make


@pytest.fixture
def fake_analysis_response() -> dict:
    """Canned Claude analysis response matching expected JSON shape."""
    return {
        "faq_entries": {
            "https://hilltopdental.com/services/dental-implants": [
                {"question": "How much do dental implants cost in Austin?", "answer": "Single tooth implants at Hilltop Family Dental start at $3,500. Full arch procedures are also available."},
                {"question": "How long does a dental implant procedure take?", "answer": "Most single implants are placed in one visit. Dr. Gallup uses guided surgery for precise placement."},
                {"question": "Does insurance cover dental implants in Austin TX?", "answer": "Many plans cover a portion of implant costs. Hilltop Family Dental accepts Delta Dental, Aetna, Cigna, and MetLife."},
                {"question": "Am I a candidate for dental implants?", "answer": "Most adults with healthy gums are candidates. Dr. Gallup offers free implant consultations."},
            ],
        },
        "content_gaps": [
            {"title": "Emergency Dentist Austin TX", "slug": "emergency-dentist-austin", "description": "Dedicated emergency page targeting 'emergency dentist Austin' searches. Should cover same-day appointments, after-hours availability, and common emergencies."},
            {"title": "Dental Implant Cost Austin", "slug": "dental-implant-cost-austin", "description": "Cost-focused landing page for price-comparison searches. Include ranges, financing, and insurance info."},
        ],
        "service_descriptions": {
            "Dental Implants": "Full-arch and single-tooth dental implants with same-day options. Dr. Gallup has placed 3,000+ implants in Austin TX.",
            "Cosmetic Dentistry": "Veneers, whitening, and smile makeovers by Dr. Gallup and Dr. Chen in Austin TX.",
        },
        "priority_actions": [
            "Create a dedicated emergency dentist page targeting 'emergency dentist Austin TX'",
            "Add FAQ schema to all service pages (4-5 questions each)",
            "Create dental implant cost page with pricing ranges and financing options",
            "Add expert quotes from Dr. Gallup on each service page",
            "Update Google Business Profile with weekly posts",
        ],
    }


@pytest.fixture
def customers_json_file(tmp_path, sample_customer, monkeypatch):
    """Write a temp customers.json for load_customers() tests.

    NOTE: webflow_api_key is NOT stored in JSON (security fix).
    It's loaded from WEBFLOW_KEY_<ID> environment variable.
    """
    data = {
        "customers": [
            {
                "id": sample_customer.id,
                "name": sample_customer.name,
                "domain": sample_customer.domain,
                "city": sample_customer.city,
                "state": sample_customer.state,
                "address": sample_customer.address,
                "phone": sample_customer.phone,
                "zip_code": sample_customer.zip_code,
                "webflow_site_id": sample_customer.webflow_site_id,
                "specialties": sample_customer.specialties,
                "brand_voice": sample_customer.brand_voice,
                "providers": [
                    {
                        "name": p.name,
                        "credentials": p.credentials,
                        "specialties": p.specialties,
                        "years_experience": p.years_experience,
                        "bio": p.bio,
                    }
                    for p in sample_customer.providers
                ],
                "competitors": sample_customer.competitors,
                "insurance_accepted": sample_customer.insurance_accepted,
                "hours": sample_customer.hours,
                "emergency_available": sample_customer.emergency_available,
            }
        ]
    }
    # Set the Webflow key as an env var (the secure way)
    env_key = f"WEBFLOW_KEY_{sample_customer.id.upper().replace('-', '_')}"
    monkeypatch.setenv(env_key, sample_customer.webflow_api_key)
    path = tmp_path / "customers.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def sample_content_recommendation() -> dict:
    """A sample content recommendation matching the DB schema."""
    return {
        "id": "rec-test-001",
        "customer_id": "hilltop-dental",
        "rec_type": "blog_post",
        "target_page": "new",
        "title": "5 Signs You Need a Dental Implant",
        "description": "Educational blog post targeting 'dental implant signs' keyword cluster.",
        "html_snippet": "<h2>5 Signs You Need a Dental Implant</h2><p>Missing teeth can affect more than your smile...</p><h3>1. You have a missing tooth</h3><p>Even a single missing tooth can lead to bone loss.</p>",
        "priority": 2,
        "category": "implants",
        "status": "approved",
        "ai_impact_reason": "Targets 1,200 monthly searches with low competition.",
    }


@pytest.fixture
def sample_verified_data() -> VerifiedBusinessData:
    """Verified Google Places data for Hilltop Family Dental."""
    return VerifiedBusinessData(
        place_id="ChIJtest123",
        name="Hilltop Family Dental",
        address="4500 Medical Pkwy, Suite 200, Austin, TX 78756",
        city="Austin",
        state="TX",
        zip_code="78756",
        phone="(512) 555-0199",
        rating=4.7,
        review_count=156,
        website="https://hilltopdental.com",
        lat=30.3100,
        lng=-97.7400,
        business_status="OPERATIONAL",
        domain_match=True,
        name_match=True,
        match_confidence="high",
    )


@pytest.fixture
def sample_competitors() -> list[CompetitorData]:
    """Nearby competitor dental practices."""
    return [
        CompetitorData(
            name="Walden Dental",
            place_id="ChIJwalden",
            rating=4.5,
            review_count=200,
            address="1234 Lamar Blvd, Austin, TX 78756",
        ),
        CompetitorData(
            name="River Rock Dental Family",
            place_id="ChIJriverrock",
            rating=4.2,
            review_count=89,
            address="5678 Burnet Rd, Austin, TX 78757",
        ),
    ]
