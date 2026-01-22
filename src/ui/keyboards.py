"""
Inline Keyboard UI components for the Telegram bot
"""

from typing import Dict, List

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.config import CONVERSION_MATRIX, FORMAT_CATEGORIES


def create_persistent_menu() -> ReplyKeyboardMarkup:
    """Create persistent bottom menu that's always visible"""
    keyboard = [
        [
            KeyboardButton("📁 Convert"),
            KeyboardButton("📜 History"),
            KeyboardButton("❓ Help"),
        ],
        [
            KeyboardButton("⚙️ Settings"),
            KeyboardButton("📋 Formats"),
            KeyboardButton("❌ Cancel"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )


def create_main_menu() -> InlineKeyboardMarkup:
    """Create main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("📁 Convert Files", callback_data="menu_convert"),
            InlineKeyboardButton("📜 History", callback_data="menu_history"),
        ],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
            InlineKeyboardButton("❓ Help", callback_data="menu_help"),
        ],
        [InlineKeyboardButton("ℹ️ Supported Formats", callback_data="menu_formats")],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_format_categories_menu() -> InlineKeyboardMarkup:
    """Create format categories selection menu"""
    keyboard = []
    row = []

    for cat_id, category in FORMAT_CATEGORIES.items():
        btn = InlineKeyboardButton(
            f"{category.icon} {category.name}", callback_data=f"cat_{cat_id}"
        )
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_main")])

    return InlineKeyboardMarkup(keyboard)


def create_format_selection_menu(
    input_format: str, page: int = 0
) -> InlineKeyboardMarkup:
    """Create target format selection menu based on input format"""
    input_format = input_format.lower().lstrip(".")

    available_formats = CONVERSION_MATRIX.get(input_format, [])

    if not available_formats:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "❌ No conversions available", callback_data="no_formats"
                    )
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
            ]
        )

    # Paginate formats (8 per page)
    formats_per_page = 8
    start_idx = page * formats_per_page
    end_idx = start_idx + formats_per_page
    page_formats = available_formats[start_idx:end_idx]
    total_pages = (len(available_formats) + formats_per_page - 1) // formats_per_page

    keyboard = []
    row = []

    for fmt in page_formats:
        btn = InlineKeyboardButton(f"📄 {fmt.upper()}", callback_data=f"fmt_{fmt}")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # Navigation row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page_{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"page_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append(
        [
            InlineKeyboardButton("🔙 Back", callback_data="menu_main"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def create_multi_file_menu(file_count: int) -> InlineKeyboardMarkup:
    """Create menu for multiple files conversion"""
    keyboard = [
        [
            InlineKeyboardButton(
                f"✅ Convert All ({file_count} files)", callback_data="convert_all"
            )
        ],
        [
            InlineKeyboardButton("➕ Add More Files", callback_data="add_more"),
            InlineKeyboardButton("🗑️ Clear All", callback_data="clear_files"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_history_menu(
    history_items: List[Dict], page: int = 0
) -> InlineKeyboardMarkup:
    """Create history browsing menu"""
    items_per_page = 5
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_items = history_items[start_idx:end_idx]
    total_pages = (len(history_items) + items_per_page - 1) // items_per_page

    keyboard = []

    for item in page_items:
        conv_id = item.get("id", "")[:8]
        filename = item.get("filename", "Unknown")[:20]
        target_fmt = item.get("target_format", "?").upper()

        btn_text = f"📄 {filename} → {target_fmt}"
        keyboard.append(
            [InlineKeyboardButton(btn_text, callback_data=f"hist_{conv_id}")]
        )

    # Navigation
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"histpage_{page - 1}")
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton("➡️ Next", callback_data=f"histpage_{page + 1}")
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append(
        [
            InlineKeyboardButton("🗑️ Clear History", callback_data="clear_history"),
            InlineKeyboardButton("🔙 Back", callback_data="menu_main"),
        ]
    )

    return InlineKeyboardMarkup(keyboard)


def create_history_item_menu(conv_id: str) -> InlineKeyboardMarkup:
    """Create menu for a specific history item"""
    keyboard = [
        [
            InlineKeyboardButton(
                "🔄 Re-download", callback_data=f"redownload_{conv_id}"
            ),
            InlineKeyboardButton(
                "🔁 Convert Again", callback_data=f"reconvert_{conv_id}"
            ),
        ],
        [
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_hist_{conv_id}"),
            InlineKeyboardButton("🔙 Back", callback_data="menu_history"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_settings_menu(settings: Dict) -> InlineKeyboardMarkup:
    """Create settings menu"""
    auto_cleanup = "✅" if settings.get("auto_cleanup", True) else "❌"
    notifications = "✅" if settings.get("notifications", True) else "❌"
    quality = settings.get("quality", "high").capitalize()

    keyboard = [
        [
            InlineKeyboardButton(
                f"🧹 Auto Cleanup: {auto_cleanup}", callback_data="toggle_cleanup"
            )
        ],
        [
            InlineKeyboardButton(
                f"🔔 Notifications: {notifications}",
                callback_data="toggle_notifications",
            )
        ],
        [InlineKeyboardButton(f"📊 Quality: {quality}", callback_data="cycle_quality")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_confirmation_menu(action: str) -> InlineKeyboardMarkup:
    """Create confirmation dialog"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"confirm_{action}"),
            InlineKeyboardButton("❌ No", callback_data="cancel"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_conversion_progress_menu(conv_id: str) -> InlineKeyboardMarkup:
    """Create progress tracking menu"""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_{conv_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_conv_{conv_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_result_menu(conv_id: str, input_format: str = None) -> InlineKeyboardMarkup:
    """Create post-conversion result menu"""
    keyboard = []

    # Add "Convert to Another Format" button if we know the input format
    if input_format:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔀 Convert to Another Format",
                    callback_data=f"reselect_fmt_{conv_id}",
                )
            ]
        )

    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    "🔄 Convert Another File", callback_data="menu_convert"
                )
            ],
            [
                InlineKeyboardButton("📜 View History", callback_data="menu_history"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
            ],
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def create_error_menu() -> InlineKeyboardMarkup:
    """Create error handling menu"""
    keyboard = [
        [
            InlineKeyboardButton("🔄 Try Again", callback_data="menu_convert"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main"),
        ],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_format_info_menu() -> InlineKeyboardMarkup:
    """Create format information display menu"""
    keyboard = []

    for cat_id, category in FORMAT_CATEGORIES.items():
        formats_str = ", ".join(sorted(category.formats)[:5])
        if len(category.formats) > 5:
            formats_str += f" (+{len(category.formats) - 5})"

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{category.icon} {category.name}: {formats_str}",
                    callback_data=f"info_{cat_id}",
                )
            ]
        )

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_main")])

    return InlineKeyboardMarkup(keyboard)
