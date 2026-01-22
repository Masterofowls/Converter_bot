"""
E-book Converter - handles FB2, EPUB, MOBI
Uses calibre's ebook-convert for conversions, with Python fallback
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pdfplumber
from ebooklib import epub

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
        """Convert e-book to specified format"""
        start_time = datetime.now()
        options = options or {}

        try:
            self.validate_input(input_path)
            input_format = input_path.suffix.lstrip(".").lower()
            output_format = output_format.lower()

            output_path = self.get_output_path(input_path, output_format)

            # Check for Python-native conversions first (no Calibre needed)
            if input_format == "pdf" and output_format == "epub":
                logger.info("Using Python-native PDF→EPUB conversion")
                await self._pdf_to_epub_python(input_path, output_path, options)
            elif input_format == "txt" and output_format == "epub":
                logger.info("Using Python-native TXT→EPUB conversion")
                await self._txt_to_epub_python(input_path, output_path, options)
            else:
                # Try Calibre for other conversions
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
            error_str = str(e)
            if "cannot find the file" in error_str.lower():
                error_msg = (
                    "Calibre not installed. Install from: "
                    "https://calibre-ebook.com/download"
                )
            else:
                error_msg = error_str
            logger.error(f"E-book conversion failed: {e}")
            return ConversionResult(
                success=False,
                input_path=input_path,
                input_format=input_path.suffix.lstrip("."),
                output_format=output_format,
                error_message=error_msg,
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

    async def _pdf_to_epub_python(
        self, input_path: Path, output_path: Path, options: dict
    ):
        """Convert PDF to EPUB using Python (no Calibre needed)"""
        book = epub.EpubBook()

        # Set metadata
        title = options.get("title", input_path.stem)
        book.set_identifier(f"id-{input_path.stem}")
        book.set_title(title)
        book.set_language(options.get("language", "en"))
        if "author" in options:
            book.add_author(options["author"])

        # Extract text from PDF
        chapters = []
        with pdfplumber.open(str(input_path)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    # Create chapter for each page
                    chapter = epub.EpubHtml(
                        title=f"Page {i + 1}",
                        file_name=f"page_{i + 1}.xhtml",
                        lang="en",
                    )
                    # Convert text to HTML paragraphs
                    paragraphs = text.split("\n")
                    html_content = "".join(
                        f"<p>{p}</p>" for p in paragraphs if p.strip()
                    )
                    chapter.content = f"""
                    <html><head><title>Page {i + 1}</title></head>
                    <body><h2>Page {i + 1}</h2>{html_content}</body></html>
                    """
                    book.add_item(chapter)
                    chapters.append(chapter)

        # Add navigation
        book.toc = chapters
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Set spine
        book.spine = ["nav"] + chapters

        # Write EPUB
        epub.write_epub(str(output_path), book)

    async def _txt_to_epub_python(
        self, input_path: Path, output_path: Path, options: dict
    ):
        """Convert TXT to EPUB using Python"""
        book = epub.EpubBook()

        title = options.get("title", input_path.stem)
        book.set_identifier(f"id-{input_path.stem}")
        book.set_title(title)
        book.set_language(options.get("language", "en"))
        if "author" in options:
            book.add_author(options["author"])

        # Read text
        text = input_path.read_text(encoding="utf-8", errors="ignore")

        # Create single chapter
        chapter = epub.EpubHtml(
            title=title,
            file_name="content.xhtml",
            lang="en",
        )
        paragraphs = text.split("\n\n")
        html_content = "".join(
            f"<p>{p.replace(chr(10), '<br/>')}</p>" for p in paragraphs if p.strip()
        )
        chapter.content = f"""
        <html><head><title>{title}</title></head>
        <body>{html_content}</body></html>
        """
        book.add_item(chapter)

        # Navigation
        book.toc = [chapter]
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", chapter]

        epub.write_epub(str(output_path), book)
