"""
Callback Handlers - handle inline keyboard callbacks
"""

import logging

from telegram import CallbackQuery, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config import CONVERSION_MATRIX, FORMAT_CATEGORIES
from src.ui.keyboards import (
    create_confirmation_menu,
    create_error_menu,
    create_format_categories_menu,
    create_format_info_menu,
    create_format_selection_menu,
    create_history_item_menu,
    create_history_menu,
    create_main_menu,
    create_settings_menu,
)
from src.ui.messages import (
    format_format_info,
    format_help_message,
    format_history_empty,
    format_history_item,
    format_settings,
    format_welcome_message,
)
from src.utils.history import HistoryManager

logger = logging.getLogger(__name__)


class CallbackHandlers:
    """Handles all inline keyboard callbacks"""

    def __init__(self, history_manager: HistoryManager, command_handlers):
        self.history = history_manager
        self.commands = command_handlers

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main callback router"""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = update.effective_user.id

        # Route to appropriate handler
        try:
            if data.startswith("menu_"):
                await self._handle_menu(query, context, data)
            elif data.startswith("cat_"):
                await self._handle_category(query, context, data)
            elif data.startswith("fmt_"):
                await self._handle_format_selection(query, context, data)
            elif data.startswith("page_"):
                await self._handle_pagination(query, context, data)
            elif data.startswith("hist"):
                await self._handle_history(query, context, data, user_id)
            elif data.startswith("toggle_") or data.startswith("cycle_"):
                await self._handle_settings(query, context, data, user_id)
            elif data.startswith("confirm_"):
                await self._handle_confirmation(query, context, data, user_id)
            elif data.startswith("info_"):
                await self._handle_format_info(query, context, data)
            elif data.startswith("redownload_"):
                await self._handle_redownload(query, context, data, user_id)
            elif data.startswith("reconvert_"):
                await self._handle_reconvert(query, context, data, user_id)
            elif data.startswith("reselect_fmt_"):
                await self._handle_reselect_format(query, context, data, user_id)
            elif data.startswith("delete_hist_"):
                await self._handle_delete_history_item(query, context, data, user_id)
            elif data == "cancel":
                await self._handle_cancel(query, context)
            elif data == "convert_all":
                await self._handle_convert_all(query, context)
            elif data == "add_more":
                await self._handle_add_more(query, context)
            elif data == "clear_files":
                await self._handle_clear_files(query, context)
            else:
                logger.warning(f"Unknown callback: {data}")

        except Exception as e:
            logger.error(f"Callback error: {e}")
            await query.edit_message_text(
                f"❌ An error occurred: {e}", reply_markup=create_error_menu()
            )

    async def _handle_menu(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, data: str
    ):
        """Handle menu navigation"""
        menu_type = data.replace("menu_", "")

        if menu_type == "main":
            await query.edit_message_text(
                format_welcome_message(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_main_menu(),
            )

        elif menu_type == "convert":
            await query.edit_message_text(
                "📁 *Send me a file to convert*\n\n"
                "You can send multiple files at once.\n"
                "Or select a format category below:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_categories_menu(),
            )

        elif menu_type == "history":
            user_id = query.from_user.id
            entries = await self.history.get_user_history(user_id, limit=50)

            if not entries:
                await query.edit_message_text(
                    format_history_empty(),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=create_main_menu(),
                )
                return

            history_data = [
                {
                    "id": e.id,
                    "filename": e.original_name,
                    "target_format": e.target_format,
                }
                for e in entries
            ]

            await query.edit_message_text(
                f"📜 *Conversion History* ({len(entries)} items)",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_history_menu(history_data),
            )

        elif menu_type == "settings":
            user_id = query.from_user.id
            settings = self.commands._get_user_settings(user_id)

            await query.edit_message_text(
                format_settings(settings),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_settings_menu(settings),
            )

        elif menu_type == "help":
            await query.edit_message_text(
                format_help_message(),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=create_main_menu(),
            )

        elif menu_type == "formats":
            await query.edit_message_text(
                "📁 *Supported Format Categories*\n\nTap a category to see details:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_info_menu(),
            )

    async def _handle_category(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, data: str
    ):
        """Handle format category selection"""
        cat_id = data.replace("cat_", "")
        category = FORMAT_CATEGORIES.get(cat_id)

        if category:
            formats_list = ", ".join(sorted(category.formats))
            await query.edit_message_text(
                f"{category.icon} *{category.name}*\n\n"
                f"{category.description}\n\n"
                f"Formats: `{formats_list}`\n\n"
                "Send a file in any of these formats to convert.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_categories_menu(),
            )

    async def _handle_format_selection(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, data: str
    ):
        """Handle target format selection"""
        target_format = data.replace("fmt_", "")
        user_data = context.user_data

        # Store selected format
        user_data["target_format"] = target_format

        # Check if we have pending files
        pending_files = user_data.get("pending_files", [])
        if pending_files:
            # Show processing message
            await query.edit_message_text(
                f"🔄 Converting to *{target_format.upper()}*...\n\n"
                "Please wait, processing your files.",
                parse_mode=ParseMode.MARKDOWN,
            )

            # Get file handlers from bot_data and trigger conversion
            file_handlers = context.application.bot_data.get("file_handlers")
            if file_handlers:
                # Create a fake Update object with the query for conversion
                await file_handlers._process_conversion(
                    query, context, pending_files, target_format
                )
                # Clear pending files after conversion
                user_data["pending_files"] = []
                user_data["ready_to_convert"] = False
        else:
            await query.edit_message_text(
                f"✅ Target format: *{target_format.upper()}*\n\n"
                "Now send me the file(s) to convert.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_main_menu(),
            )

    async def _handle_pagination(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, data: str
    ):
        """Handle pagination"""
        page = int(data.replace("page_", ""))
        user_data = context.user_data
        input_format = user_data.get("input_format", "")

        if input_format:
            await query.edit_message_text(
                f"📁 Select target format for *{input_format.upper()}*:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_selection_menu(input_format, page),
            )

    async def _handle_history(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        data: str,
        user_id: int,
    ):
        """Handle history-related callbacks"""
        if data.startswith("histpage_"):
            page = int(data.replace("histpage_", ""))
            entries = await self.history.get_user_history(user_id, limit=50)
            history_data = [
                {
                    "id": e.id,
                    "filename": e.original_name,
                    "target_format": e.target_format,
                }
                for e in entries
            ]
            await query.edit_message_text(
                f"📜 *Conversion History* ({len(entries)} items)",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_history_menu(history_data, page),
            )

        elif data.startswith("hist_"):
            entry_id = data.replace("hist_", "")
            entry = await self.history.get_entry_by_id(user_id, entry_id)

            if entry:
                await query.edit_message_text(
                    format_history_item(entry.to_dict()),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=create_history_item_menu(entry_id),
                )
            else:
                await query.edit_message_text(
                    "❌ Entry not found", reply_markup=create_main_menu()
                )

        elif data.startswith("redownload_"):
            entry_id = data.replace("redownload_", "")
            entry = await self.history.get_entry_by_id(user_id, entry_id)

            if entry and entry.file_id:
                try:
                    await context.bot.send_document(
                        chat_id=query.message.chat_id,
                        document=entry.file_id,
                        caption=f"📄 `{entry.converted_name}`",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as e:
                    await query.edit_message_text(
                        f"❌ Failed to recover: {e}", reply_markup=create_error_menu()
                    )
            else:
                await query.edit_message_text(
                    "❌ File not available for recovery",
                    reply_markup=create_main_menu(),
                )

        elif data.startswith("delete_hist_"):
            entry_id = data.replace("delete_hist_", "")
            await self.history.delete_entry(user_id, entry_id)
            await query.edit_message_text(
                "✅ Entry deleted", reply_markup=create_main_menu()
            )

        elif data == "clear_history":
            await query.edit_message_text(
                "⚠️ *Clear all history?*\n\nThis cannot be undone.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_confirmation_menu("clear_history"),
            )

    async def _handle_settings(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        data: str,
        user_id: int,
    ):
        """Handle settings toggles"""
        settings = self.commands._get_user_settings(user_id)

        if data == "toggle_cleanup":
            settings["auto_cleanup"] = not settings.get("auto_cleanup", True)
            self.commands.update_user_setting(
                user_id, "auto_cleanup", settings["auto_cleanup"]
            )

        elif data == "toggle_notifications":
            settings["notifications"] = not settings.get("notifications", True)
            self.commands.update_user_setting(
                user_id, "notifications", settings["notifications"]
            )

        elif data == "cycle_quality":
            quality_cycle = ["low", "medium", "high"]
            current = settings.get("quality", "high")
            idx = quality_cycle.index(current) if current in quality_cycle else 2
            new_quality = quality_cycle[(idx + 1) % len(quality_cycle)]
            settings["quality"] = new_quality
            self.commands.update_user_setting(user_id, "quality", new_quality)

        await query.edit_message_text(
            format_settings(settings),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_settings_menu(settings),
        )

    async def _handle_confirmation(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        data: str,
        user_id: int,
    ):
        """Handle confirmation dialogs"""
        action = data.replace("confirm_", "")

        if action == "clear_history":
            count = await self.history.clear_user_history(user_id)
            await query.edit_message_text(
                f"✅ Cleared {count} history entries", reply_markup=create_main_menu()
            )

    async def _handle_format_info(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, data: str
    ):
        """Handle format info display"""
        cat_id = data.replace("info_", "")
        category = FORMAT_CATEGORIES.get(cat_id)

        if category:
            await query.edit_message_text(
                format_format_info(category.name, category.formats),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_info_menu(),
            )

    async def _handle_cancel(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle cancel action"""
        context.user_data.clear()
        await query.edit_message_text(
            "🚫 *Operation Cancelled*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_main_menu(),
        )

    async def _handle_convert_all(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle convert all files"""
        user_data = context.user_data
        pending_files = user_data.get("pending_files", [])
        input_format = user_data.get("input_format", "")

        if pending_files and input_format:
            available = CONVERSION_MATRIX.get(input_format.lower(), [])
            await query.edit_message_text(
                f"📁 Select target format for {len(pending_files)} "
                f"*{input_format.upper()}* file(s):",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_selection_menu(input_format),
            )
        else:
            await query.edit_message_text(
                "❌ No files to convert", reply_markup=create_main_menu()
            )

    async def _handle_add_more(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle add more files"""
        user_data = context.user_data
        count = len(user_data.get("pending_files", []))

        await query.edit_message_text(
            f"📎 *{count} file(s) ready*\n\nSend more files or tap Convert when ready.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_main_menu(),
        )

    async def _handle_clear_files(
        self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle clear pending files"""
        context.user_data["pending_files"] = []
        context.user_data["input_format"] = None

        await query.edit_message_text(
            "🗑️ *Files cleared*\n\nSend new files to convert.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=create_main_menu(),
        )

    async def _handle_redownload(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        data: str,
        user_id: int,
    ):
        """Handle re-download of converted file"""
        entry_id = data.replace("redownload_", "")
        entry = await self.history.get_entry_by_id(user_id, entry_id)

        if entry and entry.file_id:
            try:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=entry.file_id,
                    caption=f"📄 `{entry.converted_name}`",
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as e:
                await query.edit_message_text(
                    f"❌ Failed to recover: {e}",
                    reply_markup=create_error_menu(),
                )
        else:
            await query.edit_message_text(
                "❌ File not available for recovery",
                reply_markup=create_main_menu(),
            )

    async def _handle_reconvert(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        data: str,
        user_id: int,
    ):
        """Handle re-convert request"""
        entry_id = data.replace("reconvert_", "")
        entry = await self.history.get_entry_by_id(user_id, entry_id)

        if entry:
            await query.edit_message_text(
                f"🔄 To reconvert `{entry.original_name}`, "
                "please send the original file again.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_main_menu(),
            )
        else:
            await query.edit_message_text(
                "❌ Entry not found",
                reply_markup=create_main_menu(),
            )

    async def _handle_delete_history_item(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        data: str,
        user_id: int,
    ):
        """Handle delete single history item"""
        entry_id = data.replace("delete_hist_", "")
        await self.history.delete_entry(user_id, entry_id)
        await query.edit_message_text(
            "✅ Entry deleted",
            reply_markup=create_main_menu(),
        )

    async def _handle_reselect_format(
        self,
        query: CallbackQuery,
        context: ContextTypes.DEFAULT_TYPE,
        data: str,
        user_id: int,
    ):
        """Handle 'Convert to Another Format' - show format selection for last file"""
        entry_id = data.replace("reselect_fmt_", "")

        # Get the last conversion info from user_data or history
        last_conv = context.user_data.get("last_conversion")

        if last_conv and last_conv.get("conv_id") == entry_id:
            input_format = last_conv.get("input_format", "")
            filename = last_conv.get("filename", "file")

            # Store as pending file for reconversion
            context.user_data["pending_files"] = [
                {
                    "name": filename,
                    "path": last_conv.get("path"),
                    "format": input_format,
                    "file_id": last_conv.get("file_id"),
                }
            ]
            context.user_data["input_format"] = input_format

            await query.edit_message_text(
                f"🔀 *Select new format for:*\n`{filename}`\n\n"
                f"Current format: *{input_format.upper()}*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=create_format_selection_menu(input_format),
            )
        else:
            # Try to get from history
            entry = await self.history.get_entry_by_id(user_id, entry_id)
            if entry:
                await query.edit_message_text(
                    f"⚠️ Original file no longer available.\n\n"
                    f"Please send `{entry.original_name}` again to convert.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=create_main_menu(),
                )
            else:
                await query.edit_message_text(
                    "❌ Conversion info not found. Please send a new file.",
                    reply_markup=create_main_menu(),
                )
