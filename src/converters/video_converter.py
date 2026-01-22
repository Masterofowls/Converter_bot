"""
Video Converter - handles MP4, WEBM, AVI, MKV, MOV, FLV, GIF
Uses FFmpeg for all conversions
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .base import BaseConverter, ConversionResult

logger = logging.getLogger(__name__)


class VideoConverter(BaseConverter):
    """Converter for video formats using FFmpeg"""

    @property
    def supported_input_formats(self) -> set:
        return {"webm", "mp4", "avi", "mkv", "mov", "flv", "gif"}

    @property
    def supported_output_formats(self) -> set:
        return {"webm", "mp4", "avi", "mkv", "mov", "gif", "mp3"}

    async def convert(
        self,
        input_path: Path,
        output_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Convert video to specified format"""
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
                cmd, timeout=options.get("timeout", 600)
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
            logger.error(f"Video conversion failed: {e}")
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
        base_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i",
            str(input_path),
        ]

        # Format-specific settings
        if output_format == "mp4":
            cmd = base_cmd + [
                "-c:v",
                "libx264",
                "-preset",
                options.get("preset", "medium"),
                "-crf",
                str(options.get("crf", 23)),
                "-c:a",
                "aac",
                "-b:a",
                options.get("audio_bitrate", "192k"),
                "-movflags",
                "+faststart",
            ]

        elif output_format == "webm":
            cmd = base_cmd + [
                "-c:v",
                "libvpx-vp9",
                "-crf",
                str(options.get("crf", 30)),
                "-b:v",
                "0",
                "-c:a",
                "libopus",
                "-b:a",
                options.get("audio_bitrate", "128k"),
            ]

        elif output_format == "avi":
            cmd = base_cmd + [
                "-c:v",
                "mpeg4",
                "-q:v",
                str(options.get("quality", 5)),
                "-c:a",
                "mp3",
                "-b:a",
                options.get("audio_bitrate", "192k"),
            ]

        elif output_format == "mkv":
            cmd = base_cmd + [
                "-c:v",
                "libx264",
                "-preset",
                options.get("preset", "medium"),
                "-crf",
                str(options.get("crf", 23)),
                "-c:a",
                "aac",
                "-b:a",
                options.get("audio_bitrate", "192k"),
            ]

        elif output_format == "mov":
            cmd = base_cmd + [
                "-c:v",
                "libx264",
                "-preset",
                options.get("preset", "medium"),
                "-crf",
                str(options.get("crf", 23)),
                "-c:a",
                "aac",
                "-b:a",
                options.get("audio_bitrate", "192k"),
            ]

        elif output_format == "gif":
            # Two-pass GIF creation for better quality
            fps = options.get("fps", 15)
            width = options.get("width", 480)

            cmd = base_cmd + [
                "-vf",
                f"fps={fps},scale={width}:-1:flags=lanczos,"
                f"split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                "-loop",
                "0",
            ]

        elif output_format == "mp3":
            # Extract audio
            cmd = base_cmd + [
                "-vn",  # No video
                "-c:a",
                "libmp3lame",
                "-b:a",
                options.get("audio_bitrate", "192k"),
            ]

        else:
            # Generic conversion
            cmd = base_cmd

        # Add resolution if specified
        if "resolution" in options and output_format != "gif":
            res = options["resolution"]
            cmd.extend(["-vf", f"scale={res}"])

        # Add output path
        cmd.append(str(output_path))

        return cmd

    async def get_video_info(self, input_path: Path) -> dict:
        """Get video information using ffprobe"""
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

    async def extract_frame(
        self, input_path: Path, output_path: Path, timestamp: str = "00:00:01"
    ) -> bool:
        """Extract a single frame from video"""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-ss",
            timestamp,
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]

        _, _, returncode = await self.run_command(cmd)
        return returncode == 0
