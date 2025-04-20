"""
Base module class for TGAI-Bennet modules.
All modules must inherit from this class and implement the required methods.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List, Union
import asyncio
import time
from datetime import datetime
import json

from src.utils.logger import get_logger
from src.core.llm_client import LLMClient
from src.exceptions import ModuleConfigurationError, ModuleExecutionError


class ModuleTrigger(Enum):
    """Types of triggers that can activate a module."""
    TIME = "time"    # Triggered at regular intervals
    EVENT = "event"  # Triggered by external events


class TriggerConfig:
    """Configuration for module triggers."""
    
    def __init__(self, trigger_type: ModuleTrigger, **kwargs):
        self.type = trigger_type
        self.interval = kwargs.get('interval', 300)  # Default 5 minutes for time triggers
        self.event_type = kwargs.get('event_type', 'webhook')  # Default to webhook for event triggers
        self.event_config = kwargs.get('event_config', {})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trigger config to dictionary."""
        return {
            'type': self.type.value,
            'interval': self.interval,
            'event_type': self.event_type,
            'event_config': self.event_config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TriggerConfig':
        """Create trigger config from dictionary."""
        return cls(
            trigger_type=ModuleTrigger(data['type']),
            interval=data.get('interval', 300),
            event_type=data.get('event_type', 'webhook'),
            event_config=data.get('event_config', {})
        )


class BaseModule(ABC):
    """
    Abstract base class for all TGAI-Bennet modules.
    
    Each module must implement the abstract methods and can override the optional ones.
    """
    
    def __init__(self, bot_instance, config):
        """
        Initialize the base module.
        
        Args:
            bot_instance: Reference to the main bot instance for sending messages
            config: Reference to the configuration loader
        """
        self.bot = bot_instance
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        self.name = self.__class__.__name__
        self._load_time = time.time()
        
        # Module metadata
        self.description = ""
        self.author = ""
        self.version = "1.0.0"
        
        # Default trigger configuration
        self.trigger = TriggerConfig(ModuleTrigger.TIME, interval=300)
        
        # LLM client instance (created on demand)
        self._llm_client: Optional[LLMClient] = None
        
        # Module state
        self.state: Dict[str, Any] = {}
        
        # Configuration loaded from module-specific settings
        self.module_config: Dict[str, Any] = {}
    
    @property
    def llm_client(self) -> LLMClient:
        """Get LLM client instance, creating it if needed."""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the module.
        
        This method is called when the module is loaded. It should set up any necessary
        resources, load configuration, and prepare the module for execution.
        """
        pass
    
    @abstractmethod
    async def run(self) -> None:
        """
        Main execution method for the module.
        
        This method is called periodically for time-based modules or when triggered
        for event-based modules. It should contain the core logic of the module.
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """
        Clean up resources used by the module.
        
        This method is called when the module is being unloaded. It should release
        any resources, close connections, and perform any necessary cleanup.
        """
        pass
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value specific to this module.
        
        The configuration is loaded from the 'modules.{module_name}' section of the main config.
        
        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key is not found
        
        Returns:
            Configuration value or default
        """
        module_config_path = f"modules.{self.name}.{key}"
        return self.config.get(module_config_path, default)
    
    async def send_telegram_message(
        self, 
        text: str, 
        chat_id: Optional[int] = None,
        parse_mode: Optional[str] = None
    ) -> bool:
        """
        Send a message via Telegram.
        
        Args:
            text: Message text
            chat_id: Target chat ID (defaults to admin chat)
            parse_mode: Message parse mode (defaults to config setting)
        
        Returns:
            bool: Whether the message was sent successfully
        """
        try:
            return await self.bot.send_message(text, chat_id=chat_id, parse_mode=parse_mode)
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {str(e)}")
            return False
    
    async def generate_llm_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        chat_id: Optional[int] = None,
        use_history: bool = False,
        **kwargs
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User prompt
            system_message: System message to set context
            model: Model to use (defaults to config setting)
            temperature: Temperature for response generation
            max_tokens: Maximum tokens in response
            chat_id: Optional chat ID for maintaining conversation history
            use_history: Whether to use conversation history (requires chat_id)
            **kwargs: Additional provider-specific parameters
        
        Returns:
            str: LLM response content
        """
        try:
            # Use context-aware completion if history is requested and chat_id is provided
            if use_history and chat_id is not None:
                response = await self.llm_client.get_context_aware_completion(
                    chat_id=chat_id,
                    user_message=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    module_name=self.__class__.__name__,
                    **kwargs
                )
                return response.content
            else:
                # Standard completion without history
                messages = []
                
                if system_message:
                    messages.append({"role": "system", "content": system_message})
                
                messages.append({"role": "user", "content": prompt})
                
                response = await self.llm_client.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                # If chat_id is provided, store the exchange in history even if not using history for generation
                if chat_id is not None:
                    try:
                        # Get chat history manager
                        history_manager = await self.llm_client.get_chat_history_manager()
                        
                        # Add the exchange to history
                        await history_manager.add_message(
                            chat_id=chat_id,
                            role="user",
                            content=prompt,
                            model=model,
                            metadata={"module": self.__class__.__name__}
                        )
                        
                        await history_manager.add_message(
                            chat_id=chat_id,
                            role="assistant",
                            content=response.content,
                            model=model,
                            metadata={"module": self.__class__.__name__}
                        )
                    except Exception as history_error:
                        self.logger.warning(f"Failed to store exchange in history: {str(history_error)}")
                
                return response.content
        except Exception as e:
            self.logger.error(f"LLM generation failed: {str(e)}")
            raise ModuleExecutionError(f"LLM generation failed: {str(e)}", e)
    
    def log_info(self, message: str):
        """Log an info message."""
        self.logger.info(message)
    
    def log_error(self, message: str, exception: Optional[Exception] = None):
        """Log an error message."""
        self.logger.error(message)
        if exception:
            self.logger.exception(str(exception))
    
    def log_warning(self, message: str):
        """Log a warning message."""
        self.logger.warning(message)
    
    def log_debug(self, message: str):
        """Log a debug message."""
        self.logger.debug(message)
    
    async def save_state(self) -> Dict[str, Any]:
        """
        Save the current state of the module.
        
        This method is called when the module is being unloaded or before the
        service stops. It should return any state that needs to be persisted.
        
        Returns:
            dict: Module state to be saved
        """
        return self.state
    
    async def load_state(self, state: Dict[str, Any]) -> None:
        """
        Load a previously saved state.
        
        This method is called when the module is initialized if there's a saved state.
        
        Args:
            state: Previously saved module state
        """
        self.state = state
    
    def validate_config(self) -> bool:
        """
        Validate module configuration.
        
        This method is called after the module is loaded to ensure it has
        a valid configuration. Override this method to add custom validation.
        
        Returns:
            bool: Whether the configuration is valid
        """
        return True
    
    def get_trigger_config(self) -> TriggerConfig:
        """
        Get the trigger configuration for this module.
        
        Override this method to provide custom trigger configuration.
        
        Returns:
            TriggerConfig: Module trigger configuration
        """
        return self.trigger
    
    def set_trigger_interval(self, interval: int):
        """
        Set the interval for time-based triggers.
        
        Args:
            interval: Interval in seconds
        """
        if self.trigger.type == ModuleTrigger.TIME:
            self.trigger.interval = interval
    
    def get_module_info(self) -> Dict[str, Any]:
        """
        Get module information and metadata.
        
        Returns:
            dict: Module information
        """
        return {
            'name': self.name,
            'description': self.description,
            'author': self.author,
            'version': self.version,
            'trigger': self.trigger.to_dict(),
            'load_time': datetime.fromtimestamp(self._load_time).isoformat()
        }
    
    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Handle incoming events for event-based modules.
        
        Override this method to handle specific event types.
        
        Args:
            event_type: Type of event
            event_data: Event data
        """
        self.logger.warning(f"Unhandled event: {event_type}")
    
    def format_telegram_response(
        self,
        title: str,
        content: Union[str, List[str]],
        status: str = 'info',
        code_block: Optional[str] = None
    ) -> str:
        """
        Format a response for Telegram with consistent styling.
        
        Args:
            title: Message title
            content: Message content (string or list of strings)
            status: Status type for icon ('info', 'success', 'warning', 'error')
            code_block: Optional code block to include
        
        Returns:
            str: Formatted message for Telegram
        """
        from src.utils.telegram_formatter import TelegramFormatter
        
        message = TelegramFormatter.status_message(title, content, status)
        
        if code_block:
            message += "\n\n" + TelegramFormatter.code_block(code_block)
        
        return message
    
    def schedule_event(self, delay: float, event_type: str, event_data: Dict[str, Any] = None):
        """
        Schedule an event to be handled after a delay.
        
        Args:
            delay: Delay in seconds
            event_type: Type of event
            event_data: Event data
        """
        async def delayed_event():
            await asyncio.sleep(delay)
            await self.handle_event(event_type, event_data or {})
        
        asyncio.create_task(delayed_event())
