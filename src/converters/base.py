"""
Base converter class - abstract base for all converters
"""

import asyncio
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConversionResult:
    """Result of a conversion operation"""

    success: bool
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    input_format: str = ""
    output_format: str = ""
    error_message: Optional[str] = None
    conversion_time: float = 0.0
    file_size: int = 0
    conversion_id: str = ""

    def __post_init__(self):
        if not self.conversion_id:
            self.conversion_id = str(uuid.uuid4())[:8]


class BaseConverter(ABC):
    """Abstract base class for all file converters"""

    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @property
    @abstractmethod
    def supported_input_formats(self) -> set:
        """Return set of supported input formats"""
        pass

    @property
    @abstractmethod
    def supported_output_formats(self) -> set:
        """Return set of supported output formats"""
        pass

    @abstractmethod
    async def convert(
        self,
        input_path: Path,
        output_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """
        Convert file to specified format

        Args:
            input_path: Path to input file
            output_format: Target format (without dot)
            options: Optional conversion parameters

        Returns:
            ConversionResult with conversion details
        """
        pass

    def can_convert(self, input_format: str, output_format: str) -> bool:
        """Check if conversion is supported"""
        return (
            input_format.lower() in self.supported_input_formats
            and output_format.lower() in self.supported_output_formats
        )

    def get_output_path(
        self,
        input_path: Path,
        output_format: str,
        preserve_name: bool = True,
    ) -> Path:
        """
        Generate output file path.

        Args:
            input_path: Original input file path
            output_format: Target format extension
            preserve_name: If True, keep original filename (just change ext)
        """
        if preserve_name:
            # Keep original name, just change extension
            filename = f"{input_path.stem}.{output_format}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            filename = f"{input_path.stem}_{timestamp}_{unique_id}.{output_format}"

        output_path = self.temp_dir / filename

        # Handle filename conflicts by adding counter
        counter = 1
        base_stem = input_path.stem
        while output_path.exists():
            filename = f"{base_stem}_{counter}.{output_format}"
            output_path = self.temp_dir / filename
            counter += 1

        return output_path

    async def run_command(self, cmd: List[str], timeout: int = 300) -> tuple:
        """
        Run external command asynchronously

        Args:
            cmd: Command and arguments as list
            timeout: Timeout in seconds

        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            return (
                stdout.decode("utf-8", errors="ignore"),
                stderr.decode("utf-8", errors="ignore"),
                process.returncode,
            )
        except asyncio.TimeoutError:
            process.kill()
            raise TimeoutError(f"Command timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise

    def cleanup_file(self, file_path: Path) -> None:
        """Safely remove a file"""
        try:
            if file_path and file_path.exists():
                file_path.unlink()
                logger.debug(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {file_path}: {e}")

    def get_file_size(self, file_path: Path) -> int:
        """Get file size in bytes"""
        try:
            return file_path.stat().st_size if file_path.exists() else 0
        except Exception:
            return 0

    def validate_input(self, input_path: Path) -> None:
        """Validate input file exists and is readable"""
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        if not input_path.is_file():
            raise ValueError(f"Path is not a file: {input_path}")
        if not os.access(input_path, os.R_OK):
            raise PermissionError(f"Cannot read file: {input_path}")
