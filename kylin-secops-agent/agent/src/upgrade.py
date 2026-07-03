"""
Agent remote upgrade module.

Workflow:
  1. Platform sends upgrade instruction via WebSocket
  2. Agent downloads new package from MinIO (or HTTPS)
  3. Verify SHA256 checksum/signature
  4. Replace current binary
  5. systemd daemon-reload + restart

Rollback: Previous version is preserved under DATA_DIR/prev/
"""

import asyncio
import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional

import aiohttp

from src import __version__
from src.logger import get_logger

logger = get_logger("upgrade")


class AgentUpgrader:
    """Handles remote agent upgrade workflow."""

    def __init__(
        self,
        data_dir: Path,
        on_progress: Optional[Callable[..., Coroutine]] = None,
    ):
        self._data_dir = data_dir
        self._prev_dir = data_dir / "prev"
        self._backup_dir = data_dir / "backups"
        self._on_progress = on_progress
        self._running = False

        # Create directories
        self._prev_dir.mkdir(parents=True, exist_ok=True)
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════════════════════════════
    # Upgrade workflow
    # ═══════════════════════════════════════════════════════════════════

    async def handle_upgrade_message(self, msg: Dict[str, Any]) -> bool:
        """Handle an incoming 'upgrade' WebSocket message.

        Expected format:
            {"type": "upgrade", "version": "3.2.1",
             "download_url": "https://minio.secops/agent/3.2.1/kylin-secops-agent.tar.gz",
             "checksum": "sha256:abc123..."}

        Returns True if upgrade was applied.
        """
        if self._running:
            logger.warning("Upgrade already in progress; ignoring")
            return False

        self._running = True
        version = msg.get("version", "")
        download_url = msg.get("download_url", "")
        checksum = msg.get("checksum", "")

        if not version or not download_url:
            logger.error("Invalid upgrade message: missing version or download_url")
            self._running = False
            return False

        logger.info("Upgrade to v%s starting (url=%s)", version, download_url)

        try:
            # 1. Download package
            await self._report_progress("downloading", 10)
            pkg_path = await self._download_package(download_url, version)

            # 2. Verify checksum
            await self._report_progress("verifying", 40)
            if checksum:
                if not self._verify_checksum(pkg_path, checksum):
                    logger.error("Checksum verification failed for %s", pkg_path)
                    await self._report_progress("failed", 0, "Checksum mismatch")
                    return False

            # 3. Backup current version
            await self._report_progress("backing_up", 60)
            self._backup_current()

            # 4. Extract/install new version
            await self._report_progress("installing", 80)
            self._install_package(pkg_path, version)

            # 5. Restart via systemd
            await self._report_progress("restarting", 90)
            self._restart_service()

            await self._report_progress("completed", 100)
            logger.info("Upgrade to v%s completed successfully", version)
            return True

        except Exception as exc:
            logger.exception("Upgrade failed: %s", exc)
            await self._report_progress("failed", 0, str(exc))
            self._rollback()
            return False
        finally:
            self._running = False

    # ═══════════════════════════════════════════════════════════════════
    # Steps
    # ═══════════════════════════════════════════════════════════════════

    async def _download_package(self, url: str, version: str) -> Path:
        """Download upgrade package from URL to local cache."""
        dest = self._data_dir / f"upgrade-v{version}.tar.gz"
        logger.info("Downloading %s -> %s", url, dest)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(dest, "wb") as fh:
                    async for chunk in resp.content.iter_chunked(8192):
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if total and downloaded % (1024 * 1024) == 0:
                            pct = int(downloaded * 100 / total)
                            logger.debug("Download progress: %d/%d (%d%%)",
                                         downloaded, total, pct)

        logger.info("Downloaded %d bytes to %s", os.path.getsize(dest), dest)
        return dest

    @staticmethod
    def _verify_checksum(pkg_path: Path, expected: str) -> bool:
        """Verify SHA256 checksum of downloaded package."""
        # Support both "sha256:..." and raw hex
        if expected.startswith("sha256:"):
            expected_hash = expected[7:]
        else:
            expected_hash = expected

        sha256 = hashlib.sha256()
        with open(pkg_path, "rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                sha256.update(chunk)

        actual = sha256.hexdigest()
        if actual != expected_hash:
            logger.error(
                "Checksum mismatch: expected=%s actual=%s", expected_hash, actual
            )
            return False
        return True

    def _backup_current(self):
        """Backup current agent installation."""
        src_dir = Path("/opt/kylin-secops-agent")
        if src_dir.exists():
            backup_name = f"prev-{int(time.time())}"
            backup_path = self._backup_dir / backup_name
            shutil.copytree(str(src_dir), str(backup_path))
            logger.info("Backed up current installation to %s", backup_path)

    def _install_package(self, pkg_path: Path, version: str):
        """Install the downloaded package.

        For tar.gz: extract to /opt/kylin-secops-agent/
        For single file: copy to /usr/local/bin/
        """
        dest_dir = Path("/opt/kylin-secops-agent")

        if pkg_path.suffix == ".gz" or pkg_path.name.endswith(".tar.gz"):
            import tarfile
            dest_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(str(pkg_path), "r:gz") as tar:
                tar.extractall(path=str(dest_dir))
            logger.info("Extracted %s to %s", pkg_path, dest_dir)
        else:
            # Single binary
            dest = dest_dir / "kylin-secops-agent"
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(pkg_path), str(dest))
            dest.chmod(0o755)
            logger.info("Installed %s to %s", pkg_path, dest)

    def _restart_service(self):
        """Restart agent via systemd."""
        logger.info("Restarting kylin-secops-agent service...")
        try:
            subprocess.run(
                ["systemctl", "daemon-reload"],
                check=True, capture_output=True, timeout=10,
            )
            subprocess.run(
                ["systemctl", "restart", "kylin-secops-agent"],
                check=True, capture_output=True, timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            logger.warning("systemctl restart failed: %s", exc.stderr.decode())
            raise
        except FileNotFoundError:
            logger.warning("systemctl not available; upgrade restart skipped")

    def _rollback(self):
        """Rollback to previous version on upgrade failure."""
        backups = sorted(self._backup_dir.iterdir()) if self._backup_dir.exists() else []
        if not backups:
            logger.warning("No backup available for rollback")
            return

        latest_backup = backups[-1]
        logger.info("Rolling back to %s...", latest_backup)

        dest_dir = Path("/opt/kylin-secops-agent")
        if dest_dir.exists():
            shutil.rmtree(str(dest_dir))
        shutil.copytree(str(latest_backup), str(dest_dir))
        logger.info("Rollback completed")

        # Try to restart
        self._restart_service()

    async def _report_progress(self, stage: str, progress: int,
                                error: str = ""):
        """Report upgrade progress."""
        if self._on_progress:
            try:
                await self._on_progress({
                    "type": "upgrade_progress",
                    "stage": stage,
                    "progress": progress,
                    "error": error,
                })
            except Exception as exc:
                logger.warning("Progress report error: %s", exc)