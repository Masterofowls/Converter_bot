"""
Configuration module for Converter Bot
All settings and constants are defined here
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

BOT_USERNAME = os.getenv("BOT_USERNAME", "@convertationsbot")
BOT_ID = int(os.getenv("BOT_ID", "8575519773"))

# Paths
BASE_DIR = Path(__file__).parent.parent
TEMP_DIR = BASE_DIR / "temp"
DATA_DIR = BASE_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"

# Ensure directories exist
TEMP_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# File size limits (in bytes)
# 2GB - Telegram Bot API limit for local server
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB for cloud Telegram
LOCAL_API_MAX_SIZE = 2000 * 1024 * 1024  # 2GB for local Bot API

# Conversion timeout (seconds)
CONVERSION_TIMEOUT = 600  # 10 minutes

# Rate limiting settings
RATE_LIMIT_MESSAGES = 30  # Max messages per window
RATE_LIMIT_WINDOW = 60  # Window in seconds (1 minute)
RATE_LIMIT_CONVERSIONS = 10  # Max conversions per hour
RATE_LIMIT_CONVERSION_WINDOW = 3600  # 1 hour

# Security settings
MAX_FILENAME_LENGTH = 255
ALLOWED_FILENAME_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ()[]{}!@#$%^&+=~"
)
BLOCKED_EXTENSIONS = {
    "exe",
    "bat",
    "cmd",
    "sh",
    "ps1",
    "vbs",
    "js",
    "msi",
    "scr",
    "com",
    "pif",
    "dll",
    "sys",
}


# Supported formats organized by category
@dataclass
class FormatCategory:
    name: str
    formats: Set[str]
    icon: str
    description: str


FORMAT_CATEGORIES: Dict[str, FormatCategory] = {
    "documents": FormatCategory(
        name="Documents",
        formats={"csv", "pdf", "docx", "xml", "json", "yaml", "md", "txt"},
        icon="📄",
        description="Text and document files",
    ),
    "ebooks": FormatCategory(
        name="E-Books",
        formats={"fb2", "epub", "mobi"},
        icon="📚",
        description="E-book formats",
    ),
    "images": FormatCategory(
        name="Images",
        formats={
            "gif",
            "svg",
            "ico",
            "png",
            "jpeg",
            "jpg",
            "webp",
            "bmp",
            "tiff",
        },
        icon="🖼️",
        description="Image files",
    ),
    "video": FormatCategory(
        name="Video",
        formats={"webm", "mp4", "avi", "mkv", "mov", "flv"},
        icon="🎬",
        description="Video files",
    ),
    "audio": FormatCategory(
        name="Audio",
        formats={"mp3", "wav", "ogg", "flac", "aac", "m4a"},
        icon="🎵",
        description="Audio files",
    ),
    "3d_models": FormatCategory(
        name="3D Models",
        formats={"obj", "fbx", "glb", "gltf", "stl", "dae"},
        icon="🎮",
        description="3D model files",
    ),
    "data": FormatCategory(
        name="Data",
        formats={"ets", "xlsx", "xls"},
        icon="📊",
        description="Data and spreadsheet files",
    ),
    "archives": FormatCategory(
        name="Archives",
        formats={"zip", "7z", "tar", "gz", "rar"},
        icon="📦",
        description="Compressed archive files",
    ),
}

# All supported input formats
ALL_INPUT_FORMATS: Set[str] = set()
for cat in FORMAT_CATEGORIES.values():
    ALL_INPUT_FORMATS.update(cat.formats)

# Conversion matrix - what can be converted to what
CONVERSION_MATRIX: Dict[str, List[str]] = {
    # Documents
    "csv": ["json", "xml", "xlsx", "pdf", "md", "txt", "yaml"],
    "pdf": ["txt", "docx", "md", "json"],
    "docx": ["pdf", "txt", "md", "json"],
    "xml": ["json", "yaml", "csv", "txt"],
    "json": ["xml", "yaml", "csv", "txt", "md"],
    "yaml": ["json", "xml", "txt"],
    "md": ["pdf", "txt", "docx", "html"],
    "txt": ["pdf", "md", "docx"],
    # E-books
    "fb2": ["epub", "pdf", "txt", "mobi"],
    "epub": ["fb2", "pdf", "txt", "mobi"],
    "mobi": ["epub", "fb2", "pdf", "txt"],
    # Images
    "gif": ["mp4", "webm", "png", "webp"],
    "svg": ["png", "pdf", "jpeg", "webp", "ico"],
    "ico": ["png", "jpeg", "webp", "svg"],
    "png": ["jpeg", "webp", "ico", "pdf", "svg", "bmp", "gif", "tiff"],
    "jpeg": ["png", "webp", "ico", "pdf", "bmp", "gif", "tiff"],
    "jpg": ["png", "webp", "ico", "pdf", "bmp", "gif", "tiff"],
    "webp": ["png", "jpeg", "gif", "ico"],
    "bmp": ["png", "jpeg", "webp", "gif"],
    "tiff": ["png", "jpeg", "webp", "pdf"],
    # Video
    "webm": ["mp4", "gif", "mp3", "avi", "mkv"],
    "mp4": ["webm", "gif", "mp3", "avi", "mkv", "mov"],
    "avi": ["mp4", "webm", "mkv", "gif", "mp3"],
    "mkv": ["mp4", "webm", "avi", "mp3"],
    "mov": ["mp4", "webm", "avi", "gif", "mp3"],
    "flv": ["mp4", "webm", "avi", "mp3"],
    # Audio
    "mp3": ["wav", "ogg", "flac", "aac", "m4a"],
    "wav": ["mp3", "ogg", "flac", "aac"],
    "ogg": ["mp3", "wav", "flac", "aac"],
    "flac": ["mp3", "wav", "ogg", "aac"],
    "aac": ["mp3", "wav", "ogg", "flac"],
    "m4a": ["mp3", "wav", "ogg", "flac"],
    # 3D Models
    "obj": ["glb", "gltf", "stl", "fbx"],
    "fbx": ["glb", "gltf", "obj", "stl"],
    "glb": ["gltf", "obj", "stl"],
    "gltf": ["glb", "obj", "stl"],
    "stl": ["obj", "glb", "gltf"],
    "dae": ["obj", "glb", "gltf", "fbx"],
    # Data
    "ets": ["csv", "json", "xml", "xlsx"],
    "xlsx": ["csv", "json", "xml", "pdf"],
    "xls": ["csv", "json", "xml", "xlsx", "pdf"],
    # Archives
    "zip": ["tar", "7z"],
    "7z": ["zip", "tar"],
    "tar": ["zip", "7z", "gz"],
    "gz": ["tar", "zip"],
    "rar": ["zip", "7z", "tar"],
}

# External API configurations
EXTERNAL_APIS = {
    "cloudconvert": {
        "enabled": (os.getenv("CLOUDCONVERT_ENABLED", "false").lower() == "true"),
        "api_key": os.getenv("CLOUDCONVERT_API_KEY", ""),
        "base_url": "https://api.cloudconvert.com/v2",
    },
    "zamzar": {
        "enabled": os.getenv("ZAMZAR_ENABLED", "false").lower() == "true",
        "api_key": os.getenv("ZAMZAR_API_KEY", ""),
        "base_url": "https://api.zamzar.com/v1",
    },
}

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Performance settings
MAX_CONCURRENT_CONVERSIONS = int(os.getenv("MAX_CONCURRENT_CONVERSIONS", "3"))
CLEANUP_INTERVAL = 300  # 5 minutes
FILE_RETENTION_TIME = 3600  # 1 hour before auto-cleanup

# History settings
MAX_HISTORY_PER_USER = 100
HISTORY_RETENTION_DAYS = 30

# UI Messages
MESSAGES = {
    "welcome": """
