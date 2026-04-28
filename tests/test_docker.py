"""Docker tests — build image, run --validate inside container.

These tests are slow and require Docker. Mark with 'docker' for easy deselection.
Run with: pytest tests/test_docker.py -v -m docker
"""

from __future__ import annotations

import subprocess

import pytest


@pytest.mark.docker
class TestDockerBuild:
    def test_image_builds(self):
        result = subprocess.run(
            ["docker", "build", "-t", "geo-agent-test", "."],
            capture_output=True,
            text=True,
            timeout=300,
            cwd="/Users/kody/dev/dental-marketing",
        )
        assert result.returncode == 0, f"Docker build failed:\n{result.stderr}"

    def test_validate_flag(self):
        """--validate should exit 0 inside the container (no API keys needed)."""
        result = subprocess.run(
            ["docker", "run", "--rm", "geo-agent-test", "python", "-m", "geo_agent.main", "--validate"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"Validate failed:\n{result.stderr}"
        assert "Validate OK" in result.stderr or "Validate OK" in result.stdout

    def test_sqlite_vec_loads(self):
        """sqlite-vec should be importable and functional inside the container."""
        result = subprocess.run(
            [
                "docker", "run", "--rm", "geo-agent-test",
                "python", "-c",
                "import sqlite3, sqlite_vec; db = sqlite3.connect(':memory:'); db.enable_load_extension(True); sqlite_vec.load(db); print('sqlite-vec OK:', db.execute('SELECT vec_version()').fetchone()[0])",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"sqlite-vec test failed:\n{result.stderr}"
        assert "sqlite-vec OK" in result.stdout
