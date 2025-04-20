"""
Custom exceptions for TGAI-Bennet application.
"""


class BennetBaseException(Exception):
    """Base exception for all TGAI-Bennet exceptions."""
    
    def __init__(self, message: str, original_exception: Exception = None):
        super().__init__(message)
        self.original_exception = original_exception


class ConfigurationError(BennetBaseException):
    """Raised when there's an error in the configuration."""
    pass


class LLMProviderError(BennetBaseException):
    """Raised when there's an error with the LLM provider."""
    pass


class ModuleError(BennetBaseException):
    """Base exception for module-related errors."""
    pass


class ModuleLoadError(ModuleError):
    """Raised when a module fails to load properly."""
    pass


class ModuleExecutionError(ModuleError):
    """Raised when a module fails during execution."""
    pass


class ModuleNotFoundError(ModuleError):
    """Raised when a module cannot be found."""
    pass


class ModuleConfigurationError(ModuleError):
    """Raised when a module has invalid configuration."""
    pass


class TelegramBotError(BennetBaseException):
    """Raised when there's an error with the Telegram bot."""
    pass


class ServiceError(BennetBaseException):
    """Raised when there's a service-level error."""
    pass


class RateLimitError(BennetBaseException):
    """Raised when API rate limits are exceeded."""
    pass


class HealthCheckError(BennetBaseException):
    """Raised when health checks fail."""
    pass


class DatabaseError(BennetBaseException):
    """Raised when there's an error with database operations."""
    pass


class StateError(BennetBaseException):
    """Raised when there's an error with state management."""
    pass
