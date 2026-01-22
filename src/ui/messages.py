"""
Message Templates and Formatters
"""

from datetime import datetime
from typing import Dict, List


def format_welcome_message(username: str = None) -> str:
    """Format welcome message with user greeting"""
    greeting = f"Hello, {username}! 👋\n\n" if username else ""
    return f"""{greeting}🔄 *Welcome to File Converter Bot!*

I can convert files between multiple formats:

📄 *Documents*: CSV, PDF, DOCX, XML, JSON, YAML, MD, TXT
📚 *E-Books*: FB2, EPUB, MOBI
🖼️ *Images*: GIF, SVG, ICO, PNG, JPEG, WEBP, BMP, TIFF
🎬 *Video*: WEBM, MP4, AVI, MKV, MOV
🎵 *Audio*: MP3, WAV, OGG, FLAC, AAC
🎮 *3D Models*: OBJ, FBX, GLB, GLTF, STL
📊 *Data*: ETS, XLSX, XLS

*Features:*
✅ Multiple file conversion at once
✅ Conversion history recovery
✅ Fast local processing
✅ Works on all Telegram platforms

Send me a file to get started! 📎"""


def format_help_message() -> str:
    """Format help message"""
    return """📖 *Help Guide*

*Commands:*
/start - Start the bot
/help - Show this help
/convert - Start conversion mode
/history - View conversion history
/recover \\<id\\> - Recover file by ID
/settings - Bot settings
/cancel - Cancel current operation
/formats - Show supported formats

*How to convert:*
1\\. Send me one or multiple files
2\\. Select target format from the menu
3\\. Wait for conversion \\(progress shown\\)
4\\. Download your converted files

*Tips:*
• You can forward files from other chats
• Send multiple files, then choose format
• Use /history to find old conversions
• Conversion IDs help you recover files

*Limits:*
• Max file size: 2GB \\(local server\\)
• Concurrent conversions: 3
• History retention: 30 days"""


def format_conversion_started(
    filename: str, source_format: str, target_format: str
) -> str:
    """Format conversion started message"""
    return f"""⏳ *Converting...*

📄 File: `{filename}`
🔄 {source_format.upper()} → {target_format.upper()}

Please wait, this may take a moment..."""


def format_conversion_complete(
    filename: str,
    source_format: str,
    target_format: str,
    conversion_time: float,
    file_size: int,
    conversion_id: str,
) -> str:
    """Format conversion complete message"""
    size_str = format_file_size(file_size)
    return f"""✅ *Conversion Complete!*

📄 File: `{filename}`
🔄 {source_format.upper()} → {target_format.upper()}
⏱️ Time: {conversion_time:.2f}s
📦 Size: {size_str}
🆔 ID: `{conversion_id}`

Use ID to recover this file later with /recover"""


def format_conversion_error(filename: str, error_message: str) -> str:
    """Format conversion error message with truncation for long errors"""
    # Truncate error message to prevent Telegram API errors
    max_error_len = 200
    if len(error_message) > max_error_len:
        # Try to find a meaningful part of the error
        if "Error:" in error_message:
            error_message = error_message.split("Error:")[-1].strip()
        if "error:" in error_message:
            error_message = error_message.split("error:")[-1].strip()
        # Still too long? Truncate
        if len(error_message) > max_error_len:
            error_message = error_message[:max_error_len] + "..."

    # Escape special markdown characters in error
    error_message = escape_markdown(error_message)

    return f"""❌ *Conversion Failed*

📄 File: `{filename}`
⚠️ Error: {error_message}

Please try again or use /help for assistance."""


def escape_markdown(text: str) -> str:
    """Escape special markdown characters for Telegram"""
    special_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text


def format_files_received(files: List[Dict], detected_format: str) -> str:
    """Format files received message"""
    file_list = "\n".join(
        [f"  • `{f['name']}` ({format_file_size(f['size'])})" for f in files]
    )

    return f"""📥 *Files Received*

{file_list}

Detected format: *{detected_format.upper()}*
Select target format to start conversion:"""


def format_history_item(item: Dict) -> str:
    """Format a single history item"""
    timestamp = datetime.fromisoformat(item.get("timestamp", ""))
    time_str = timestamp.strftime("%Y-%m-%d %H:%M")

    return f"""📋 *Conversion Details*

🆔 ID: `{item.get("id", "N/A")}`
📄 Original: `{item.get("original_name", "Unknown")}`
🔄 Conversion: {item.get("source_format", "?").upper()} → \
{item.get("target_format", "?").upper()}
📦 Size: {format_file_size(item.get("size", 0))}
📅 Date: {time_str}
✅ Status: {item.get("status", "Unknown")}"""


