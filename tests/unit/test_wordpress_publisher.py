"""Tests for WordPress publisher (geo_agent/publishers/wordpress.py)."""

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from geo_agent.publishers.wordpress import WordPressPublisher


@pytest.fixture
def publisher():
    return WordPressPublisher(
        site_url="https://example.com",
        api_key="test-api-key-123",
    )


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text or json.dumps(json_data or {})
    return resp


class TestInit:
    def test_strips_trailing_slash(self):
        pub = WordPressPublisher("https://example.com/", "key")
        assert pub.site_url == "https://example.com"
        assert pub.api_base == "https://example.com/wp-json/practicerank/v1"

    def test_sets_auth_header(self):
        pub = WordPressPublisher("https://example.com", "my-key")
        assert pub.client.headers["X-PracticeRank-Key"] == "my-key"


class TestHealthCheck:
    def test_success(self, publisher):
        publisher.client.get = MagicMock(return_value=_mock_response(200, {
            "status": "ok",
            "site_name": "Test Site",
            "wp_version": "6.7",
            "plugin_version": "2.0.0",
        }))
        result = publisher.health_check()
        assert result is not None
        assert result["status"] == "ok"
        assert result["site_name"] == "Test Site"
        publisher.client.get.assert_called_once_with(
            "https://example.com/wp-json/practicerank/v1/health"
        )

    def test_failure_returns_none(self, publisher):
        publisher.client.get = MagicMock(return_value=_mock_response(401, {"error": "unauthorized"}))
        assert publisher.health_check() is None

    def test_network_error_returns_none(self, publisher):
        publisher.client.get = MagicMock(side_effect=Exception("Connection refused"))
        assert publisher.health_check() is None


class TestGetSiteInfo:
    def test_success(self, publisher):
        publisher.client.get = MagicMock(return_value=_mock_response(200, {
            "pages": [{"id": 1, "title": "Home"}],
            "posts": [],
            "categories": ["Blog"],
        }))
        result = publisher.get_site_info()
        assert result is not None
        assert len(result["pages"]) == 1

    def test_failure(self, publisher):
        publisher.client.get = MagicMock(return_value=_mock_response(500))
        assert publisher.get_site_info() is None


class TestPushSchema:
    def test_global_schemas(self, publisher):
        schemas = [{"@type": "LocalBusiness", "name": "Test Dental"}]
        publisher.client.post = MagicMock(return_value=_mock_response(200, {
            "updated": ["global"],
        }))
        result = publisher.push_schema(global_schemas=schemas)
        assert result is not None
        assert "global" in result["updated"]

        call_args = publisher.client.post.call_args
        assert call_args[1]["json"]["global"] == schemas

    def test_page_schemas(self, publisher):
        page_schemas = {"services": [{"@type": "MedicalProcedure"}]}
        publisher.client.post = MagicMock(return_value=_mock_response(200, {"updated": ["pages"]}))
        result = publisher.push_schema(page_schemas=page_schemas)
        assert result is not None

    def test_empty_schemas_returns_none(self, publisher):
        assert publisher.push_schema() is None

    def test_failure(self, publisher):
        publisher.client.post = MagicMock(return_value=_mock_response(500, text="Server Error"))
        result = publisher.push_schema(global_schemas=[{"@type": "Test"}])
        assert result is None


