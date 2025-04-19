"""
Telegram bot core module for TGAI-Bennet.
Handles Telegram interactions, message processing, and command handling.
"""

import asyncio
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

from telegram import Update, Bot, constants
from telegram.ext import (
    Application,
    CommandHandler, 
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.error import TelegramError

from src.exceptions import TelegramBotError, ConfigurationError
from src.config.loader import get_config, reload_config
from src.core.llm_client import LLMClient
from src.utils.logger import get_logger
from src.utils.telegram_formatter import TelegramFormatter


logger = get_logger("telegram_bot")


class TGAIBennet:
    """
    Main Telegram bot class for TGAI-Bennet.
    Manages bot lifecycle, message handling, and integration with other components.
    """
    
    def __init__(self):
        """Initialize the Telegram bot."""
        self.config = get_config()
        
        # Get bot token and admin chat ID from environment
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.admin_chat_id = int(os.getenv('TELEGRAM_ADMIN_CHAT_ID', '0'))
        
        if not self.bot_token:
            raise ConfigurationError("TELEGRAM_BOT_TOKEN not found in environment")
        
        if not self.admin_chat_id:
            raise ConfigurationError("TELEGRAM_ADMIN_CHAT_ID not found in environment")
        
        # Initialize components
        self.llm_client = LLMClient()
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        
        # Module manager will be set by main.py
        self.module_manager = None
        
        # Health monitor will be set by main.py
        self.health_monitor = None
        
        logger.info(f"TGAI-Bennet bot initialized for admin chat ID: {self.admin_chat_id}")
    
    async def setup(self):
        """Set up the bot application and handlers."""
        try:
            # Create application
            self.application = (
                Application.builder()
                .token(self.bot_token)
                .build()
            )
            
            # Get bot instance
            self.bot = self.application.bot
            
            # Register handlers
            self._register_handlers()
            
            # Initialize the application
            await self.application.initialize()
            
            logger.info("Bot setup completed successfully")
            
        except Exception as e:
            logger.error(f"Bot setup failed: {str(e)}")
            raise TelegramBotError(f"Bot setup failed: {str(e)}", e)
    
    def _register_handlers(self):
        """Register command and message handlers."""
        # Admin commands
        admin_commands = {
            'reload_modules': self._cmd_reload_modules,
            'reload_config': self._cmd_reload_config,
            'status': self._cmd_status,
            'stop': self._cmd_stop,
            'health': self._cmd_health,
        }
        
        # Get command names from config
        commands_config = self.config.get('telegram.commands', {})
        
        for cmd_key, handler in admin_commands.items():
            cmd = commands_config.get(cmd_key, f'/{cmd_key}')
            # Strip the leading '/' as CommandHandler doesn't need it
            cmd_name = cmd.lstrip('/')
            
            # Only admin can use these commands
            self.application.add_handler(
                CommandHandler(
                    cmd_name,
                    handler,
                    filters=filters.User(self.admin_chat_id)
                )
            )
        
        # Start command available to everyone
        self.application.add_handler(
            CommandHandler('start', self._cmd_start)
        )
        
        # Help command available to everyone
        self.application.add_handler(
            CommandHandler('help', self._cmd_help)
        )
        
        # Handler for regular messages (chat)
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_message
            )
        )
        
        # Error handler
        self.application.add_error_handler(self._error_handler)
    
    async def _is_admin(self, update: Update) -> bool:
        """Check if the user is an admin."""
        return update.effective_user.id == self.admin_chat_id
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        welcome_message = (
            "🤖 Welcome to TGAI-Bennet!\n\n"
            f"I am your AI assistant powered by {self.llm_client.provider}.\n"
            "Send me any message and I'll respond using AI.\n\n"
            "Use /help to see available commands."
        )
        
        if await self._is_admin(update):
            welcome_message += "\n\n👑 Admin commands are available to you."
        
        await update.message.reply_text(welcome_message)
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        commands_config = self.config.get('telegram.commands', {})
        
        help_text = "📚 Available Commands:\n\n"
        help_text += "/start - Start the bot\n"
        help_text += "/help - Show this help message\n"
        
        if await self._is_admin(update):
            help_text += "\n👑 Admin Commands:\n"
            help_text += f"{commands_config.get('reload_modules', '/reload_modules')} - Reload modules\n"
            help_text += f"{commands_config.get('reload_config', '/reload_config')} - Reload configuration\n"
            help_text += f"{commands_config.get('status', '/status')} - Show bot status\n"
            help_text += f"{commands_config.get('health', '/health')} - Show health check\n"
            help_text += f"{commands_config.get('stop', '/stop')} - Stop the bot\n"
        
        await update.message.reply_text(help_text)
    
    async def _cmd_reload_modules(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reload_modules command."""
        if not self.module_manager:
            await update.message.reply_text("⚠️ Module manager not initialized.")
            return
        
        try:
            result = await self.module_manager.reload_modules()
            
            message = TelegramFormatter.status_message(
                "Modules Reloaded",
                f"Successfully reloaded {result['loaded']} modules.\n"
                f"Unloaded {result['unloaded']} modules.\n"
                f"Errors: {result['errors']}",
                status='success' if result['errors'] == 0 else 'warning'
            )
            
            await update.message.reply_text(
                message,
                parse_mode=self.config.get('telegram.parse_mode', 'Markdown')
            )
            
        except Exception as e:
            logger.error(f"Error reloading modules: {str(e)}")
            await update.message.reply_text(f"❌ Error reloading modules: {str(e)}")
    
    async def _cmd_reload_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /reload_config command."""
        try:
            reload_config()
            self.config = get_config()
            
            # Reinitialize LLM client with new config
            self.llm_client = LLMClient()
            
            message = TelegramFormatter.status_message(
                "Configuration Reloaded",
                "Successfully reloaded configuration file.",
                status='success'
            )
            
            await update.message.reply_text(
                message,
                parse_mode=self.config.get('telegram.parse_mode', 'Markdown')
            )
            
        except Exception as e:
            logger.error(f"Error reloading config: {str(e)}")
            await update.message.reply_text(f"❌ Error reloading config: {str(e)}")
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        status_info = {
            'Provider': self.llm_client.provider,
            'Model': self.config.get('llm.default_model'),
            'Modules': 'Module manager not initialized' if not self.module_manager else f"{len(self.module_manager.modules)} loaded",
            'Health Monitor': 'Not initialized' if not self.health_monitor else 'Running',
            'Uptime': str(datetime.now() - self.application.start_time if hasattr(self.application, 'start_time') else 'N/A'),
        }
        
        if self.llm_client:
            metrics = self.llm_client.get_metrics()
            status_info.update({
                'LLM Requests': metrics.get('requests_count', 0),
                'Rate Limit Window': f"{metrics.get('rate_limit_window', 0)}s",
                'Rate Limit Requests': metrics.get('rate_limit_requests', 0),
            })
        
        message = TelegramFormatter.status_message(
            "TGAI-Bennet Status",
            TelegramFormatter.format_key_value_pairs(status_info),
            status='info'
        )
        
        await update.message.reply_text(
            message,
            parse_mode=self.config.get('telegram.parse_mode', 'Markdown')
        )
    
    async def _cmd_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /health command."""
        if not self.health_monitor:
            await update.message.reply_text("⚠️ Health monitor not initialized.")
            return
        
        try:
            health_data = await self.health_monitor.get_health_status()
            
            message = TelegramFormatter.health_check_message(health_data)
            
            await update.message.reply_text(
                message,
                parse_mode=self.config.get('telegram.parse_mode', 'Markdown')
            )
            
        except Exception as e:
            logger.error(f"Error getting health status: {str(e)}")
            await update.message.reply_text(f"❌ Error getting health status: {str(e)}")
    
    async def _cmd_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command."""
        message = TelegramFormatter.status_message(
            "Bot Stopping",
            "Gracefully shutting down TGAI-Bennet...",
            status='warning'
        )
        
        await update.message.reply_text(
            message,
            parse_mode=self.config.get('telegram.parse_mode', 'Markdown')
        )
        
        # Signal the application to stop
        logger.info("Stop command received. Initiating shutdown...")
        
        # Create a task to stop the bot after sending the message
        async def stop_bot():
            await asyncio.sleep(1)  # Give time for the message to be sent
            await self.stop()
        
        asyncio.create_task(stop_bot())
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular chat messages."""
        # For now, only respond to admin
        if not await self._is_admin(update):
            await update.message.reply_text("Sorry, this bot is currently available to admin only.")
            return
        
        user_message = update.message.text
        
        try:
            # Show typing indicator
            await update.message.chat.send_action(constants.ChatAction.TYPING)
            
            # Create messages for LLM
            messages = [
                {"role": "system", "content": "You are Bennet, a helpful AI assistant in a Telegram chat."},
                {"role": "user", "content": user_message}
            ]
            
            # Get LLM response
            response = await self.llm_client.chat_completion(messages)
            
            # Format and send response
            formatted_response = response.content
            
            # Split long messages if needed
            max_length = self.config.get('telegram.max_message_length', 4096)
            if len(formatted_response) > max_length:
                parts = TelegramFormatter.split_long_message(formatted_response)
                for part in parts:
                    await update.message.reply_text(
                        part,
                        parse_mode=self.config.get('telegram.parse_mode', 'Markdown')
                    )
            else:
                await update.message.reply_text(
                    formatted_response,
                    parse_mode=self.config.get('telegram.parse_mode', 'Markdown')
                )
        
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            error_message = TelegramFormatter.error_message(
                "Message Handling Error",
                e,
                details={'message': user_message[:50] + '...' if len(user_message) > 50 else user_message}
            )
            
            await update.message.reply_text(
                error_message,
                parse_mode=self.config.get('telegram.parse_mode', 'Markdown')
            )
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in the bot."""
        error = context.error
        logger.error(f"Update {update} caused error {error}")
        
        # Send error notification to admin
        if self.admin_chat_id:
            error_message = TelegramFormatter.error_message(
                "Bot Error",
                error,
                details={'update': str(update)}
            )
            
            try:
                await self.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=error_message,
                    parse_mode=self.config.get('telegram.parse_mode', 'Markdown')
                )
            except Exception as e:
                logger.error(f"Failed to send error notification: {str(e)}")
    
    async def send_message(
        self,
        text: str,
        chat_id: Optional[int] = None,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: Optional[bool] = None,
        disable_notification: Optional[bool] = None
    ) -> bool:
        """
        Send a message to a chat.
        
        Args:
            text: Message text
            chat_id: Target chat ID (defaults to admin chat)
            parse_mode: Message parse mode
            disable_web_page_preview: Whether to disable link previews
            disable_notification: Whether to send the message silently
            
        Returns:
            bool: Whether the message was sent successfully
        """
        chat_id = chat_id or self.admin_chat_id
        parse_mode = parse_mode or self.config.get('telegram.parse_mode', 'Markdown')
        disable_web_page_preview = disable_web_page_preview or self.config.get('telegram.disable_web_page_preview', True)
        disable_notification = disable_notification or self.config.get('telegram.disable_notification', False)
        
        try:
            # Handle long messages
            max_length = self.config.get('telegram.max_message_length', 4096)
            if len(text) > max_length:
                parts = TelegramFormatter.split_long_message(text)
                for part in parts:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=part,
                        parse_mode=parse_mode,
                        disable_web_page_preview=disable_web_page_preview,
                        disable_notification=disable_notification
                    )
            else:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview,
                    disable_notification=disable_notification
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            return False
    
    async def start(self):
        """Start the bot."""
        try:
            if not self.application:
                await self.setup()
            
            # Start polling
            await self.application.start()
            self.application.start_time = datetime.now()
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            # Send startup message to admin
            await self.send_message(
                TelegramFormatter.status_message(
                    "Bot Started",
                    f"TGAI-Bennet has started successfully!\nProvider: {self.llm_client.provider}",
                    status='success'
                )
            )
            
            logger.info("Bot started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start bot: {str(e)}")
            raise TelegramBotError(f"Failed to start bot: {str(e)}", e)
    
    async def stop(self):
        """Stop the bot gracefully."""
        try:
            if self.application:
                # Send shutdown message to admin
                try:
                    await self.send_message(
                        TelegramFormatter.status_message(
                            "Bot Stopped",
                            "TGAI-Bennet has been stopped.",
                            status='info'
                        )
                    )
                except Exception:
                    # Ignore errors when sending shutdown message
                    pass
                
                # Stop polling and shutdown
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                
                logger.info("Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping bot: {str(e)}")
            raise TelegramBotError(f"Error stopping bot: {str(e)}", e)
    
    def set_module_manager(self, module_manager):
        """Set the module manager instance."""
        self.module_manager = module_manager
    
    def set_health_monitor(self, health_monitor):
        """Set the health monitor instance."""
        self.health_monitor = health_monitor