def format_history_empty() -> str:
    """Format empty history message"""
    return """📭 *No Conversion History*

You haven't converted any files yet.
Send me a file to get started!"""


def format_settings(settings: Dict) -> str:
    """Format settings message"""
    auto_cleanup = "✅ Enabled" if settings.get("auto_cleanup", True) else "❌ Disabled"
    notifications = (
        "✅ Enabled" if settings.get("notifications", True) else "❌ Disabled"
    )
    quality = settings.get("quality", "high").capitalize()

    return f"""⚙️ *Settings*

🧹 Auto Cleanup: {auto_cleanup}
   _{get_setting_description("auto_cleanup")}_

🔔 Notifications: {notifications}
   _{get_setting_description("notifications")}_

📊 Quality: {quality}
   _{get_setting_description("quality")}_

Tap a setting to change it."""


def get_setting_description(setting: str) -> str:
    """Get description for a setting"""
    descriptions = {
        "auto_cleanup": "Remove temp files after sending",
        "notifications": "Show conversion progress updates",
        "quality": "Output quality \\(affects file size\\)",
    }
    return descriptions.get(setting, "")


def format_format_info(category_name: str, formats: set) -> str:
    """Format information about a format category"""
    format_list = ", ".join(sorted(formats))
    return f"""📁 *{category_name} Formats*

Supported formats: `{format_list}`

Send a file in any of these formats to convert it."""


def format_multi_conversion_summary(results: List[Dict]) -> str:
    """Format summary for multiple file conversions"""
    success_count = sum(1 for r in results if r.get("success"))
    fail_count = len(results) - success_count

    summary_lines = []
    for r in results:
        status = "✅" if r.get("success") else "❌"
        summary_lines.append(
            f"{status} `{r.get('filename', 'Unknown')}` → "
            f"{r.get('target_format', '?').upper()}"
        )

    summary = "\n".join(summary_lines)

    return f"""📊 *Conversion Summary*

{summary}

✅ Successful: {success_count}
❌ Failed: {fail_count}"""


def format_file_size(size_bytes: int) -> str:
    """Format file size to human readable string"""
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB"]
    unit_index = 0

    size = float(size_bytes)
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    return f"{size:.1f} {units[unit_index]}"


