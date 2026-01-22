"""
History Manager - handles conversion history storage and recovery
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """Represents a conversion history entry"""

    id: str
    user_id: int
    original_name: str
    converted_name: str
    source_format: str
    target_format: str
    file_size: int
    timestamp: str
    status: str
    file_id: Optional[str] = None  # Telegram file_id for recovery
    message_id: Optional[int] = None  # Message containing the file
    chat_id: Optional[int] = None
    checksum: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        return cls(**data)


class HistoryManager:
    """Manages conversion history with persistence"""

    def __init__(
        self, data_dir: Path, max_entries_per_user: int = 100, retention_days: int = 30
    ):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = data_dir / "history.json"
        self.max_entries = max_entries_per_user
        self.retention_days = retention_days
        self._history: Dict[int, List[HistoryEntry]] = {}
        self._lock = asyncio.Lock()
        self._load_history()

    def _load_history(self):
        """Load history from disk"""
        try:
            if self.history_file.exists():
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for user_id, entries in data.items():
                    self._history[int(user_id)] = [
                        HistoryEntry.from_dict(e) for e in entries
                    ]

                logger.info(f"Loaded history for {len(self._history)} users")
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            self._history = {}

    async def save_history(self):
        """Save history to disk"""
        async with self._lock:
            try:
                data = {
                    str(user_id): [e.to_dict() for e in entries]
                    for user_id, entries in self._history.items()
                }

                # Write atomically
                temp_file = self.history_file.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                temp_file.replace(self.history_file)
                logger.debug("History saved successfully")
            except Exception as e:
                logger.error(f"Failed to save history: {e}")

    async def add_entry(self, user_id: int, entry: HistoryEntry):
        """Add a history entry for a user"""
        async with self._lock:
            if user_id not in self._history:
                self._history[user_id] = []

            self._history[user_id].insert(0, entry)

            # Trim to max entries
            if len(self._history[user_id]) > self.max_entries:
                self._history[user_id] = self._history[user_id][: self.max_entries]

        await self.save_history()

    async def get_user_history(
        self, user_id: int, limit: int = 50
    ) -> List[HistoryEntry]:
        """Get history entries for a user"""
        entries = self._history.get(user_id, [])
        return entries[:limit]

    async def get_entry_by_id(
        self, user_id: int, entry_id: str
    ) -> Optional[HistoryEntry]:
        """Get a specific history entry by ID"""
        entries = self._history.get(user_id, [])
        for entry in entries:
            if entry.id == entry_id or entry.id.startswith(entry_id):
                return entry
        return None

    async def delete_entry(self, user_id: int, entry_id: str) -> bool:
        """Delete a specific history entry"""
        async with self._lock:
            if user_id not in self._history:
                return False

            original_len = len(self._history[user_id])
            self._history[user_id] = [
                e
                for e in self._history[user_id]
                if not (e.id == entry_id or e.id.startswith(entry_id))
            ]

            if len(self._history[user_id]) < original_len:
                await self.save_history()
                return True
            return False

    async def clear_user_history(self, user_id: int) -> int:
        """Clear all history for a user"""
        async with self._lock:
            count = len(self._history.get(user_id, []))
            self._history[user_id] = []

        await self.save_history()
        return count

    async def cleanup_old_entries(self):
        """Remove entries older than retention period"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        removed = 0

        async with self._lock:
            for user_id in self._history:
                original_len = len(self._history[user_id])
                self._history[user_id] = [
                    e
                    for e in self._history[user_id]
                    if datetime.fromisoformat(e.timestamp) > cutoff
                ]
                removed += original_len - len(self._history[user_id])

        if removed > 0:
            await self.save_history()
            logger.info(f"Cleaned up {removed} old history entries")

        return removed

    async def search_history(self, user_id: int, query: str) -> List[HistoryEntry]:
        """Search user's history by filename or format"""
        entries = self._history.get(user_id, [])
        query = query.lower()

        return [
            e
            for e in entries
            if query in e.original_name.lower()
            or query in e.source_format.lower()
            or query in e.target_format.lower()
        ]

    async def get_stats(self, user_id: int) -> Dict:
        """Get conversion statistics for a user"""
        entries = self._history.get(user_id, [])

        if not entries:
            return {
                "total_conversions": 0,
                "formats_used": [],
                "total_size": 0,
                "success_rate": 0,
            }

        formats = set()
        total_size = 0
        success_count = 0

        for e in entries:
            formats.add(e.source_format)
            formats.add(e.target_format)
            total_size += e.file_size
            if e.status == "success":
                success_count += 1

        return {
            "total_conversions": len(entries),
            "formats_used": list(formats),
            "total_size": total_size,
            "success_rate": success_count / len(entries) if entries else 0,
        }

    @staticmethod
    def generate_entry_id(user_id: int, filename: str, timestamp: str) -> str:
        """Generate unique entry ID"""
        data = f"{user_id}-{filename}-{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:12]

    @staticmethod
    def calculate_checksum(file_path: Path) -> str:
        """Calculate file checksum for integrity verification"""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
