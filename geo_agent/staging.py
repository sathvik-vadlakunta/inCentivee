"""Staging environment and approval flow for generated content.

Before publishing anything, the agent stages all files and creates a diff
report the client can review and approve.
"""

from __future__ import annotations

import difflib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class StagingManager:
    """Manage staging, diffing, and approval of generated content."""

    def __init__(self, data_dir: str | None = None):
        self.base_dir = Path(data_dir or "/app/data")
        self.staging_dir = self.base_dir / "staging"
        self.published_dir = self.base_dir / "published"

    def stage_changes(self, customer_id: str, files: dict[str, str]) -> Path:
        """Save generated files to the staging directory.

        Args:
            customer_id: Customer identifier.
            files: Dict of filename -> content (e.g. {"llms.txt": "...", "schema.html": "..."}).

        Returns:
            Path to the staging directory for this customer.
        """
        stage_path = self.staging_dir / customer_id
        stage_path.mkdir(parents=True, exist_ok=True)

        for filename, content in files.items():
            (stage_path / filename).write_text(content)

        # Write staging metadata
        meta = {
            "customer_id": customer_id,
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "files": list(files.keys()),
            "approved": False,
        }
        (stage_path / "_meta.json").write_text(json.dumps(meta, indent=2))

        logger.info(f"Staged {len(files)} files for {customer_id}")
        return stage_path

    def generate_diff_report(self, customer_id: str) -> str:
        """Compare staging vs last published version and generate markdown diff.

        Returns:
            Markdown-formatted diff report.
        """
        stage_path = self.staging_dir / customer_id
        published_path = self.published_dir / customer_id

        if not stage_path.exists():
            return f"No staged changes for {customer_id}."

        report_lines = [
            f"# Staged Changes: {customer_id}",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
        ]

        staged_files = [
            f for f in stage_path.iterdir()
            if f.is_file() and not f.name.startswith("_")
        ]

        for staged_file in sorted(staged_files):
            filename = staged_file.name
            new_content = staged_file.read_text()

            # Get previously published version
            published_file = published_path / filename
            if published_file.exists():
                old_content = published_file.read_text()
                if old_content == new_content:
                    report_lines.append(f"## {filename}")
                    report_lines.append("*No changes*\n")
                    continue

                diff = difflib.unified_diff(
                    old_content.splitlines(keepends=True),
                    new_content.splitlines(keepends=True),
                    fromfile=f"published/{filename}",
                    tofile=f"staged/{filename}",
                    n=3,
                )
                diff_text = "".join(diff)

                report_lines.append(f"## {filename} (modified)")
                report_lines.append("```diff")
                report_lines.append(diff_text.rstrip())
                report_lines.append("```\n")
            else:
                # New file
                report_lines.append(f"## {filename} (new)")
                preview = new_content[:2000]
                if len(new_content) > 2000:
                    preview += f"\n... ({len(new_content)} bytes total)"
                report_lines.append("```")
                report_lines.append(preview)
                report_lines.append("```\n")

        report = "\n".join(report_lines)

        # Save the diff report
        (stage_path / "_diff_report.md").write_text(report)
        return report

    def is_staged(self, customer_id: str) -> bool:
        meta_path = self.staging_dir / customer_id / "_meta.json"
        return meta_path.exists()

    def is_approved(self, customer_id: str) -> bool:
        meta_path = self.staging_dir / customer_id / "_meta.json"
        if not meta_path.exists():
            return False
        meta = json.loads(meta_path.read_text())
        return meta.get("approved", False)

    def approve_changes(self, customer_id: str) -> bool:
        """Mark staged changes as approved."""
        meta_path = self.staging_dir / customer_id / "_meta.json"
        if not meta_path.exists():
            logger.warning(f"No staged changes to approve for {customer_id}")
            return False

        meta = json.loads(meta_path.read_text())
        meta["approved"] = True
        meta["approved_at"] = datetime.now(timezone.utc).isoformat()
        meta_path.write_text(json.dumps(meta, indent=2))

        logger.info(f"Approved staged changes for {customer_id}")
        return True

    def get_staged_files(self, customer_id: str) -> dict[str, str]:
        """Read all staged files for a customer."""
        stage_path = self.staging_dir / customer_id
        if not stage_path.exists():
            return {}

        files = {}
        for f in stage_path.iterdir():
            if f.is_file() and not f.name.startswith("_"):
                files[f.name] = f.read_text()
        return files

    def publish_staged(self, customer_id: str) -> dict[str, str]:
        """Move staged content to published directory.

        Returns:
            Dict of filename -> content that was published.
        """
        stage_path = self.staging_dir / customer_id
        if not stage_path.exists():
            logger.warning(f"No staged content for {customer_id}")
            return {}

        meta_path = stage_path / "_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if not meta.get("approved", False):
                logger.warning(f"Staged content not approved for {customer_id}")
                return {}

        # Copy staged files to published
        published_path = self.published_dir / customer_id
        published_path.mkdir(parents=True, exist_ok=True)

        published = {}
        for f in stage_path.iterdir():
            if f.is_file() and not f.name.startswith("_"):
                content = f.read_text()
                (published_path / f.name).write_text(content)
                published[f.name] = content

        # Save publish metadata
        pub_meta = {
            "customer_id": customer_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "files": list(published.keys()),
        }
        (published_path / "_meta.json").write_text(json.dumps(pub_meta, indent=2))

        # Clean up staging
        for f in stage_path.iterdir():
            f.unlink()
        stage_path.rmdir()

        logger.info(f"Published {len(published)} files for {customer_id}")
        return published

    def cleanup_staging(self, customer_id: str):
        """Remove staged content without publishing."""
        stage_path = self.staging_dir / customer_id
        if stage_path.exists():
            for f in stage_path.iterdir():
                f.unlink()
            stage_path.rmdir()
            logger.info(f"Cleaned up staging for {customer_id}")