def format_progress(current: int, total: int, width: int = 20) -> str:
    """Format progress bar"""
    filled = int(width * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    percent = (current / total * 100) if total > 0 else 0
    return f"[{bar}] {percent:.1f}%"


def format_queue_status(position: int, total_queue: int) -> str:
    """Format queue status message"""
    if position == 0:
        return "🔄 Processing now..."
    return f"⏳ Queue position: {position}/{total_queue}"


def format_rate_limit_error(remaining: int, wait_seconds: int = 60) -> str:
    """Format rate limit exceeded error"""
    return f"""⚠️ *Rate Limit Exceeded*

You're sending files too quickly.
Please wait about {wait_seconds} seconds.

Remaining requests: {remaining}"""


def format_file_too_large_error(
    filename: str, file_size_mb: float, max_size_mb: float = 50.0
) -> str:
    """Format file too large error with helpful tips"""
    return f"""⚠️ *File Too Large for Telegram*

📄 File: `{filename}`
📦 Size: {file_size_mb:.1f} MB
📏 Limit: {max_size_mb:.1f} MB

*Options:*
• Download via direct link \\(if available\\)
• Use @TGFileSplitBot to split & download
• Convert to a more compressed format first

The converted file has been saved locally."""


def format_unsupported_format_error(
    detected_format: str, similar_formats: list = None
) -> str:
    """Format unsupported format error with suggestions"""
    msg = f"""❌ *Unsupported Format*

Detected: `{detected_format}`

Use /formats to see all supported formats."""

    if similar_formats:
        suggestions = ", ".join(similar_formats[:5])
        msg += f"\n\n*Did you mean:* {suggestions}"

    return msg


def format_security_blocked_error(reason: str) -> str:
    """Format security block error"""
    return f"""🛡️ *Security Block*

This file was blocked for security reasons:
{escape_markdown(reason)}

If you believe this is a mistake, please try:
• Renaming the file with a safe extension
• Removing any special characters from filename"""


def format_conversion_tips() -> str:
    """Format helpful conversion tips"""
    return """💡 *Conversion Tips*

*For smaller files:*
• Use WEBP for images \\(great compression\\)
• Use MP3/AAC for audio \\(vs WAV/FLAC\\)
• Use WEBM/MP4 for video \\(vs AVI\\)

*For quality:*
• Use PNG/TIFF for lossless images
• Use FLAC/WAV for lossless audio
• Use /settings to adjust quality level

*For speed:*
• Send multiple files at once
• Avoid unnecessary format round\\-trips
• Use simpler formats when possible"""


def format_archive_info(archive_name: str, file_count: int, total_size_str: str) -> str:
    """Format archive contents info"""
    return f"""📦 *Archive Contents*

📄 Archive: `{archive_name}`
📁 Files: {file_count}
📦 Total size: {total_size_str}

Choose what to do with these files:"""


# ============== Animated Progress Messages ==============


def get_progress_frames() -> list:
    """Get animation frames for progress indicator"""
    return ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def get_loading_animation() -> list:
    """Get loading bar animation frames"""
    return [
        "▱▱▱▱▱▱▱▱▱▱",
        "▰▱▱▱▱▱▱▱▱▱",
        "▰▰▱▱▱▱▱▱▱▱",
        "▰▰▰▱▱▱▱▱▱▱",
        "▰▰▰▰▱▱▱▱▱▱",
        "▰▰▰▰▰▱▱▱▱▱",
        "▰▰▰▰▰▰▱▱▱▱",
        "▰▰▰▰▰▰▰▱▱▱",
        "▰▰▰▰▰▰▰▰▱▱",
        "▰▰▰▰▰▰▰▰▰▱",
        "▰▰▰▰▰▰▰▰▰▰",
    ]


def format_animated_processing(
    filename: str,
    frame_idx: int,
    stage: str = "Converting",
) -> str:
    """Format animated processing message"""
    frames = get_progress_frames()
    frame = frames[frame_idx % len(frames)]

    return f"""{frame} *{stage}...*

📄 File: `{filename}`

Please wait..."""


def format_progress_bar(
    current: int,
    total: int,
    width: int = 10,
    show_percent: bool = True,
) -> str:
    """Format a visual progress bar"""
    if total <= 0:
        percent = 0
        filled = 0
    else:
        percent = min(100, int(current / total * 100))
        filled = int(width * current / total)

    bar = "▰" * filled + "▱" * (width - filled)

    if show_percent:
        return f"[{bar}] {percent}%"
    return f"[{bar}]"


def format_conversion_progress(
    filename: str,
    source_format: str,
    target_format: str,
    progress: int = 0,
    stage: str = "Processing",
) -> str:
    """Format conversion progress with visual bar"""
    bar = format_progress_bar(progress, 100)

    stages = {
        "downloading": "📥 Downloading",
        "processing": "⚙️ Processing",
        "converting": "🔄 Converting",
        "compressing": "📦 Compressing",
        "uploading": "📤 Uploading",
    }
    stage_icon = stages.get(stage.lower(), "⏳ " + stage)

    return f"""*{stage_icon}*

📄 `{filename}`
🔄 {source_format.upper()} → {target_format.upper()}

{bar}"""


def format_queue_status_detailed(
    position: int,
    total_queue: int,
    active_workers: int,
    max_workers: int,
) -> str:
    """Format detailed queue status"""
    if position == 0:
        return f"""🔄 *Processing Now*

Workers: {active_workers}/{max_workers} active
Your conversion is in progress..."""

    # Estimate wait time (rough: 30s per task ahead)
    estimated_wait = position * 30
    wait_str = (
        f"{estimated_wait // 60}m {estimated_wait % 60}s"
        if estimated_wait >= 60
        else f"{estimated_wait}s"
    )

    return f"""⏳ *In Queue*

📊 Position: {position} of {total_queue}
⏱️ Est\\. wait: ~{wait_str}
👥 Workers: {active_workers}/{max_workers}

You'll be notified when processing starts\\."""


def format_upload_started(filename: str, file_size: int) -> str:
    """Format upload started message with animation"""
    size_str = format_file_size(file_size)
    return f"""📥 *Receiving File*

📄 `{filename}`
📦 Size: {size_str}

{format_progress_bar(0, 100)}"""


def format_conversion_stages() -> Dict[str, str]:
    """Get conversion stage messages"""
    return {
        "received": "📥 File received",
        "validating": "🔍 Validating file...",
        "queued": "📋 Added to queue",
        "starting": "🚀 Starting conversion...",
        "converting": "🔄 Converting...",
        "compressing": "📦 Compressing output...",
        "sending": "📤 Sending file...",
        "complete": "✅ Complete!",
        "failed": "❌ Failed",
    }


def format_files_cleanup_notice() -> str:
    """Notice about automatic file cleanup"""
    return """🔒 *Privacy Notice*

Your files are automatically deleted from our servers
immediately after conversion for your privacy.

Use /recover with conversion ID to re\\-download from history\\."""


def format_multi_user_notice(queue_position: int) -> str:
    """Format notice when other users are in queue"""
    if queue_position <= 1:
        return ""
    return f"""
_\\({queue_position - 1} other conversions ahead\\)_"""
