"""
File Handlers - handle incoming files and conversion processing
"""

import asyncio
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from telegram import Document, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config import ALL_INPUT_FORMATS, CONVERSION_TIMEOUT, MAX_UPLOAD_SIZE
from src.converters import ConverterFactory
from src.ui.keyboards import (
    create_error_menu,
    create_format_selection_menu,
    create_main_menu,
    create_multi_file_menu,
    create_result_menu,
)
from src.ui.messages import (
    format_conversion_complete,
    format_conversion_error,
    format_conversion_progress,
    format_files_received,
    format_multi_conversion_summary,
    format_queue_status_detailed,
)
from src.utils.file_manager import FileManager
from src.utils.history import HistoryEntry, HistoryManager
from src.utils.queue_manager import queue_manager
from src.utils.security import (
    filename_sanitizer,
    input_validator,
    rate_limiter,
)

logger = logging.getLogger(__name__)

# Telegram bot upload limit
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024  # 50MB


async def compress_video_for_telegram(
    input_path: Path, target_size_mb: int = 48
) -> Optional[Path]:
    """
    Compress a video file to fit within Telegram's size limit.
    Uses ffmpeg with aggressive compression settings.
    Returns the compressed file path, or None if compression fails.
    """
    output_path = input_path.parent / f"compressed_{input_path.name}"

    # Check if ffmpeg is available
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        logger.warning("ffmpeg not found, cannot compress video")
        return None

    try:
        # Get video duration for bitrate calculation
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ]
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                probe_cmd, capture_output=True, text=True, timeout=30
            ),
        )
        duration = float(result.stdout.strip()) if result.stdout.strip() else 60

        # Calculate target bitrate (in kbps)
        # target_size in KB, duration in seconds
        target_bitrate = int((target_size_mb * 8 * 1024) / duration * 0.9)
        video_bitrate = max(
            min(target_bitrate - 128, 2000), 200
        )  # Leave 128k for audio

        # Compress with ffmpeg
        compress_cmd = [
            "ffmpeg",
            "-i",
            str(input_path),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-b:v",
            f"{video_bitrate}k",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-y",
            str(output_path),
        ]

        logger.info(
            f"Compressing video to ~{target_size_mb}MB (bitrate: {video_bitrate}k)"
        )

        process = await asyncio.create_subprocess_exec(
            *compress_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

        if process.returncode == 0 and output_path.exists():
            new_size = output_path.stat().st_size
            logger.info(f"Compression successful: {new_size / 1024 / 1024:.1f}MB")
            return output_path
        else:
            logger.error(f"ffmpeg compression failed: {stderr.decode()[:200]}")
            return None

    except Exception as e:
        logger.error(f"Video compression error: {e}")
        if output_path.exists():
            output_path.unlink()
        return None


async def compress_image_for_telegram(
    input_path: Path, target_size_mb: int = 48
) -> Optional[Path]:
    """
    Compress an image file to fit within Telegram's size limit.
    Uses Pillow with quality reduction.
    """
    try:
        from PIL import Image

        output_path = input_path.parent / f"compressed_{input_path.name}"

        with Image.open(input_path) as img:
            # Convert to RGB if needed (for JPEG output)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Try progressive quality reduction
            for quality in [85, 70, 55, 40, 25]:
                img.save(output_path, "JPEG", quality=quality, optimize=True)
                if output_path.stat().st_size <= target_size_mb * 1024 * 1024:
                    logger.info(f"Image compressed at quality={quality}")
                    return output_path

            # Still too large, resize
            scale = 0.7
            while scale > 0.1:
                new_size = (int(img.width * scale), int(img.height * scale))
                resized = img.resize(new_size, Image.LANCZOS)
                resized.save(output_path, "JPEG", quality=70, optimize=True)
                if output_path.stat().st_size <= target_size_mb * 1024 * 1024:
                    logger.info(f"Image resized to {new_size} and compressed")
                    return output_path
                scale -= 0.1

        logger.warning("Could not compress image enough")
        return None

    except Exception as e:
        logger.error(f"Image compression error: {e}")
        return None


async def compress_to_archive(
    input_path: Path, target_size_mb: int = 48
) -> Optional[Path]:
    """
    Compress a file into a ZIP archive.
    Useful for documents and other compressible files.
    """
    import zipfile

    try:
        output_path = input_path.parent / f"{input_path.stem}.zip"

        with zipfile.ZipFile(
            output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zf:
            zf.write(input_path, input_path.name)

        new_size = output_path.stat().st_size
        if new_size <= target_size_mb * 1024 * 1024:
            logger.info(f"Compressed to ZIP: {new_size / 1024 / 1024:.1f}MB")
            return output_path
        else:
            output_path.unlink()
            return None

    except Exception as e:
        logger.error(f"Archive compression error: {e}")
        return None


async def try_compress_file(
    input_path: Path, file_type: str, target_size_mb: int = 48
) -> Optional[Path]:
    """
    Attempt to compress a file based on its type.
    Returns compressed path or None if compression fails/not possible.
    """
    file_type = file_type.lower()

    # Video files
    if file_type in {"mp4", "avi", "mkv", "mov", "webm", "flv", "m4v"}:
        return await compress_video_for_telegram(input_path, target_size_mb)

    # Image files
    if file_type in {"png", "jpeg", "jpg", "bmp", "tiff", "webp"}:
        return await compress_image_for_telegram(input_path, target_size_mb)

    # Try ZIP compression for other compressible formats
    if file_type in {"pdf", "docx", "xlsx", "txt", "json", "xml", "csv"}:
        return await compress_to_archive(input_path, target_size_mb)

    return None


async def split_file(input_path: Path, chunk_size_mb: int = 48) -> List[Path]:
    """
    Split a large file into smaller chunks.
    Returns list of chunk file paths.
    """
    chunk_size = chunk_size_mb * 1024 * 1024
    chunks = []

    try:
        file_size = input_path.stat().st_size
        num_chunks = (file_size + chunk_size - 1) // chunk_size

        with open(input_path, "rb") as f:
            for i in range(num_chunks):
                chunk_path = (
                    input_path.parent
                    / f"{input_path.stem}.part{i + 1}{input_path.suffix}"
                )
                with open(chunk_path, "wb") as chunk_file:
                    chunk_file.write(f.read(chunk_size))
                chunks.append(chunk_path)
                logger.info(f"Created chunk {i + 1}/{num_chunks}: {chunk_path.name}")

        return chunks

    except Exception as e:
        logger.error(f"File splitting error: {e}")
        # Cleanup partial chunks
        for chunk in chunks:
            if chunk.exists():
                chunk.unlink()
        return []


class FileHandlers:
    """Handles file uploads and conversion processing"""

    def __init__(
        self,
        converter_factory: ConverterFactory,
        history_manager: HistoryManager,
        file_manager: FileManager,
    ):
        self.converter = converter_factory
        self.history = history_manager
        self.files = file_manager
        self._conversion_semaphore = asyncio.Semaphore(3)  # Max 3 concurrent

    async def _animate_progress(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        message,
        filename: str,
        source_format: str,
        target_format: str,
    ):
        """Animate progress message during conversion"""
        stages = ["Processing", "Converting", "Finalizing"]
        progress = 10
        stage_idx = 0

        try:
            while True:
                await asyncio.sleep(2)  # Update every 2 seconds

                # Increment progress
                progress = min(90, progress + 15)
                if progress > 60:
                    stage_idx = 2
                elif progress > 30:
                    stage_idx = 1

                try:
                    await message.edit_text(
                        format_conversion_progress(
                            filename,
                            source_format,
                            target_format,
                            progress=progress,
                            stage=stages[stage_idx],
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    # Message may have been deleted or edited
                    pass
        except asyncio.CancelledError:
            pass

    async def _safe_edit_or_send(
        self,
        message,
        context,
        chat_id: int,
        text: str,
        parse_mode=None,
        reply_markup=None,
    ):
        """Safely edit a message or send a new one if editing fails"""
        try:
            await message.edit_text(
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming document files"""
        message = update.message
        document = message.document
        user_id = update.effective_user.id

        # Rate limiting check
        if not rate_limiter.check_message_limit(user_id):
            remaining = rate_limiter.get_remaining_messages(user_id)
            await message.reply_text(
                f"⚠️ Rate limit exceeded. Please wait a moment.\n"
                f"You can send {remaining} more files per minute.",
                reply_markup=create_error_menu(),
            )
            return

        # Validate file
        if not self._validate_file(document):
            await message.reply_text(
                "❌ Unsupported file type or file too large.",
                reply_markup=create_error_menu(),
            )
            return

        # Get file format
        file_ext = self._get_file_extension(document.file_name)
        if not file_ext or file_ext.lower() not in ALL_INPUT_FORMATS:
            await message.reply_text(
                f"❌ Unsupported format: `{file_ext}`\n"
                "Use /formats to see supported types.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_error_menu(),
            )
            return

        # Initialize user data if needed
        if "pending_files" not in context.user_data:
            context.user_data["pending_files"] = []

        # Download file
        try:
            file = await context.bot.get_file(document.file_id)
            file_bytes = await file.download_as_bytearray()

            # Save to temp storage
            file_path = await self.files.save_file(
                bytes(file_bytes), document.file_name, user_id
            )

            # Add to pending files
            file_info = {
                "path": str(file_path),
                "name": document.file_name,
                "size": document.file_size,
                "format": file_ext.lower(),
                "file_id": document.file_id,
            }
            context.user_data["pending_files"].append(file_info)
            context.user_data["input_format"] = file_ext.lower()

            # Check if we have a target format set
            target_format = context.user_data.get("target_format")
            if target_format and context.user_data.get("ready_to_convert"):
                # Start conversion immediately
                await self._process_conversion(
                    update, context, [file_info], target_format
                )
            else:
                # Show format selection
                pending = context.user_data["pending_files"]
                if len(pending) == 1:
                    await message.reply_text(
                        format_files_received([file_info], file_ext),
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=create_format_selection_menu(file_ext),
                    )
                else:
                    await message.reply_text(
                        f"📥 Added `{document.file_name}`\n"
                        f"Total: {len(pending)} files ready",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=create_multi_file_menu(len(pending)),
                    )

        except Exception as e:
            logger.error(f"File download error: {e}")
            await message.reply_text(
                f"❌ Failed to process file: {e}", reply_markup=create_error_menu()
            )

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming photos"""
        message = update.message
        photo = message.photo[-1]  # Get largest size
        user_id = update.effective_user.id

        try:
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()

            # Photos are JPEG by default
            filename = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            file_path = await self.files.save_file(bytes(file_bytes), filename, user_id)

            file_info = {
                "path": str(file_path),
                "name": filename,
                "size": len(file_bytes),
                "format": "jpeg",
                "file_id": photo.file_id,
            }

            if "pending_files" not in context.user_data:
                context.user_data["pending_files"] = []
            context.user_data["pending_files"].append(file_info)
            context.user_data["input_format"] = "jpeg"

            await message.reply_text(
                format_files_received([file_info], "jpeg"),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_selection_menu("jpeg"),
            )

        except Exception as e:
            logger.error(f"Photo processing error: {e}")
            await message.reply_text(
                f"❌ Failed to process photo: {e}", reply_markup=create_error_menu()
            )

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming video files"""
        message = update.message
        video = message.video
        user_id = update.effective_user.id

        # Get mime type to determine format
        mime_type = video.mime_type or "video/mp4"
        ext_map = {
            "video/mp4": "mp4",
            "video/webm": "webm",
            "video/x-matroska": "mkv",
            "video/quicktime": "mov",
            "video/x-msvideo": "avi",
        }
        file_ext = ext_map.get(mime_type, "mp4")

        try:
            file = await context.bot.get_file(video.file_id)
            file_bytes = await file.download_as_bytearray()

            filename = video.file_name or f"video.{file_ext}"
            file_path = await self.files.save_file(bytes(file_bytes), filename, user_id)

            file_info = {
                "path": str(file_path),
                "name": filename,
                "size": video.file_size,
                "format": file_ext,
                "file_id": video.file_id,
            }

            if "pending_files" not in context.user_data:
                context.user_data["pending_files"] = []
            context.user_data["pending_files"].append(file_info)
            context.user_data["input_format"] = file_ext

            await message.reply_text(
                format_files_received([file_info], file_ext),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_selection_menu(file_ext),
            )

        except Exception as e:
            logger.error(f"Video processing error: {e}")
            await message.reply_text(
                f"❌ Failed to process video: {e}", reply_markup=create_error_menu()
            )

    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming audio files"""
        message = update.message
        audio = message.audio or message.voice
        user_id = update.effective_user.id

        # Determine format from mime type
        mime_type = getattr(audio, "mime_type", "audio/mpeg") or "audio/mpeg"
        ext_map = {
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/ogg": "ogg",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/flac": "flac",
            "audio/aac": "aac",
            "audio/mp4": "m4a",
        }
        file_ext = ext_map.get(mime_type, "mp3")

        try:
            file = await context.bot.get_file(audio.file_id)
            file_bytes = await file.download_as_bytearray()

            filename = getattr(audio, "file_name", None)
            filename = filename or f"audio.{file_ext}"
            file_path = await self.files.save_file(bytes(file_bytes), filename, user_id)

            file_info = {
                "path": str(file_path),
                "name": filename,
                "size": audio.file_size or len(file_bytes),
                "format": file_ext,
                "file_id": audio.file_id,
            }

            if "pending_files" not in context.user_data:
                context.user_data["pending_files"] = []
            context.user_data["pending_files"].append(file_info)
            context.user_data["input_format"] = file_ext

            await message.reply_text(
                format_files_received([file_info], file_ext),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_selection_menu(file_ext),
            )

        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            await message.reply_text(
                f"❌ Failed to process audio: {e}", reply_markup=create_error_menu()
            )

    async def process_selected_format(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, target_format: str
    ):
        """Process conversion after format selection"""
        user_data = context.user_data
        pending_files = user_data.get("pending_files", [])

        if not pending_files:
            await update.callback_query.edit_message_text(
                "❌ No files to convert. Send a file first.",
                reply_markup=create_main_menu(),
            )
            return

        await self._process_conversion(update, context, pending_files, target_format)

    async def _process_conversion(
        self,
        update,
        context: ContextTypes.DEFAULT_TYPE,
        files: List[Dict],
        target_format: str,
    ):
        """Process actual file conversion with queue management"""
        # Handle both Update objects and CallbackQuery objects
        if hasattr(update, "effective_user"):
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
        else:
            # It's a CallbackQuery
            user_id = update.from_user.id
            chat_id = update.message.chat_id
        results = []

        # Check queue status and show to user
        queue_info = queue_manager.get_user_queue_position(user_id)
        if queue_info["total_pending"] > 0:
            await context.bot.send_message(
                chat_id=chat_id,
                text=format_queue_status_detailed(
                    queue_info["user_pending"] + 1,
                    queue_info["total_pending"] + 1,
                    queue_info["active_workers"],
                    queue_info["max_workers"],
                ),
                parse_mode=ParseMode.MARKDOWN,
            )

        async with self._conversion_semaphore:
            for file_info in files:
                try:
                    input_path = Path(file_info["path"])
                    source_format = file_info["format"]

                    # Check if file exists, if not try to re-download
                    if not input_path.exists() and file_info.get("file_id"):
                        logger.info(f"Re-downloading file: {file_info['name']}")
                        try:
                            tg_file = await context.bot.get_file(file_info["file_id"])
                            file_bytes = await tg_file.download_as_bytearray()
                            input_path = await self.files.save_file(
                                bytes(file_bytes), file_info["name"], user_id
                            )
                            file_info["path"] = str(input_path)
                        except Exception as download_err:
                            logger.error(f"Failed to re-download file: {download_err}")
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text="❌ Could not retrieve original file. "
                                "Please send the file again.",
                                reply_markup=create_error_menu(),
                            )
                            continue
                    elif not input_path.exists():
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"❌ File not found: `{file_info['name']}`\n"
                            f"Please send the file again.",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=create_error_menu(),
                        )
                        continue

                    # Send animated progress message
                    progress_msg = await context.bot.send_message(
                        chat_id=chat_id,
                        text=format_conversion_progress(
                            file_info["name"],
                            source_format,
                            target_format,
                            progress=10,
                            stage="Processing",
                        ),
                        parse_mode=ParseMode.MARKDOWN,
                    )

                    # Start progress animation task
                    animation_task = asyncio.create_task(
                        self._animate_progress(
                            context,
                            progress_msg,
                            file_info["name"],
                            source_format,
                            target_format,
                        )
                    )

                    try:
                        # Perform conversion
                        result = await asyncio.wait_for(
                            self.converter.convert(input_path, target_format),
                            timeout=CONVERSION_TIMEOUT,
                        )
                    finally:
                        # Stop animation
                        animation_task.cancel()
                        try:
                            await animation_task
                        except asyncio.CancelledError:
                            pass

                    if result.success and result.output_path:
                        output_path = result.output_path
                        file_size = result.file_size

                        # Check file size and handle large files
                        if file_size > TELEGRAM_MAX_SIZE:
                            await self._safe_edit_or_send(
                                progress_msg,
                                context,
                                chat_id,
                                f"⚠️ File is {file_size / 1024 / 1024:.1f}MB "
                                f"(limit: 50MB)\n\n🔄 Attempting compression...",
                            )

                            # Try compression based on file type
                            compressed = await try_compress_file(
                                output_path,
                                target_format,
                                target_size_mb=48,
                            )

                            if compressed and compressed.exists():
                                # Use compressed file
                                await self.files.cleanup_file(output_path)
                                output_path = compressed
                                file_size = compressed.stat().st_size
                                await self._safe_edit_or_send(
                                    progress_msg,
                                    context,
                                    chat_id,
                                    f"✅ Compressed to {file_size / 1024 / 1024:.1f}MB",
                                )

                            # If still too large, warn user
                            if file_size > TELEGRAM_MAX_SIZE:
                                size_mb = file_size / 1024 / 1024
                                await self._safe_edit_or_send(
                                    progress_msg,
                                    context,
                                    chat_id,
                                    f"⚠️ *File too large* ({size_mb:.1f}MB)\n\n"
                                    "Telegram bots cannot send > 50MB.\n\n"
                                    "*Options:*\n"
                                    "• Use smaller source file\n"
                                    "• Convert to compressed format\n"
                                    "• Use @TGFileSplitBot to split",
                                    parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=create_error_menu(),
                                )
                                results.append(
                                    {
                                        "filename": file_info["name"],
                                        "target_format": target_format,
                                        "success": False,
                                        "error": f"Too large: {int(size_mb)}MB",
                                    }
                                )
                                await self.files.cleanup_file(output_path)
                                await self.files.cleanup_file(input_path)
                                continue

                        # Send converted file
                        with open(output_path, "rb") as f:
                            sent_msg = await context.bot.send_document(
                                chat_id=chat_id,
                                document=f,
                                filename=output_path.name,
                                caption=format_conversion_complete(
                                    file_info["name"],
                                    source_format,
                                    target_format,
                                    result.conversion_time,
                                    file_size,
                                    result.conversion_id,
                                ),
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=create_result_menu(
                                    result.conversion_id, source_format
                                ),
                            )

                        # Store last conversion info for "Convert to Another Format"
                        context.user_data["last_conversion"] = {
                            "conv_id": result.conversion_id,
                            "filename": file_info["name"],
                            "input_format": source_format,
                            "path": str(input_path),
                            "file_id": file_info.get("file_id"),
                        }

                        # Save to history (with null checks)
                        sent_file_id = None
                        sent_message_id = None
                        if sent_msg:
                            sent_message_id = sent_msg.message_id
                            if sent_msg.document:
                                sent_file_id = sent_msg.document.file_id

                        entry = HistoryEntry(
                            id=result.conversion_id,
                            user_id=user_id,
                            original_name=file_info["name"],
                            converted_name=output_path.name,
                            source_format=source_format,
                            target_format=target_format,
                            file_size=file_size,
                            timestamp=datetime.now().isoformat(),
                            status="success",
                            file_id=sent_file_id,
                            message_id=sent_message_id,
                            chat_id=chat_id,
                        )
                        await self.history.add_entry(user_id, entry)

                        results.append(
                            {
                                "filename": file_info["name"],
                                "target_format": target_format,
                                "success": True,
                                "conv_id": result.conversion_id,
                                "source_format": source_format,
                            }
                        )

                        # Cleanup
                        await self.files.cleanup_file(output_path)

                    else:
                        # Conversion failed
                        await progress_msg.edit_text(
                            format_conversion_error(
                                file_info["name"],
                                result.error_message or "Unknown error",
                            ),
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=create_error_menu(),
                        )

                        results.append(
                            {
                                "filename": file_info["name"],
                                "target_format": target_format,
                                "success": False,
                                "error": result.error_message,
                            }
                        )

                    # PRIVACY: Immediately cleanup all files after processing
                    # Don't keep any user files on server
                    await self.files.cleanup_file(input_path)
                    logger.debug(f"Cleaned up input: {input_path}")

                except asyncio.TimeoutError:
                    results.append(
                        {
                            "filename": file_info["name"],
                            "target_format": target_format,
                            "success": False,
                            "error": "Conversion timed out",
                        }
                    )
                    # Cleanup on timeout
                    await self.files.cleanup_file(Path(file_info["path"]))

                except Exception as e:
                    logger.error(f"Conversion error: {e}")
                    results.append(
                        {
                            "filename": file_info["name"],
                            "target_format": target_format,
                            "success": False,
                            "error": str(e),
                        }
                    )
                    # Cleanup on error
                    await self.files.cleanup_file(Path(file_info["path"]))

        # Clear pending files
        context.user_data["pending_files"] = []
        context.user_data["target_format"] = None
        context.user_data["ready_to_convert"] = False

        # Send summary if multiple files
        if len(results) > 1:
            # Get last successful conversion for "Convert to Another Format"
            last_success = next(
                (r for r in reversed(results) if r.get("success")), None
            )
            last_fmt = last_success.get("source_format") if last_success else None
            last_id = last_success.get("conv_id", "") if last_success else ""

            await context.bot.send_message(
                chat_id=chat_id,
                text=format_multi_conversion_summary(results),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_result_menu(last_id, last_fmt),
            )

    def _validate_file(self, document: Document) -> bool:
        """Validate uploaded file for security and size"""
        if not document:
            return False
        if document.file_size and document.file_size > MAX_UPLOAD_SIZE:
            return False

        # Check for blocked extensions
        if document.file_name:
            if not filename_sanitizer.is_safe_extension(document.file_name):
                logger.warning(f"Blocked unsafe extension: {document.file_name}")
                return False

        return True

    def _get_file_extension(self, filename: str) -> Optional[str]:
        """Extract file extension from filename"""
        if not filename or "." not in filename:
            return None
        ext = filename.rsplit(".", 1)[-1].lower()
        # Validate format
        return input_validator.validate_format(ext)
