"""
Archive Converter - handles archive format conversions
Supports: ZIP, 7Z, TAR, GZ, RAR
"""

import logging
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import BaseConverter, ConversionResult

logger = logging.getLogger(__name__)

# Check for py7zr support
try:
    import py7zr

    HAS_7Z = True
except ImportError:
    HAS_7Z = False
    logger.warning("py7zr not installed - 7z support limited")

# Check for rarfile support
try:
    import rarfile

    HAS_RAR = True
except ImportError:
    HAS_RAR = False
    logger.warning("rarfile not installed - RAR extraction disabled")


class ArchiveConverter(BaseConverter):
    """Converter for archive formats"""

    @property
    def supported_input_formats(self) -> Set[str]:
        formats = {"zip", "tar", "gz", "tar.gz", "tgz"}
        if HAS_7Z:
            formats.add("7z")
        if HAS_RAR:
            formats.add("rar")
        return formats

    @property
    def supported_output_formats(self) -> Set[str]:
        formats = {"zip", "tar", "gz", "tar.gz"}
        if HAS_7Z:
            formats.add("7z")
        return formats

    async def convert(
        self,
        input_path: Path,
        output_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Convert archive to different format"""
        import time

        start_time = time.time()

        try:
            self.validate_input(input_path)
            input_format = input_path.suffix.lower().lstrip(".")
            output_format = output_format.lower().lstrip(".")

            # Handle compound extensions
            if input_path.name.endswith(".tar.gz"):
                input_format = "tar.gz"
            elif input_path.name.endswith(".tgz"):
                input_format = "tgz"

            output_path = self.get_output_path(input_path, output_format)

            # Extract to temp directory
            extract_dir = self.temp_dir / f"extract_{input_path.stem}"
            extract_dir.mkdir(exist_ok=True)

            try:
                # Extract archive
                await self._extract_archive(input_path, extract_dir, input_format)

                # Create new archive
                await self._create_archive(extract_dir, output_path, output_format)

                # Get file list for info
                file_count = sum(1 for _ in extract_dir.rglob("*") if _.is_file())

            finally:
                # Cleanup extraction directory
                if extract_dir.exists():
                    shutil.rmtree(extract_dir, ignore_errors=True)

            conversion_time = time.time() - start_time
            file_size = self.get_file_size(output_path)

            logger.info(
                f"Converted {input_format} -> {output_format} "
                f"({file_count} files, {file_size} bytes)"
            )

            return ConversionResult(
                success=True,
                input_path=input_path,
                output_path=output_path,
                input_format=input_format,
                output_format=output_format,
                conversion_time=conversion_time,
                file_size=file_size,
            )

        except Exception as e:
            logger.error(f"Archive conversion failed: {e}")
            return ConversionResult(
                success=False,
                input_path=input_path,
                input_format=input_path.suffix.lstrip("."),
                output_format=output_format,
                error_message=str(e),
            )

    async def _extract_archive(
        self,
        archive_path: Path,
        extract_dir: Path,
        archive_format: str,
    ) -> None:
        """Extract archive contents to directory"""
        archive_format = archive_format.lower()

        if archive_format == "zip":
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(extract_dir)

        elif archive_format in ("tar", "tar.gz", "tgz", "gz"):
            mode = "r:gz" if archive_format in ("tar.gz", "tgz", "gz") else "r"
            with tarfile.open(archive_path, mode) as tf:
                # Security: prevent path traversal
                for member in tf.getmembers():
                    if member.name.startswith("/") or ".." in member.name:
                        raise ValueError(f"Unsafe path in archive: {member.name}")
                tf.extractall(extract_dir)

        elif archive_format == "7z" and HAS_7Z:
            with py7zr.SevenZipFile(archive_path, mode="r") as z:
                z.extractall(extract_dir)

        elif archive_format == "rar" and HAS_RAR:
            with rarfile.RarFile(archive_path, "r") as rf:
                rf.extractall(extract_dir)

        else:
            raise ValueError(f"Unsupported archive format: {archive_format}")

    async def _create_archive(
        self,
        source_dir: Path,
        output_path: Path,
        archive_format: str,
    ) -> None:
        """Create archive from directory contents"""
        archive_format = archive_format.lower()

        if archive_format == "zip":
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in source_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(source_dir)
                        zf.write(file_path, arcname)

        elif archive_format in ("tar", "tar.gz", "gz"):
            mode = "w:gz" if archive_format in ("tar.gz", "gz") else "w"
            with tarfile.open(output_path, mode) as tf:
                for file_path in source_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(source_dir)
                        tf.add(file_path, arcname)

        elif archive_format == "7z" and HAS_7Z:
            with py7zr.SevenZipFile(output_path, mode="w") as z:
                for file_path in source_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = str(file_path.relative_to(source_dir))
                        z.write(file_path, arcname)

        else:
            raise ValueError(f"Cannot create archive format: {archive_format}")

    async def list_contents(
        self,
        archive_path: Path,
    ) -> List[Dict[str, Any]]:
        """List archive contents without extracting"""
        self.validate_input(archive_path)
        archive_format = archive_path.suffix.lower().lstrip(".")

        if archive_path.name.endswith(".tar.gz"):
            archive_format = "tar.gz"

        contents = []

        try:
            if archive_format == "zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for info in zf.infolist():
                        contents.append(
                            {
                                "name": info.filename,
                                "size": info.file_size,
                                "compressed": info.compress_size,
                                "is_dir": info.is_dir(),
                            }
                        )

            elif archive_format in ("tar", "tar.gz", "tgz", "gz"):
                mode = "r:gz" if archive_format in ("tar.gz", "tgz") else "r"
                with tarfile.open(archive_path, mode) as tf:
                    for member in tf.getmembers():
                        contents.append(
                            {
                                "name": member.name,
                                "size": member.size,
                                "compressed": member.size,
                                "is_dir": member.isdir(),
                            }
                        )

            elif archive_format == "7z" and HAS_7Z:
                with py7zr.SevenZipFile(archive_path, mode="r") as z:
                    for entry in z.list():
                        contents.append(
                            {
                                "name": entry.filename,
                                "size": entry.uncompressed or 0,
                                "compressed": entry.compressed or 0,
                                "is_dir": entry.is_directory,
                            }
                        )

            elif archive_format == "rar" and HAS_RAR:
                with rarfile.RarFile(archive_path, "r") as rf:
                    for info in rf.infolist():
                        contents.append(
                            {
                                "name": info.filename,
                                "size": info.file_size,
                                "compressed": info.compress_size,
                                "is_dir": info.is_dir(),
                            }
                        )

        except Exception as e:
            logger.error(f"Failed to list archive contents: {e}")

        return contents

    def get_archive_info(self, archive_path: Path) -> Dict[str, Any]:
        """Get summary info about archive"""
        archive_format = archive_path.suffix.lower().lstrip(".")
        if archive_path.name.endswith(".tar.gz"):
            archive_format = "tar.gz"

        total_size = 0
        file_count = 0

        try:
            if archive_format == "zip":
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for info in zf.infolist():
                        if not info.is_dir():
                            total_size += info.file_size
                            file_count += 1

        except Exception as e:
            logger.warning(f"Could not read archive info: {e}")

        return {
            "format": archive_format,
            "file_count": file_count,
            "total_size": total_size,
            "archive_size": archive_path.stat().st_size,
        }
