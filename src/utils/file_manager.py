"""
File Manager - handles temporary file storage and cleanup
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set

import aiofiles

logger = logging.getLogger(__name__)


class FileManager:
    """Manages temporary files with automatic cleanup"""

    def __init__(
        self, temp_dir: Path, cleanup_interval: int = 300, file_retention: int = 3600
    ):
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_interval = cleanup_interval
        self.file_retention = file_retention
        self._active_files: Set[Path] = set()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the file manager and cleanup task"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("File manager started")

    async def stop(self):
        """Stop the file manager"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("File manager stopped")

    async def save_file(self, data: bytes, filename: str, user_id: int) -> Path:
        """Save uploaded file to temp directory"""
        # Create user-specific subdirectory
        user_dir = self.temp_dir / str(user_id)
        user_dir.mkdir(exist_ok=True)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self._sanitize_filename(filename)
        file_path = user_dir / f"{timestamp}_{safe_name}"

        # Ensure unique path
        counter = 1
        base_path = file_path
        while file_path.exists():
            stem = base_path.stem
            suffix = base_path.suffix
            file_path = user_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        # Write file
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(data)

        self._active_files.add(file_path)
        logger.debug(f"Saved file: {file_path}")
        return file_path

    async def get_file(self, file_path: Path) -> Optional[bytes]:
        """Read file contents"""
        try:
            if file_path.exists():
                async with aiofiles.open(file_path, "rb") as f:
                    return await f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
        return None

    def mark_for_cleanup(self, file_path: Path):
        """Mark a file for cleanup"""
        self._active_files.discard(file_path)

    async def cleanup_file(self, file_path: Path):
        """Remove a specific file"""
        try:
            if file_path and file_path.exists():
                file_path.unlink()
                self._active_files.discard(file_path)
                logger.debug(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")

    async def cleanup_user_files(self, user_id: int):
        """Remove all temp files for a user"""
        user_dir = self.temp_dir / str(user_id)
        if user_dir.exists():
            try:
                shutil.rmtree(user_dir)
                # Remove from active files
                self._active_files = {
                    f
                    for f in self._active_files
                    if not str(f).startswith(str(user_dir))
                }
                logger.info(f"Cleaned up files for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to cleanup user files: {e}")

    async def _cleanup_loop(self):
        """Periodic cleanup of old files"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_old_files()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def _cleanup_old_files(self):
        """Remove files older than retention period"""
        cutoff = datetime.now() - timedelta(seconds=self.file_retention)
        removed = 0

        for user_dir in self.temp_dir.iterdir():
            if not user_dir.is_dir():
                continue

            for file_path in user_dir.iterdir():
                try:
                    # Check if file is old enough
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff and file_path not in self._active_files:
                        file_path.unlink()
                        removed += 1
                except Exception as e:
                    logger.warning(f"Error checking file {file_path}: {e}")

            # Remove empty directories
            try:
                if user_dir.exists() and not any(user_dir.iterdir()):
                    user_dir.rmdir()
            except Exception:
                pass

        if removed > 0:
            logger.info(f"Cleanup removed {removed} old files")

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove path separators and dangerous characters
        dangerous_chars = ["/", "\\", "..", "\x00"]
        safe_name = filename

        for char in dangerous_chars:
            safe_name = safe_name.replace(char, "_")

        # Limit length
        if len(safe_name) > 200:
            name, ext = os.path.splitext(safe_name)
            safe_name = name[: 200 - len(ext)] + ext

        return safe_name

    def get_user_storage_size(self, user_id: int) -> int:
        """Get total storage used by a user"""
        user_dir = self.temp_dir / str(user_id)
        if not user_dir.exists():
            return 0

        total = 0
        for file_path in user_dir.iterdir():
            try:
                total += file_path.stat().st_size
            except Exception:
                pass
        return total

    def get_temp_dir_size(self) -> int:
        """Get total temp directory size"""
        total = 0
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                try:
                    total += os.path.getsize(os.path.join(root, file))
                except Exception:
                    pass
        return total
