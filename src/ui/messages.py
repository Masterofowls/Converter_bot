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
    """Format conversion error message"""
    return f"""❌ *Conversion Failed*

📄 File: `{filename}`
⚠️ Error: {error_message}

Please try again or use /help for assistance."""


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