🔄 *Welcome to File Converter Bot!*

I can convert files between multiple formats:
📄 Documents: CSV, PDF, DOCX, XML, JSON, YAML, MD, TXT
📚 E-Books: FB2, EPUB, MOBI
🖼️ Images: GIF, SVG, ICO, PNG, JPEG, WEBP, BMP, TIFF
🎬 Video: WEBM, MP4, AVI, MKV, MOV
🎵 Audio: MP3, WAV, OGG, FLAC, AAC
🎮 3D Models: OBJ, FBX, GLB, GLTF, STL
📊 Data: ETS, XLSX, XLS

*Features:*
✅ Multiple file conversion at once
✅ Conversion history recovery
✅ Fast local processing
✅ Works on all Telegram platforms

Send me a file or use /help for more info!
""",
    "help": """
📖 *Help Guide*

*Commands:*
/start - Start the bot
/help - Show this help
/convert - Start conversion mode
/history - View conversion history
/recover - Recover previous files
/settings - Bot settings
/cancel - Cancel current operation

*How to convert:*
1. Send me one or multiple files
2. Select target format
3. Wait for conversion
4. Download converted files

*Tips:*
• You can send multiple files at once
• Use /history to find previous conversions
• Files are processed locally for speed
""",
    "select_format": "📁 Select target format for conversion:",
    "converting": "⏳ Converting your file(s)... Please wait.",
    "success": "✅ Conversion complete!",
    "error": "❌ Error during conversion: {error}",
    "no_files": "📎 Please send me file(s) to convert.",
    "unsupported": "❌ Unsupported file format: {format}",
    "file_too_large": "❌ File is too large. Maximum size: {max_size}MB",
    "cancelled": "🚫 Operation cancelled.",
}
