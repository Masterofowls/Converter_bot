"""
Security utilities for the Telegram bot
"""

import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Tuple

from src.config import (
    ALLOWED_FILENAME_CHARS,
    BLOCKED_EXTENSIONS,
    MAX_FILENAME_LENGTH,
    RATE_LIMIT_CONVERSION_WINDOW,
    RATE_LIMIT_CONVERSIONS,
    RATE_LIMIT_MESSAGES,
    RATE_LIMIT_WINDOW,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter for user actions"""

    def __init__(self):
        # {user_id: [(timestamp, action_type), ...]}
        self._user_actions: Dict[int, list] = defaultdict(list)

    def _cleanup_old_actions(
        self,
        user_id: int,
        window: int,
    ) -> None:
        """Remove actions older than the window"""
        current_time = time.time()
        self._user_actions[user_id] = [
            (ts, action)
            for ts, action in self._user_actions[user_id]
            if current_time - ts < window
        ]

    def check_rate_limit(
        self,
        user_id: int,
        action_type: str = "message",
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if user is within rate limits.

        Returns:
            Tuple of (is_allowed, seconds_until_reset)
        """
        current_time = time.time()

        if action_type == "message":
            window = RATE_LIMIT_WINDOW
            limit = RATE_LIMIT_MESSAGES
        elif action_type == "conversion":
            window = RATE_LIMIT_CONVERSION_WINDOW
            limit = RATE_LIMIT_CONVERSIONS
        else:
            return True, None

        self._cleanup_old_actions(user_id, window)

        # Count actions of this type
        action_count = sum(
            1 for _, a in self._user_actions[user_id] if a == action_type
        )

        if action_count >= limit:
            # Find when oldest action expires
            oldest = min(
                ts for ts, a in self._user_actions[user_id] if a == action_type
            )
            seconds_until_reset = int(window - (current_time - oldest)) + 1
            return False, seconds_until_reset

        # Record this action
        self._user_actions[user_id].append((current_time, action_type))
        return True, None

    def get_remaining(
        self,
        user_id: int,
        action_type: str = "message",
    ) -> int:
        """Get remaining actions allowed"""
        if action_type == "message":
            window = RATE_LIMIT_WINDOW
            limit = RATE_LIMIT_MESSAGES
        elif action_type == "conversion":
            window = RATE_LIMIT_CONVERSION_WINDOW
            limit = RATE_LIMIT_CONVERSIONS
        else:
            return 999

        self._cleanup_old_actions(user_id, window)
        action_count = sum(
            1 for _, a in self._user_actions[user_id] if a == action_type
        )
        return max(0, limit - action_count)


class FilenameSanitizer:
    """Sanitize filenames for security"""

    @staticmethod
    def sanitize(filename: str) -> str:
        """
        Sanitize a filename for safe storage and display.

        - Removes path components (prevents directory traversal)
        - Removes/replaces dangerous characters
        - Truncates to max length
        - Ensures valid extension
        """
        if not filename:
            return "unnamed_file"

        # Remove any path components
        filename = Path(filename).name

        # Remove null bytes and other control characters
        filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)

        # Replace problematic characters
        sanitized = ""
        for char in filename:
            if char in ALLOWED_FILENAME_CHARS:
                sanitized += char
            else:
                sanitized += "_"

        # Collapse multiple underscores/spaces
        sanitized = re.sub(r"[_\s]+", "_", sanitized)

        # Remove leading/trailing special chars
        sanitized = sanitized.strip("._- ")

        # Ensure not empty
        if not sanitized:
            sanitized = "unnamed_file"

        # Truncate while preserving extension
        if len(sanitized) > MAX_FILENAME_LENGTH:
            # Keep extension
            parts = sanitized.rsplit(".", 1)
            if len(parts) == 2 and len(parts[1]) <= 10:
                ext = parts[1]
                max_stem = MAX_FILENAME_LENGTH - len(ext) - 1
                sanitized = f"{parts[0][:max_stem]}.{ext}"
            else:
                sanitized = sanitized[:MAX_FILENAME_LENGTH]

        return sanitized

    @staticmethod
    def is_safe_extension(filename: str) -> bool:
        """Check if the file extension is safe"""
        ext = Path(filename).suffix.lower().lstrip(".")
        return ext not in BLOCKED_EXTENSIONS

    @staticmethod
    def get_safe_extension(filename: str) -> str:
        """Get the file extension, or empty if blocked"""
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext in BLOCKED_EXTENSIONS:
            return ""
        return ext


class InputValidator:
    """Validate user inputs"""

    @staticmethod
    def validate_format(format_str: str) -> Optional[str]:
        """
        Validate and normalize a format string.
        Returns normalized format or None if invalid.
        """
        if not format_str:
            return None

        # Normalize
        fmt = format_str.lower().strip().lstrip(".")

        # Check length (formats are typically 2-5 chars)
        if not (1 <= len(fmt) <= 10):
            return None

        # Check characters (alphanumeric only)
        if not fmt.isalnum():
            return None

        return fmt

    @staticmethod
    def validate_callback_data(data: str, max_length: int = 64) -> bool:
        """Validate callback data is safe"""
        if not data:
            return False
        if len(data) > max_length:
            return False
        # Only allow safe characters
        if not re.match(r"^[a-zA-Z0-9_\-]+$", data):
            return False
        return True

    @staticmethod
    def validate_conversion_id(conv_id: str) -> bool:
        """Validate a conversion ID"""
        if not conv_id:
            return False
        # UUIDs are 8 chars in our case (truncated)
        if not (4 <= len(conv_id) <= 36):
            return False
        if not re.match(r"^[a-zA-Z0-9\-]+$", conv_id):
            return False
        return True


# Global instances
rate_limiter = RateLimiter()
filename_sanitizer = FilenameSanitizer()
input_validator = InputValidator()
