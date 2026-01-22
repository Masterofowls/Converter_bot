"""
Command Handlers - handle bot commands
"""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.ui.keyboards import (
    create_format_categories_menu,
    create_format_info_menu,
    create_history_menu,
    create_main_menu,
    create_persistent_menu,
    create_settings_menu,
)
from src.ui.messages import (
    format_help_message,
    format_history_empty,
    format_settings,
    format_welcome_message,
)
from src.utils.history import HistoryManager

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Handles all bot commands"""

    def __init__(self, history_manager: HistoryManager):
        self.history_manager = history_manager
        self._user_settings = {}  # In-memory settings cache

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        username = user.first_name if user else None

        # Send persistent menu first
        await update.message.reply_text(
            "⌨️ Menu buttons added!",
            reply_markup=create_persistent_menu(),
        )

        await update.message.reply_text(
            format_welcome_message(username),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_main_menu(),
        )

        logger.info(f"User {user.id} started the bot")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        await update.message.reply_text(
            format_help_message(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_main_menu(),
        )

    async def convert(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /convert command"""
        await update.message.reply_text(
            "📁 *Send me a file to convert*\n\n"
            "You can send multiple files at once.\n"
            "Supported formats:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_format_categories_menu(),
        )

    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command"""
        user_id = update.effective_user.id
        entries = await self.history_manager.get_user_history(user_id, limit=50)

        if not entries:
            await update.message.reply_text(
                format_history_empty(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_main_menu(),
            )
            return

        history_data = [
            {"id": e.id, "filename": e.original_name, "target_format": e.target_format}
            for e in entries
        ]

        await update.message.reply_text(
            f"📜 *Conversion History* ({len(entries)} items)",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_history_menu(history_data),
        )

    async def recover(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /recover <id> command"""
        user_id = update.effective_user.id

        # Parse recovery ID from command
        if not context.args:
            await update.message.reply_text(
                "❓ *Usage:* `/recover <conversion_id>`\n\n"
                "Find your conversion ID in /history",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        entry_id = context.args[0]
        entry = await self.history_manager.get_entry_by_id(user_id, entry_id)

        if not entry:
            await update.message.reply_text(
                f"❌ Conversion `{entry_id}` not found.\nCheck /history for valid IDs.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Check if we have a file_id for recovery
        if entry.file_id:
            try:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=entry.file_id,
                    caption=f"📄 Recovered: `{entry.converted_name}`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                logger.info(f"Recovered file {entry_id} for user {user_id}")
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Failed to recover file: {e}\nThe file may have expired.",
                    parse_mode=ParseMode.MARKDOWN,
                )
        else:
            await update.message.reply_text(
                "❌ This file cannot be recovered.\nFile reference not available.",
                parse_mode=ParseMode.MARKDOWN,
            )

    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        user_id = update.effective_user.id
        user_settings = self._get_user_settings(user_id)

        await update.message.reply_text(
            format_settings(user_settings),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_settings_menu(user_settings),
        )

    async def formats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /formats command"""
        await update.message.reply_text(
            "📁 *Supported Format Categories*\n\n"
            "Tap a category to see all supported formats:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_format_info_menu(),
        )

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command"""
        # Clear user's conversion state
        user_id = update.effective_user.id
        context.user_data.clear()

        await update.message.reply_text(
            "🚫 *Operation Cancelled*\n\nAll pending files cleared.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_main_menu(),
        )

        logger.info(f"User {user_id} cancelled operation")

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        user_id = update.effective_user.id
        stats = await self.history_manager.get_stats(user_id)

        size_str = self._format_size(stats["total_size"])
        rate = stats["success_rate"] * 100

        await update.message.reply_text(
            f"📊 *Your Statistics*\n\n"
            f"Total conversions: {stats['total_conversions']}\n"
            f"Success rate: {rate:.1f}%\n"
            f"Total data processed: {size_str}\n"
            f"Formats used: {len(stats['formats_used'])}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_main_menu(),
        )

    def _get_user_settings(self, user_id: int) -> dict:
        """Get user settings with defaults"""
        defaults = {"auto_cleanup": True, "notifications": True, "quality": "high"}
        return self._user_settings.get(user_id, defaults)

    def update_user_setting(self, user_id: int, key: str, value):
        """Update a user setting"""
        if user_id not in self._user_settings:
            self._user_settings[user_id] = self._get_user_settings(user_id)
        self._user_settings[user_id][key] = value

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes to human readable"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    async def handle_menu_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle persistent menu button presses (text messages)"""
        text = update.message.text

        # Map menu button texts to command handlers
        menu_handlers = {
            "📁 Convert": self.convert,
            "📜 History": self.history,
            "❓ Help": self.help,
            "⚙️ Settings": self.settings,
            "📋 Formats": self.formats,
            "❌ Cancel": self.cancel,
        }

        handler = menu_handlers.get(text)
        if handler:
            await handler(update, context)
        # If text doesn't match menu, ignore (could be file caption, etc.)
