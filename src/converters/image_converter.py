"""
Image Converter - handles PNG, JPEG, GIF, SVG, ICO, WEBP, BMP, TIFF
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image

# Try to import cairosvg (optional, for SVG support)
try:
    import cairosvg

    CAIROSVG_AVAILABLE = True
except (ImportError, OSError):
    cairosvg = None
    CAIROSVG_AVAILABLE = False
    # SVG conversion disabled on Windows without Cairo

from .base import BaseConverter, ConversionResult

logger = logging.getLogger(__name__)


class ImageConverter(BaseConverter):
    """Converter for image formats"""

    @property
    def supported_input_formats(self) -> set:
        return {"gif", "svg", "ico", "png", "jpeg", "jpg", "webp", "bmp", "tiff", "tif"}

    @property
    def supported_output_formats(self) -> set:
        return {"gif", "svg", "ico", "png", "jpeg", "jpg", "webp", "bmp", "tiff", "pdf"}

    async def convert(
        self,
        input_path: Path,
        output_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> ConversionResult:
        """Convert image to specified format"""
        start_time = datetime.now()
        options = options or {}

        try:
            self.validate_input(input_path)
            input_format = input_path.suffix.lstrip(".").lower()
            output_format = output_format.lower()

            # Normalize formats
            if input_format == "tif":
                input_format = "tiff"
            if output_format == "jpg":
                output_format = "jpeg"

            output_path = self.get_output_path(input_path, output_format)

            # Handle SVG input separately
            if input_format == "svg":
                await self._convert_svg(input_path, output_path, output_format, options)
            # Handle SVG output
            elif output_format == "svg":
                await self._to_svg(input_path, output_path, options)
            # Handle ICO output
            elif output_format == "ico":
                await self._to_ico(input_path, output_path, options)
            # Handle PDF output
            elif output_format == "pdf":
                await self._to_pdf(input_path, output_path, options)
            # Handle GIF output (animation preservation)
            elif output_format == "gif" and input_format == "gif":
                await self._gif_to_gif(input_path, output_path, options)
            else:
                await self._convert_raster(
                    input_path, output_path, output_format, options
                )

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
            logger.error(f"Image conversion failed: {e}")
            return ConversionResult(
                success=False,
                input_path=input_path,
                input_format=input_path.suffix.lstrip("."),
                output_format=output_format,
                error_message=str(e),
            )

    async def _convert_svg(
        self, input_path: Path, output_path: Path, output_format: str, options: dict
    ):
        """Convert SVG to other formats"""
        if not CAIROSVG_AVAILABLE:
            raise RuntimeError(
                "SVG conversion not available - Cairo library not installed"
            )

        width = options.get("width")
        height = options.get("height")
        scale = options.get("scale", 1.0)

        kwargs = {}
        if width:
            kwargs["output_width"] = width
        if height:
            kwargs["output_height"] = height
        kwargs["scale"] = scale

        if output_format == "png":
            cairosvg.svg2png(url=str(input_path), write_to=str(output_path), **kwargs)
        elif output_format == "pdf":
            cairosvg.svg2pdf(url=str(input_path), write_to=str(output_path), **kwargs)
        elif output_format in ("jpeg", "jpg"):
            # Convert to PNG first, then to JPEG
            temp_png = output_path.with_suffix(".temp.png")
            cairosvg.svg2png(url=str(input_path), write_to=str(temp_png), **kwargs)
            with Image.open(temp_png) as img:
                rgb_img = img.convert("RGB")
                rgb_img.save(
                    str(output_path), "JPEG", quality=options.get("quality", 95)
                )
            temp_png.unlink()
        elif output_format == "webp":
            temp_png = output_path.with_suffix(".temp.png")
            cairosvg.svg2png(url=str(input_path), write_to=str(temp_png), **kwargs)
            with Image.open(temp_png) as img:
                img.save(str(output_path), "WEBP", quality=options.get("quality", 90))
            temp_png.unlink()
        elif output_format == "ico":
            temp_png = output_path.with_suffix(".temp.png")
            cairosvg.svg2png(
                url=str(input_path),
                write_to=str(temp_png),
                output_width=256,
                output_height=256,
            )
            with Image.open(temp_png) as img:
                sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
                img.save(str(output_path), format="ICO", sizes=sizes)
            temp_png.unlink()
        else:
            raise ValueError(f"Unsupported SVG conversion: {output_format}")

    async def _to_svg(self, input_path: Path, output_path: Path, options: dict):
        """Convert raster image to SVG (traced)"""
        # Simple bitmap to SVG conversion (embedded)
        with Image.open(input_path) as img:
            import base64
            import io

            # Convert to PNG for embedding
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            b64_data = base64.b64encode(buffer.getvalue()).decode()

            svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{img.width}" height="{img.height}">
  <image width="{img.width}" height="{img.height}"
         xlink:href="data:image/png;base64,{b64_data}"/>
</svg>'''
            output_path.write_text(svg_content, encoding="utf-8")

    async def _to_ico(self, input_path: Path, output_path: Path, options: dict):
        """Convert image to ICO format"""
        with Image.open(input_path) as img:
            # Ensure RGBA mode for transparency
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Standard ICO sizes
            sizes = options.get("sizes", [(16, 16), (32, 32), (48, 48), (256, 256)])

            img.save(str(output_path), format="ICO", sizes=sizes)

    async def _to_pdf(self, input_path: Path, output_path: Path, options: dict):
        """Convert image to PDF"""
        with Image.open(input_path) as img:
            # Convert to RGB if necessary
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(
                    img, mask=img.split()[-1] if img.mode == "RGBA" else None
                )
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            img.save(str(output_path), "PDF", resolution=options.get("dpi", 300))

    async def _gif_to_gif(self, input_path: Path, output_path: Path, options: dict):
        """Process GIF preserving animation"""
        with Image.open(input_path) as img:
            frames = []
            durations = []

            try:
                while True:
                    frames.append(img.copy())
                    durations.append(img.info.get("duration", 100))
                    img.seek(img.tell() + 1)
            except EOFError:
                pass

            if frames:
                frames[0].save(
                    str(output_path),
                    format="GIF",
                    save_all=True,
                    append_images=frames[1:],
                    duration=durations,
                    loop=img.info.get("loop", 0),
                )

    async def _convert_raster(
        self, input_path: Path, output_path: Path, output_format: str, options: dict
    ):
        """Convert between raster image formats"""
        with Image.open(input_path) as img:
            # Handle animated GIFs
            if getattr(img, "is_animated", False) and output_format == "gif":
                await self._gif_to_gif(input_path, output_path, options)
                return

            # Get quality settings
            quality = options.get("quality", 95)

            # Handle mode conversion for different formats
            if output_format in ("jpeg", "jpg"):
                if img.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(
                        img, mask=img.split()[-1] if "A" in img.mode else None
                    )
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(str(output_path), "JPEG", quality=quality)

            elif output_format == "png":
                img.save(
                    str(output_path), "PNG", optimize=options.get("optimize", True)
                )

            elif output_format == "webp":
                img.save(
                    str(output_path),
                    "WEBP",
                    quality=quality,
                    lossless=options.get("lossless", False),
                )

            elif output_format == "gif":
                if img.mode not in ("P", "L"):
                    img = img.convert("P", palette=Image.ADAPTIVE)
                img.save(str(output_path), "GIF")

            elif output_format == "bmp":
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(str(output_path), "BMP")

            elif output_format == "tiff":
                img.save(
                    str(output_path),
                    "TIFF",
                    compression=options.get("compression", "tiff_lzw"),
                )

            else:
                # Generic save
                img.save(str(output_path))
