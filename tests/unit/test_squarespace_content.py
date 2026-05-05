"""Tests for Squarespace content publisher (mocked Playwright)."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_content_recommendation.return_value = {
        "id": "rec-1",
        "customer_id": "downtown-dental",
        "rec_type": "blog_post",
        "title": "Benefits of Regular Checkups",
        "description": "Why regular dental visits matter.",
        "html_snippet": "<p>Regular checkups help prevent cavities.</p>",
        "category": "general",
        "status": "approved",
    }
    return db


@pytest.fixture
def publisher(mock_db):
    from geo_agent.publishers.squarespace_content import SquarespaceContentPublisher
    return SquarespaceContentPublisher(
        db=mock_db,
        customer_id="downtown-dental",
        email="admin@downtown.com",
        password_encrypted="encrypted_pass",
        site_url="https://downtown-dental.squarespace.com",
    )


class TestRecTypeDispatch:
    @pytest.mark.asyncio
    async def test_blog_post_calls_create_blog_draft(self, publisher, mock_db):
        with patch.object(publisher, 'create_blog_draft', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = "https://downtown-dental.squarespace.com/config/pages/blog/draft-1"
            result = await publisher.publish_recommendation("rec-1")
            assert result["ok"] is True
            assert "draft_url" in result
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_publishable_type_returns_error(self, publisher, mock_db):
        mock_db.get_content_recommendation.return_value = {
            "id": "rec-2",
            "customer_id": "downtown-dental",
            "rec_type": "expert_quote",
            "title": "Quote",
            "status": "approved",
        }
        result = await publisher.publish_recommendation("rec-2")
        assert result["ok"] is False
        assert "not publishable" in result["error"]

    @pytest.mark.asyncio
    async def test_non_approved_returns_error(self, publisher, mock_db):
        mock_db.get_content_recommendation.return_value = {
            "id": "rec-3",
            "customer_id": "downtown-dental",
            "rec_type": "blog_post",
            "title": "Draft Post",
            "status": "pending",
        }
        result = await publisher.publish_recommendation("rec-3")
        assert result["ok"] is False
        assert "must be 'approved'" in result["error"]

    @pytest.mark.asyncio
    async def test_not_found_returns_error(self, publisher, mock_db):
        mock_db.get_content_recommendation.return_value = None
        result = await publisher.publish_recommendation("rec-missing")
        assert result["ok"] is False
        assert "not found" in result["error"]


class TestCredentialEncryption:
    def test_encryption_roundtrip(self):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        f = Fernet(key)

        password = "my_secret_password"
        encrypted = f.encrypt(password.encode()).decode()
        decrypted = f.decrypt(encrypted.encode()).decode()
        assert decrypted == password

    def test_decrypt_password_requires_env_key(self, publisher):
        with patch.dict(os.environ, {"PRACTICERANK_ENCRYPTION_KEY": ""}, clear=False):
            with pytest.raises(RuntimeError, match="PRACTICERANK_ENCRYPTION_KEY"):
                publisher._decrypt_password()


class TestBatchPublish:
    @pytest.mark.asyncio
    async def test_batch_processes_all_recs(self, publisher, mock_db):
        with patch.object(publisher, 'publish_recommendation', new_callable=AsyncMock) as mock_pub:
            mock_pub.return_value = {"ok": True, "draft_url": "url", "rec_id": "rec-1"}
            results = await publisher.publish_batch(["rec-1", "rec-2", "rec-3"])
            assert len(results) == 3
            assert mock_pub.call_count == 3


class TestStatusTransitions:
    @pytest.mark.asyncio
    async def test_successful_publish_updates_platform_ids(self, publisher, mock_db):
        with patch.object(publisher, 'create_blog_draft', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = "https://site.squarespace.com/config/pages/blog/draft-1"
            await publisher.publish_recommendation("rec-1")
            mock_db.set_recommendation_platform_ids.assert_called_once_with(
                "rec-1", "", "https://site.squarespace.com/config/pages/blog/draft-1"
            )

    @pytest.mark.asyncio
    async def test_failed_publish_sets_error(self, publisher, mock_db):
        with patch.object(publisher, 'create_blog_draft', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = RuntimeError("Browser crashed")
            result = await publisher.publish_recommendation("rec-1")
            assert result["ok"] is False
            mock_db.set_recommendation_publish_error.assert_called_once()