class TestPushContent:
    def test_create_post(self, publisher):
        publisher.client.post = MagicMock(return_value=_mock_response(200, {
            "post_id": 42,
            "url": "https://example.com/test-post/",
            "slug": "test-post",
            "post_type": "post",
            "publish_status": "draft",
        }))
        result = publisher.push_content(
            title="Test Post",
            content_html="<p>Hello world</p>",
            slug="test-post",
            category="Blog",
            meta_description="A test post",
        )
        assert result is not None
        assert result["post_id"] == 42
        assert result["publish_status"] == "draft"

        payload = publisher.client.post.call_args[1]["json"]
        assert payload["title"] == "Test Post"
        assert payload["content"] == "<p>Hello world</p>"
        assert payload["slug"] == "test-post"
        assert payload["category"] == "Blog"
        assert payload["meta_description"] == "A test post"

    def test_create_page(self, publisher):
        publisher.client.post = MagicMock(return_value=_mock_response(200, {
            "post_id": 10,
            "post_type": "page",
            "url": "https://example.com/about/",
        }))
        result = publisher.push_content(
            title="About Us",
            content_html="<p>About</p>",
            content_type="page",
        )
        assert result is not None
        assert result["post_type"] == "page"

    def test_duplicate_slug_triggers_update(self, publisher):
        conflict_resp = _mock_response(409, {
            "code": "slug_exists",
            "data": {"existing_id": 99},
        })
        update_resp = _mock_response(200, {
            "post_id": 99,
            "url": "https://example.com/existing/",
        })
        publisher.client.post = MagicMock(return_value=conflict_resp)
        publisher.client.put = MagicMock(return_value=update_resp)

        result = publisher.push_content(
            title="Updated Post",
            content_html="<p>Updated</p>",
        )
        assert result is not None
        assert result["post_id"] == 99
        publisher.client.put.assert_called_once()

    def test_optional_fields_excluded_when_empty(self, publisher):
        publisher.client.post = MagicMock(return_value=_mock_response(200, {"post_id": 1}))
        publisher.push_content(title="Minimal", content_html="<p>Hi</p>")
        payload = publisher.client.post.call_args[1]["json"]
        assert "slug" not in payload
        assert "tags" not in payload
        assert "featured_image_url" not in payload

    def test_network_error(self, publisher):
        publisher.client.post = MagicMock(side_effect=Exception("timeout"))
        assert publisher.push_content("Title", "<p>Body</p>") is None


class TestUpdateContent:
    def test_update_post(self, publisher):
        publisher.client.put = MagicMock(return_value=_mock_response(200, {
            "post_id": 42,
            "url": "https://example.com/updated/",
        }))
        result = publisher.update_content(
            post_id=42,
            title="New Title",
            content_html="<p>New content</p>",
        )
        assert result is not None
        assert result["post_id"] == 42
        publisher.client.put.assert_called_once_with(
            "https://example.com/wp-json/practicerank/v1/content/42",
            json={"title": "New Title", "content": "<p>New content</p>"},
        )

    def test_partial_update(self, publisher):
        publisher.client.put = MagicMock(return_value=_mock_response(200, {"post_id": 5}))
        publisher.update_content(post_id=5, status="publish")
        payload = publisher.client.put.call_args[1]["json"]
        assert payload == {"status": "publish"}
        assert "title" not in payload

    def test_failure(self, publisher):
        publisher.client.put = MagicMock(return_value=_mock_response(404))
        assert publisher.update_content(post_id=999, title="X") is None


class TestPushFiles:
    def test_push_llms_txt(self, publisher):
        publisher.client.post = MagicMock(return_value=_mock_response(200, {
            "written": ["llms.txt"],
        }))
        result = publisher.push_files(llms_txt="# Test Practice\n> AI-optimized")
        assert result is not None
        assert "llms.txt" in result["written"]
        payload = publisher.client.post.call_args[1]["json"]
        assert "llms.txt" in payload

    def test_push_multiple_files(self, publisher):
        publisher.client.post = MagicMock(return_value=_mock_response(200, {
            "written": ["llms.txt", "llms-full.txt", "robots.txt"],
        }))
        result = publisher.push_files(
            llms_txt="# llms",
            llms_full_txt="# full",
            robots_txt="User-agent: *\nAllow: /",
        )
        assert result is not None
        assert len(result["written"]) == 3

    def test_empty_returns_none(self, publisher):
        assert publisher.push_files() is None

    def test_failure(self, publisher):
        publisher.client.post = MagicMock(return_value=_mock_response(500))
        assert publisher.push_files(llms_txt="test") is None


