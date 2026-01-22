"""
Converter Bot - Main Entry Point
A powerful Telegram bot for converting files between multiple formats
"""

import asyncio
import logging
import sys

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.config import (
    BOT_TOKEN,
    CLEANUP_INTERVAL,
    DATA_DIR,
    FILE_RETENTION_TIME,
    LOG_FORMAT,
    LOG_LEVEL,
    TEMP_DIR,
)
from src.converters import ConverterFactory
from src.handlers.callback_handlers import CallbackHandlers
from src.handlers.command_handlers import CommandHandlers
from src.handlers.file_handlers import FileHandlers
from src.utils.file_manager import FileManager
from src.utils.history import HistoryManager

# Configure logging
log_handlers = [logging.StreamHandler(sys.stdout)]

# Add file handler only if DATA_DIR exists and is writable
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_handlers.append(logging.FileHandler(DATA_DIR / "bot.log", encoding="utf-8"))
except (OSError, PermissionError):
    pass  # Skip file logging on Render if permissions don't allow

logging.basicConfig(
    format=LOG_FORMAT,
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)


class ConverterBot:
    """Main bot application class"""

    def __init__(self):
        self.application = None
        self.history_manager = None
        self.file_manager = None
        self.converter_factory = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize all bot components"""
        logger.info("Initializing Converter Bot...")

        # Initialize managers
        self.history_manager = HistoryManager(
            data_dir=DATA_DIR, max_entries_per_user=100, retention_days=30
        )

        self.file_manager = FileManager(
            temp_dir=TEMP_DIR,
            cleanup_interval=CLEANUP_INTERVAL,
            file_retention=FILE_RETENTION_TIME,
        )

        self.converter_factory = ConverterFactory(TEMP_DIR)

        # Initialize handlers
        command_handlers = CommandHandlers(self.history_manager)
        callback_handlers = CallbackHandlers(self.history_manager, command_handlers)
        file_handlers = FileHandlers(
            self.converter_factory, self.history_manager, self.file_manager
        )

        # Build application
        builder = Application.builder()
        builder.token(BOT_TOKEN).concurrent_updates(True)
        self.application = builder.build()

        # Register command handlers
        self.application.add_handler(CommandHandler("start", command_handlers.start))
        self.application.add_handler(CommandHandler("help", command_handlers.help))
        self.application.add_handler(
            CommandHandler("convert", command_handlers.convert)
        )
        self.application.add_handler(
            CommandHandler("history", command_handlers.history)
        )
        self.application.add_handler(
            CommandHandler("recover", command_handlers.recover)
        )
        self.application.add_handler(
            CommandHandler("settings", command_handlers.settings)
        )
        self.application.add_handler(
            CommandHandler("formats", command_handlers.formats)
        )
        self.application.add_handler(CommandHandler("cancel", command_handlers.cancel))
        self.application.add_handler(CommandHandler("stats", command_handlers.stats))

        # Register persistent menu text handler (must be before callback handler)
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, command_handlers.handle_menu_text
            )
        )

        # Register callback handler
        self.application.add_handler(
            CallbackQueryHandler(callback_handlers.handle_callback)
        )

        # Register file handlers
        self.application.add_handler(
            MessageHandler(filters.Document.ALL, file_handlers.handle_document)
        )
        self.application.add_handler(
            MessageHandler(filters.PHOTO, file_handlers.handle_photo)
        )
        self.application.add_handler(
            MessageHandler(filters.VIDEO, file_handlers.handle_video)
        )
        self.application.add_handler(
            MessageHandler(filters.AUDIO | filters.VOICE, file_handlers.handle_audio)
        )

        # Store handlers reference for format processing
        self.application.bot_data["file_handlers"] = file_handlers

        # Add error handler
        self.application.add_error_handler(self.error_handler)

        logger.info("Bot initialization complete")

    async def start(self):
        """Start the bot"""
        await self.initialize()

        # Start file manager cleanup task
        await self.file_manager.start()

        # Start periodic history cleanup
        asyncio.create_task(self._history_cleanup_task())

        logger.info("Starting bot polling...")

        # Initialize and start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES, drop_pending_updates=True
        )

        logger.info("Bot is running! Press Ctrl+C to stop.")

        # Run forever until cancelled
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass

    async def stop(self):
        """Stop the bot gracefully"""
        logger.info("Shutting down bot...")

        # Stop file manager
        await self.file_manager.stop()

        # Save history
        await self.history_manager.save_history()

        # Stop application
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

        logger.info("Bot shutdown complete")

    async def _history_cleanup_task(self):
        """Periodic task to clean old history entries"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(3600)  # Run every hour
                removed = await self.history_manager.cleanup_old_entries()
                if removed > 0:
                    logger.info(f"Cleaned {removed} old history entries")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"History cleanup error: {e}")

    async def error_handler(self, update: object, context):
        """Handle errors"""
        logger.error(f"Exception: {context.error}", exc_info=context.error)

        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again or use /help."
                )
            except Exception:
                pass

    def signal_handler(self):
        """Handle shutdown signals"""
        self._shutdown_event.set()


async def main():
    """Main entry point"""
    bot = ConverterBot()

    try:
        await bot.start()
    except asyncio.CancelledError:
        pass
    finally:
        await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
