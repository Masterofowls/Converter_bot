"""
E-book Converter - handles FB2, EPUB, MOBI
Uses calibre's ebook-convert for conversions
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .base import BaseConverter, ConversionResult

logger = logging.getLogger(__name__)


class EbookConverter(BaseConverter):
    """Converter for e-book formats using Calibre"""

    @property
    def supported_input_formats(self) -> set:
        return {"fb2", "epub", "mobi", "azw3", "pdf", "txt", "html", "rtf"}

    @property
    def supported_output_formats(self) -> set:
        return {"fb2", "epub", "mobi", "azw3", "pdf", "txt", "html"}

    async def convert(
        self,
        input_path: Path,
        output_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Convert e-book to specified format using ebook-convert"""
        start_time = datetime.now()
        options = options or {}

        try:
            self.validate_input(input_path)
            input_format = input_path.suffix.lstrip(".").lower()
            output_format = output_format.lower()

            output_path = self.get_output_path(input_path, output_format)

            # Build ebook-convert command
            cmd = self._build_convert_command(
                input_path, output_path, output_format, options
            )

            stdout, stderr, returncode = await self.run_command(
                cmd, timeout=options.get("timeout", 600)
            )

            if returncode != 0:
                raise RuntimeError(f"ebook-convert error: {stderr}")

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
            logger.error(f"E-book conversion failed: {e}")
            return ConversionResult(
                success=False,
                input_path=input_path,
                input_format=input_path.suffix.lstrip("."),
                output_format=output_format,
                error_message=str(e),
            )

    def _build_convert_command(
        self, input_path: Path, output_path: Path, output_format: str, options: dict
    ) -> list:
        """Build ebook-convert command"""
        cmd = ["ebook-convert", str(input_path), str(output_path)]

        # Add metadata options
        if "title" in options:
            cmd.extend(["--title", options["title"]])
        if "author" in options:
            cmd.extend(["--authors", options["author"]])
        if "cover" in options:
            cmd.extend(["--cover", options["cover"]])

        # Format-specific options
        if output_format == "epub":
            cmd.extend(
                [
                    "--epub-version",
                    options.get("epub_version", "3"),
                ]
            )
            if options.get("no_default_epub_cover"):
                cmd.append("--no-default-epub-cover")

        elif output_format == "mobi":
            cmd.extend(
                [
                    "--mobi-file-type",
                    options.get("mobi_type", "both"),
                ]
            )

        elif output_format == "pdf":
            cmd.extend(
                [
                    "--paper-size",
                    options.get("paper_size", "letter"),
                    "--pdf-page-margin-top",
                    str(options.get("margin_top", 72)),
                    "--pdf-page-margin-bottom",
                    str(options.get("margin_btm", 72)),
                    "--pdf-page-margin-left",
                    str(options.get("margin_left", 72)),
                    "--pdf-page-margin-right",
                    str(options.get("margin_right", 72)),
                ]
            )
            if options.get("pdf_serif_family"):
                cmd.extend(["--pdf-serif-family", options["pdf_serif_family"]])

        # General options
        if options.get("smarten_punctuation", True):
            cmd.append("--smarten-punctuation")

        return cmd

    async def get_ebook_metadata(self, input_path: Path) -> dict:
        """Get e-book metadata using ebook-meta"""
        cmd = ["ebook-meta", str(input_path)]

        stdout, stderr, returncode = await self.run_command(cmd)

        if returncode == 0:
            metadata = {}
            for line in stdout.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip().lower()] = value.strip()
            return metadata
        return {}

    async def set_ebook_metadata(self, input_path: Path, metadata: dict) -> bool:
        """Set e-book metadata"""
        cmd = ["ebook-meta", str(input_path)]

        if "title" in metadata:
            cmd.extend(["--title", metadata["title"]])
        if "author" in metadata:
            cmd.extend(["--authors", metadata["author"]])
        if "publisher" in metadata:
            cmd.extend(["--publisher", metadata["publisher"]])
        if "tags" in metadata:
            cmd.extend(["--tags", ",".join(metadata["tags"])])

        _, _, returncode = await self.run_command(cmd)
        return returncode == 0