class TestPublishApprovedContent:
    def test_publishes_approved_recs(self, publisher):
        mock_db = MagicMock()
        mock_db.get_content_recommendations.return_value = [
            {
                "id": "rec1",
                "rec_type": "blog_post",
                "title": "Best Dental Implants Guide",
                "generated_content": "<p>Dental implants are...</p>",
                "slug": "best-dental-implants",
                "meta_description": "Guide to dental implants",
                "category": "Blog",
                "tags": ["implants", "dental"],
            },
        ]
        publisher.client.post = MagicMock(return_value=_mock_response(200, {
            "post_id": 55,
            "url": "https://example.com/best-dental-implants/",
            "publish_status": "draft",
        }))

        results = publisher.publish_approved_content(mock_db, "cust-123")
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["rec_id"] == "rec1"

        # Verify DB was updated
        mock_db.update_content_recommendation.assert_called_once()
        update_args = mock_db.update_content_recommendation.call_args[0]
        assert update_args[0] == "rec1"
        assert update_args[1]["status"] == "published"
        assert update_args[1]["wp_post_id"] == 55

    def test_no_approved_content(self, publisher):
        mock_db = MagicMock()
        mock_db.get_content_recommendations.return_value = []
        results = publisher.publish_approved_content(mock_db, "cust-123")
        assert results == []

    def test_skips_empty_content(self, publisher):
        mock_db = MagicMock()
        mock_db.get_content_recommendations.return_value = [
            {"id": "rec1", "rec_type": "blog_post", "title": "Empty", "generated_content": ""},
        ]
        results = publisher.publish_approved_content(mock_db, "cust-123")
        assert len(results) == 0

    def test_skips_non_publishable_types(self, publisher):
        mock_db = MagicMock()
        mock_db.get_content_recommendations.return_value = [
            {"id": "rec1", "rec_type": "meta_update", "title": "Meta Fix"},
        ]
        results = publisher.publish_approved_content(mock_db, "cust-123")
        assert len(results) == 0

    def test_failed_push_does_not_update_db(self, publisher):
        mock_db = MagicMock()
        mock_db.get_content_recommendations.return_value = [
            {
                "id": "rec1",
                "rec_type": "blog_post",
                "title": "Failed Post",
                "generated_content": "<p>Content</p>",
            },
        ]
        publisher.client.post = MagicMock(return_value=_mock_response(500))

        results = publisher.publish_approved_content(mock_db, "cust-123")
        assert len(results) == 1
        assert results[0]["success"] is False
        mock_db.update_content_recommendation.assert_not_called()


class TestFullSync:
    def test_runs_all_steps(self, publisher):
        mock_db = MagicMock()
        mock_db.get_content_recommendations.return_value = []

        publisher.push_schema = MagicMock(return_value={"updated": ["global"]})
        publisher.push_files = MagicMock(return_value={"written": ["llms.txt"]})
        publisher.publish_approved_content = MagicMock(return_value=[])

        result = publisher.full_sync(
            db=mock_db,
            customer_id="cust-1",
            customer={"name": "Test"},
            llms_txt="# Test",
            global_schemas=[{"@type": "LocalBusiness"}],
        )

        assert result["schema"] == {"updated": ["global"]}
        assert result["files"] == {"written": ["llms.txt"]}
        assert result["content"] == []
        publisher.push_schema.assert_called_once()
        publisher.push_files.assert_called_once()
        publisher.publish_approved_content.assert_called_once()

    def test_skips_content_when_disabled(self, publisher):
        mock_db = MagicMock()
        publisher.push_schema = MagicMock(return_value=None)
        publisher.push_files = MagicMock(return_value=None)
        publisher.publish_approved_content = MagicMock()

        publisher.full_sync(
            db=mock_db,
            customer_id="cust-1",
            customer={},
            publish_content=False,
        )
        publisher.publish_approved_content.assert_not_called()
