"""Tests for the staging and approval flow."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from geo_agent.staging import StagingManager


@pytest.fixture
def staging(tmp_path):
    return StagingManager(data_dir=str(tmp_path))


@pytest.fixture
def staged_customer(staging):
    """Stage some files for a test customer."""
    staging.stage_changes("test-dental", {
        "llms.txt": "# Test Practice\n> AI information about Test Practice",
        "schema.html": '<script type="application/ld+json">{"@type":"Dentist"}</script>',
        "robots.txt": "User-agent: *\nAllow: /",
    })
    return "test-dental"


class TestStageChanges:
    def test_stage_creates_files(self, staging, tmp_path):
        staging.stage_changes("test-dental", {
            "llms.txt": "test content",
            "robots.txt": "User-agent: *",
        })

        stage_path = tmp_path / "staging" / "test-dental"
        assert stage_path.exists()
        assert (stage_path / "llms.txt").read_text() == "test content"
        assert (stage_path / "robots.txt").read_text() == "User-agent: *"

    def test_stage_creates_metadata(self, staging, tmp_path):
        staging.stage_changes("test-dental", {"llms.txt": "test"})

        meta_path = tmp_path / "staging" / "test-dental" / "_meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["customer_id"] == "test-dental"
        assert meta["approved"] is False
        assert "llms.txt" in meta["files"]


class TestIsStaged:
    def test_is_staged(self, staging, staged_customer):
        assert staging.is_staged("test-dental") is True
        assert staging.is_staged("nonexistent") is False


class TestDiffReport:
    def test_diff_new_files(self, staging, staged_customer):
        report = staging.generate_diff_report("test-dental")
        assert "test-dental" in report
        assert "llms.txt (new)" in report
        assert "schema.html (new)" in report

    def test_diff_modified_files(self, staging, staged_customer, tmp_path):
        # Create a "published" version
        published_path = tmp_path / "published" / "test-dental"
        published_path.mkdir(parents=True)
        (published_path / "llms.txt").write_text("# Old content")

        report = staging.generate_diff_report("test-dental")
        assert "llms.txt (modified)" in report
        assert "diff" in report.lower()

    def test_diff_no_changes(self, staging, staged_customer, tmp_path):
        # Create identical published version
        published_path = tmp_path / "published" / "test-dental"
        published_path.mkdir(parents=True)
        (published_path / "llms.txt").write_text(
            "# Test Practice\n> AI information about Test Practice"
        )

        report = staging.generate_diff_report("test-dental")
        assert "No changes" in report

    def test_diff_nonexistent_customer(self, staging):
        report = staging.generate_diff_report("nonexistent")
        assert "No staged changes" in report


class TestApproval:
    def test_approve_changes(self, staging, staged_customer):
        assert staging.is_approved("test-dental") is False
        staging.approve_changes("test-dental")
        assert staging.is_approved("test-dental") is True

    def test_approve_nonexistent(self, staging):
        assert staging.approve_changes("nonexistent") is False


class TestPublish:
    def test_publish_approved(self, staging, staged_customer, tmp_path):
        staging.approve_changes("test-dental")
        published = staging.publish_staged("test-dental")

        assert len(published) == 3
        assert "llms.txt" in published
        assert "schema.html" in published

        # Check published directory
        published_path = tmp_path / "published" / "test-dental"
        assert published_path.exists()
        assert (published_path / "llms.txt").exists()

        # Staging should be cleaned up
        assert not staging.is_staged("test-dental")

    def test_publish_unapproved_fails(self, staging, staged_customer):
        published = staging.publish_staged("test-dental")
        assert len(published) == 0

    def test_publish_nonexistent(self, staging):
        published = staging.publish_staged("nonexistent")
        assert len(published) == 0


class TestGetStagedFiles:
    def test_get_staged_files(self, staging, staged_customer):
        files = staging.get_staged_files("test-dental")
        assert len(files) == 3
        assert "llms.txt" in files

    def test_get_staged_files_empty(self, staging):
        files = staging.get_staged_files("nonexistent")
        assert len(files) == 0


class TestCleanup:
    def test_cleanup_staging(self, staging, staged_customer, tmp_path):
        staging.cleanup_staging("test-dental")
        assert not staging.is_staged("test-dental")
        assert not (tmp_path / "staging" / "test-dental").exists()
