"""
Audio Converter - handles MP3, WAV, OGG, FLAC, AAC, M4A
Uses FFmpeg for all conversions
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .base import BaseConverter, ConversionResult

logger = logging.getLogger(__name__)


class AudioConverter(BaseConverter):
    """Converter for audio formats using FFmpeg"""

    @property
    def supported_input_formats(self) -> set:
        return {"mp3", "wav", "ogg", "flac", "aac", "m4a", "wma"}

    @property
    def supported_output_formats(self) -> set:
        return {"mp3", "wav", "ogg", "flac", "aac", "m4a"}

    async def convert(
        self,
        input_path: Path,
        output_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Convert audio to specified format"""
        start_time = datetime.now()
        options = options or {}

        try:
            self.validate_input(input_path)
            input_format = input_path.suffix.lstrip(".").lower()
            output_format = output_format.lower()

            output_path = self.get_output_path(input_path, output_format)

            # Build FFmpeg command
            cmd = self._build_ffmpeg_command(
                input_path, output_path, output_format, options
            )

            stdout, stderr, returncode = await self.run_command(
                cmd, timeout=options.get("timeout", 300)
            )

            if returncode != 0:
                raise RuntimeError(f"FFmpeg error: {stderr}")

            elapsed = (datetime.now() - start_time).total_seconds()

            return ConversionResult(
                success=True,
                input_path=input_path,
                output_path=output_path,
                input_format=input_format,
                output_format=output_format,
                conversion_time=elapsed,
                file_size=self.get_file_size(output_path),
            )

        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return ConversionResult(
                success=False,
                input_path=input_path,
                input_format=input_path.suffix.lstrip("."),
                output_format=output_format,
                error_message=str(e),
            )

    def _build_ffmpeg_command(
        self, input_path: Path, output_path: Path, output_format: str, options: dict
    ) -> list:
        """Build FFmpeg command based on output format"""
        base_cmd = ["ffmpeg", "-y", "-i", str(input_path)]

        # Format-specific settings
        if output_format == "mp3":
            bitrate = options.get("bitrate", "192k")
            cmd = base_cmd + [
                "-c:a",
                "libmp3lame",
                "-b:a",
                bitrate,
                "-q:a",
                str(options.get("quality", 2)),
            ]

        elif output_format == "wav":
            cmd = base_cmd + [
                "-c:a",
                "pcm_s16le",
                "-ar",
                str(options.get("sample_rate", 44100)),
                "-ac",
                str(options.get("channels", 2)),
            ]

        elif output_format == "ogg":
            cmd = base_cmd + [
                "-c:a",
                "libvorbis",
                "-q:a",
                str(options.get("quality", 5)),
            ]

        elif output_format == "flac":
            cmd = base_cmd + [
                "-c:a",
                "flac",
                "-compression_level",
                str(options.get("compression", 8)),
            ]

        elif output_format == "aac":
            bitrate = options.get("bitrate", "192k")
            cmd = base_cmd + [
                "-c:a",
                "aac",
                "-b:a",
                bitrate,
            ]

        elif output_format == "m4a":
            bitrate = options.get("bitrate", "192k")
            cmd = base_cmd + [
                "-c:a",
                "aac",
                "-b:a",
                bitrate,
            ]

        else:
            # Generic conversion
            cmd = base_cmd

        # Add metadata if provided
        if "metadata" in options:
            for key, value in options["metadata"].items():
                cmd.extend(["-metadata", f"{key}={value}"])

        # Add output path
        cmd.append(str(output_path))

        return cmd

    async def get_audio_info(self, input_path: Path) -> dict:
        """Get audio information using ffprobe"""
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(input_path),
        ]

        stdout, stderr, returncode = await self.run_command(cmd)

        if returncode == 0:
            import json

            return json.loads(stdout)
        return {}

    async def normalize_audio(
        self, input_path: Path, output_path: Path, target_level: float = -16.0
    ) -> bool:
        """Normalize audio levels"""
        # First pass - analyze
        analyze_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-af",
            f"loudnorm=I={target_level}:print_format=json",
            "-f",
            "null",
            "-",
        ]

        _, stderr, returncode = await self.run_command(analyze_cmd)

        if returncode != 0:
            return False

        # Second pass - apply normalization
        normalize_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-af",
            f"loudnorm=I={target_level}",
            str(output_path),
        ]

        _, _, returncode = await self.run_command(normalize_cmd)
        return returncode == 0
