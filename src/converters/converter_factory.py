"""
Converter Factory - selects appropriate converter based on file format
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .archive_converter import ArchiveConverter
from .audio_converter import AudioConverter
from .base import BaseConverter, ConversionResult
from .data_converter import DataConverter
from .document_converter import DocumentConverter
from .ebook_converter import EbookConverter
from .image_converter import ImageConverter
from .model3d_converter import Model3DConverter
from .video_converter import VideoConverter

logger = logging.getLogger(__name__)


class ConverterFactory:
    """Factory class for selecting and managing converters"""

    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self._converters: Dict[str, BaseConverter] = {}
        self._initialize_converters()

    def _initialize_converters(self):
        """Initialize all converter instances"""
        self._converters = {
            "document": DocumentConverter(self.temp_dir),
            "image": ImageConverter(self.temp_dir),
            "video": VideoConverter(self.temp_dir),
            "audio": AudioConverter(self.temp_dir),
            "3d_model": Model3DConverter(self.temp_dir),
            "ebook": EbookConverter(self.temp_dir),
            "data": DataConverter(self.temp_dir),
            "archive": ArchiveConverter(self.temp_dir),
        }

        # Build format to converter mapping
        self._format_map: Dict[str, str] = {}
        for converter_name, converter in self._converters.items():
            for fmt in converter.supported_input_formats:
                self._format_map[fmt] = converter_name

    def get_converter(self, input_format: str) -> Optional[BaseConverter]:
        """Get appropriate converter for input format"""
        input_format = input_format.lower().lstrip(".")

        # Normalize some formats
        format_aliases = {
            "jpg": "jpeg",
            "tif": "tiff",
            "yml": "yaml",
        }
        input_format = format_aliases.get(input_format, input_format)

        converter_name = self._format_map.get(input_format)
        if converter_name:
            return self._converters[converter_name]
        return None

    def can_convert(self, input_format: str, output_format: str) -> bool:
        """Check if conversion between formats is supported"""
        converter = self.get_converter(input_format)
        if not converter:
            return False
        return converter.can_convert(input_format, output_format)

    async def convert(
        self,
        input_path: Path,
        output_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Perform conversion using appropriate converter"""
        input_format = input_path.suffix.lstrip(".").lower()
        output_format_lower = output_format.lower().lstrip(".")

        # Smart converter selection based on input AND output format
        converter = self._select_best_converter(input_format, output_format_lower)

        if not converter:
            return ConversionResult(
                success=False,
                input_path=input_path,
                input_format=input_format,
                output_format=output_format,
                error_message=f"No converter for format: {input_format}",
            )

        return await converter.convert(input_path, output_format, options)

    def _select_best_converter(
        self, input_format: str, output_format: str
    ) -> Optional[BaseConverter]:
        """Select the best converter based on both input and output format"""

        # Define format categories for smart routing
        ebook_formats = {"epub", "mobi", "azw3", "fb2"}
        spreadsheet_formats = {"xlsx", "xls", "ets", "tsv"}
        image_formats = {
            "png",
            "jpeg",
            "jpg",
            "webp",
            "bmp",
            "tiff",
            "tif",
            "ico",
            "svg",
        }
        video_formats = {"mp4", "avi", "mkv", "mov", "flv", "webm"}

        # --- PDF INPUT ROUTING ---
        if input_format == "pdf":
            # PDF -> ebook formats: use ebook converter
            if output_format in ebook_formats:
                conv = self._converters.get("ebook")
                if conv and conv.can_convert(input_format, output_format):
                    return conv
            # PDF -> document formats: use document converter
            else:
                conv = self._converters.get("document")
                if conv and conv.can_convert(input_format, output_format):
                    return conv

        # --- TXT INPUT ROUTING ---
        if input_format == "txt":
            # TXT -> ebook formats: use ebook converter
            if output_format in ebook_formats:
                conv = self._converters.get("ebook")
                if conv and conv.can_convert(input_format, output_format):
                    return conv
            # TXT -> other: use document converter
            else:
                conv = self._converters.get("document")
                if conv and conv.can_convert(input_format, output_format):
                    return conv

        # --- HTML INPUT ROUTING ---
        if input_format == "html":
            # HTML -> ebook formats: use ebook converter
            if output_format in ebook_formats:
                conv = self._converters.get("ebook")
                if conv and conv.can_convert(input_format, output_format):
                    return conv

        # --- CSV INPUT ROUTING ---
        if input_format == "csv":
            # CSV -> spreadsheet/data formats: use data converter
            if output_format in spreadsheet_formats | {
                "json",
                "xml",
                "html",
                "md",
                "pdf",
            }:
                conv = self._converters.get("data")
                if conv and conv.can_convert(input_format, output_format):
                    return conv
            # CSV -> document formats: use document converter
            else:
                conv = self._converters.get("document")
                if conv and conv.can_convert(input_format, output_format):
                    return conv

        # --- JSON INPUT ROUTING ---
        if input_format == "json":
            # JSON from spreadsheet context -> data converter
            if output_format in spreadsheet_formats | {"csv", "html", "md", "pdf"}:
                conv = self._converters.get("data")
                if conv and conv.can_convert(input_format, output_format):
                    return conv
            # JSON -> document formats: use document converter
            else:
                conv = self._converters.get("document")
                if conv and conv.can_convert(input_format, output_format):
                    return conv

        # --- GIF INPUT ROUTING ---
        if input_format == "gif":
            # GIF -> video formats: use video converter
            if output_format in video_formats | {"mp3"}:
                conv = self._converters.get("video")
                if conv and conv.can_convert(input_format, output_format):
                    return conv
            # GIF -> image formats: use image converter
            else:
                conv = self._converters.get("image")
                if conv and conv.can_convert(input_format, output_format):
                    return conv

        # --- DEFAULT: find any converter that supports this conversion ---
        for converter in self._converters.values():
            if converter.can_convert(input_format, output_format):
                return converter

        # Fallback to format map (for single-converter formats)
        return self.get_converter(input_format)

    def get_supported_formats(self) -> Dict[str, set]:
        """Get all supported input and output formats"""
        input_formats = set()
        output_formats = set()

        for converter in self._converters.values():
            input_formats.update(converter.supported_input_formats)
            output_formats.update(converter.supported_output_formats)

        return {"input": input_formats, "output": output_formats}

    def get_conversion_options(self, input_format: str, output_format: str) -> list:
        """Get available conversion options for format pair"""
        input_format = input_format.lower()
        output_format = output_format.lower()

        # Common options
        options = []

        # Image-specific options
        if input_format in {"png", "jpeg", "jpg", "webp", "bmp", "gif", "tiff"}:
            if output_format in {"jpeg", "jpg", "webp"}:
                options.append(
                    {
                        "name": "quality",
                        "type": "int",
                        "default": 95,
                        "min": 1,
                        "max": 100,
                        "description": "Output quality (1-100)",
                    }
                )
            if output_format == "ico":
                options.append(
                    {
                        "name": "sizes",
                        "type": "list",
                        "default": [(16, 16), (32, 32), (48, 48), (256, 256)],
                        "description": "Icon sizes to generate",
                    }
                )

        # Video-specific options
        if input_format in {"mp4", "webm", "avi", "mkv", "mov"}:
            if output_format in {"mp4", "webm", "mkv"}:
                options.append(
                    {
                        "name": "crf",
                        "type": "int",
                        "default": 23,
                        "min": 0,
                        "max": 51,
                        "description": "Quality (0=best, 51=worst)",
                    }
                )
                options.append(
                    {
                        "name": "preset",
                        "type": "choice",
                        "default": "medium",
                        "choices": [
                            "ultrafast",
                            "superfast",
                            "veryfast",
                            "faster",
                            "fast",
                            "medium",
                            "slow",
                            "slower",
                            "veryslow",
                        ],
                        "description": "Encoding speed/quality tradeoff",
                    }
                )
            if output_format == "gif":
                options.append(
                    {
                        "name": "fps",
                        "type": "int",
                        "default": 15,
                        "min": 1,
                        "max": 30,
                        "description": "Frames per second",
                    }
                )
                options.append(
                    {
                        "name": "width",
                        "type": "int",
                        "default": 480,
                        "description": "Output width (height auto)",
                    }
                )

        # Audio-specific options
        if input_format in {"mp3", "wav", "ogg", "flac", "aac", "m4a"}:
            options.append(
                {
                    "name": "bitrate",
                    "type": "choice",
                    "default": "192k",
                    "choices": ["64k", "128k", "192k", "256k", "320k"],
                    "description": "Audio bitrate",
                }
            )

        return options
