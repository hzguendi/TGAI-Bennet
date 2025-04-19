"""
Configuration validators for TGAI-Bennet.
Provides functions to validate configuration values and sections.
"""

import re
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path

from src.exceptions import ConfigurationError
from src.utils.logger import get_logger


logger = get_logger("config_validators")


class ConfigValidator:
    """Utility class for validating configuration values."""
    
    @staticmethod
    def validate_string(value: Any, min_length: int = 0, max_length: Optional[int] = None, 
                       pattern: Optional[str] = None) -> bool:
        """Validate if a value is a string and meets length/pattern requirements."""
        if not isinstance(value, str):
            return False
        
        if len(value) < min_length:
            return False
        
        if max_length is not None and len(value) > max_length:
            return False
        
        if pattern and not re.match(pattern, value):
            return False
        
        return True
    
    @staticmethod
    def validate_integer(value: Any, min_value: Optional[int] = None, 
                        max_value: Optional[int] = None) -> bool:
        """Validate if a value is an integer within a range."""
        if not isinstance(value, int):
            return False
        
        if min_value is not None and value < min_value:
            return False
        
        if max_value is not None and value > max_value:
            return False
        
        return True
    
    @staticmethod
    def validate_float(value: Any, min_value: Optional[float] = None, 
                      max_value: Optional[float] = None) -> bool:
        """Validate if a value is a float within a range."""
        if not isinstance(value, (int, float)):
            return False
        
        if min_value is not None and value < min_value:
            return False
        
        if max_value is not None and value > max_value:
            return False
        
        return True
    
    @staticmethod
    def validate_boolean(value: Any) -> bool:
        """Validate if a value is a boolean."""
        return isinstance(value, bool)
    
    @staticmethod
    def validate_list(value: Any, min_length: int = 0, 
                     item_validator: Optional[Callable] = None) -> bool:
        """Validate if a value is a list with optional item validation."""
        if not isinstance(value, list):
            return False
        
        if len(value) < min_length:
            return False
        
        if item_validator:
            for item in value:
                if not item_validator(item):
                    return False
        
        return True
    
    @staticmethod
    def validate_dict(value: Any, required_keys: Optional[List[str]] = None) -> bool:
        """Validate if a value is a dictionary with optional required keys."""
        if not isinstance(value, dict):
            return False
        
        if required_keys:
            for key in required_keys:
                if key not in value:
                    return False
        
        return True
    
    @staticmethod
    def validate_path(value: Any, must_exist: bool = False, 
                     create_if_missing: bool = False) -> bool:
        """Validate if a value is a valid path."""
        if not isinstance(value, str):
            return False
        
        try:
            path = Path(value)
            
            if must_exist and not path.exists():
                if create_if_missing:
                    path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created missing path: {path}")
                else:
                    return False
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def validate_url(value: Any, require_scheme: bool = True) -> bool:
        """Validate if a value is a valid URL."""
        if not isinstance(value, str):
            return False
        
        url_pattern = r'^https?://' if require_scheme else r'^(https?://)?'
        url_pattern += r'[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*(:[0-9]+)?(/.*)?$'
        
        return bool(re.match(url_pattern, value))
    
    @staticmethod
    def validate_log_level(value: Any) -> bool:
        """Validate if a value is a valid log level."""
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        return isinstance(value, str) and value.upper() in valid_levels
    
    @staticmethod
    def validate_telegram_parse_mode(value: Any) -> bool:
        """Validate if a value is a valid Telegram parse mode."""
        valid_modes = {'Markdown', 'HTML', 'None'}
        return isinstance(value, str) and value in valid_modes
    
    @staticmethod
    def validate_rotation_setting(value: Any) -> bool:
        """Validate if a value is a valid log rotation setting."""
        if not isinstance(value, str):
            return False
        
        # Check for various valid formats
        patterns = [
            r'^\d+\s+(day|days)$',    # X days
            r'^\d+\s+(hour|hours)$',  # X hours
            r'^\d+\s+MB$',            # X MB
        ]
        
        return any(re.match(pattern, value) for pattern in patterns)
    
    @staticmethod
    def validate_retention_setting(value: Any) -> bool:
        """Validate if a value is a valid log retention setting."""
        if not isinstance(value, str):
            return False
        
        # Check for various valid formats
        patterns = [
            r'^\d+\s+(day|days)$',    # X days
            r'^\d+\s+(hour|hours)$',  # X hours
            r'^\d+\s+(week|weeks)$',  # X weeks
            r'^\d+\s+(month|months)$', # X months
        ]
        
        return any(re.match(pattern, value) for pattern in patterns)


def validate_app_section(config: Dict[str, Any]) -> None:
    """Validate the 'app' section of the configuration."""
    app_config = config.get('app', {})
    
    if not ConfigValidator.validate_dict(app_config, required_keys=['name', 'version']):
        raise ConfigurationError("'app' section must be a dictionary with 'name' and 'version' keys")
    
    if not ConfigValidator.validate_string(app_config['name'], min_length=1):
        raise ConfigurationError("'app.name' must be a non-empty string")
    
    if not ConfigValidator.validate_string(app_config['version'], pattern=r'^\d+\.\d+\.\d+$'):
        raise ConfigurationError("'app.version' must follow semantic versioning (X.Y.Z)")
    
    if 'debug' in app_config and not ConfigValidator.validate_boolean(app_config['debug']):
        raise ConfigurationError("'app.debug' must be a boolean")


def validate_llm_section(config: Dict[str, Any]) -> None:
    """Validate the 'llm' section of the configuration."""
    llm_config = config.get('llm', {})
    
    if not ConfigValidator.validate_dict(llm_config, required_keys=['default_provider', 'providers']):
        raise ConfigurationError("'llm' section must include 'default_provider' and 'providers'")
    
    providers = llm_config.get('providers', {})
    if not ConfigValidator.validate_dict(providers):
        raise ConfigurationError("'llm.providers' must be a dictionary")
    
    default_provider = llm_config.get('default_provider')
    if default_provider not in providers:
        raise ConfigurationError(f"Default provider '{default_provider}' not found in providers configuration")
    
    # Validate each provider configuration
    for provider_name, provider_config in providers.items():
        if not ConfigValidator.validate_dict(provider_config, required_keys=['base_url', 'models']):
            raise ConfigurationError(f"Provider '{provider_name}' must have 'base_url' and 'models' keys")
        
        if not ConfigValidator.validate_url(provider_config['base_url']):
            raise ConfigurationError(f"Invalid base_url for provider '{provider_name}'")
        
        if not ConfigValidator.validate_list(provider_config['models'], min_length=1):
            raise ConfigurationError(f"Provider '{provider_name}' must have at least one model defined")
    
    # Validate temperature
    if 'temperature' in llm_config:
        if not ConfigValidator.validate_float(llm_config['temperature'], min_value=0.0, max_value=1.0):
            raise ConfigurationError("'llm.temperature' must be a float between 0 and 1")
    
    # Validate max_tokens
    if 'max_tokens' in llm_config:
        if not ConfigValidator.validate_integer(llm_config['max_tokens'], min_value=1):
            raise ConfigurationError("'llm.max_tokens' must be a positive integer")


def validate_telegram_section(config: Dict[str, Any]) -> None:
    """Validate the 'telegram' section of the configuration."""
    telegram_config = config.get('telegram', {})
    
    if not ConfigValidator.validate_dict(telegram_config):
        raise ConfigurationError("'telegram' section must be a dictionary")
    
    # Validate parse_mode
    if 'parse_mode' in telegram_config:
        if not ConfigValidator.validate_telegram_parse_mode(telegram_config['parse_mode']):
            raise ConfigurationError("'telegram.parse_mode' must be 'Markdown', 'HTML', or 'None'")
    
    # Validate reply_timeout
    if 'reply_timeout' in telegram_config:
        if not ConfigValidator.validate_integer(telegram_config['reply_timeout'], min_value=1):
            raise ConfigurationError("'telegram.reply_timeout' must be a positive integer")
    
    # Validate max_message_length
    if 'max_message_length' in telegram_config:
        if not ConfigValidator.validate_integer(telegram_config['max_message_length'], 
                                              min_value=1, max_value=4096):
            raise ConfigurationError("'telegram.max_message_length' must be between 1 and 4096")
    
    # Validate commands
    if 'commands' in telegram_config:
        if not ConfigValidator.validate_dict(telegram_config['commands']):
            raise ConfigurationError("'telegram.commands' must be a dictionary")
        
        for command_name, command_text in telegram_config['commands'].items():
            if not ConfigValidator.validate_string(command_text, pattern=r'^/[a-zA-Z0-9_]+$'):
                raise ConfigurationError(f"Invalid command format for '{command_name}': {command_text}")


def validate_modules_section(config: Dict[str, Any]) -> None:
    """Validate the 'modules' section of the configuration."""
    modules_config = config.get('modules', {})
    
    if not ConfigValidator.validate_dict(modules_config, required_keys=['enabled', 'directory']):
        raise ConfigurationError("'modules' section must be a dictionary with 'enabled' and 'directory' keys")
    
    if not ConfigValidator.validate_boolean(modules_config['enabled']):
        raise ConfigurationError("'modules.enabled' must be a boolean")
    
    if not ConfigValidator.validate_path(modules_config['directory']):
        raise ConfigurationError("'modules.directory' must be a valid path")
    
    # Validate hot_reload
    if 'hot_reload' in modules_config:
        if not ConfigValidator.validate_boolean(modules_config['hot_reload']):
            raise ConfigurationError("'modules.hot_reload' must be a boolean")
    
    # Validate scan_interval
    if 'scan_interval' in modules_config:
        if not ConfigValidator.validate_integer(modules_config['scan_interval'], min_value=1):
            raise ConfigurationError("'modules.scan_interval' must be a positive integer")
    
    # Validate state_storage
    if 'state_storage' in modules_config:
        state_config = modules_config['state_storage']
        if not ConfigValidator.validate_dict(state_config, required_keys=['enabled', 'type']):
            raise ConfigurationError("'modules.state_storage' must have 'enabled' and 'type' keys")
        
        if not ConfigValidator.validate_boolean(state_config['enabled']):
            raise ConfigurationError("'modules.state_storage.enabled' must be a boolean")
        
        valid_storage_types = {'json', 'sqlite', 'redis'}
        if state_config['type'] not in valid_storage_types:
            raise ConfigurationError(f"'modules.state_storage.type' must be one of: {valid_storage_types}")
        
        if state_config['type'] == 'json' and 'path' in state_config:
            if not ConfigValidator.validate_path(state_config['path']):
                raise ConfigurationError("'modules.state_storage.path' must be a valid path")


def validate_logging_section(config: Dict[str, Any]) -> None:
    """Validate the 'logging' section of the configuration."""
    logging_config = config.get('logging', {})
    
    if not ConfigValidator.validate_dict(logging_config):
        raise ConfigurationError("'logging' section must be a dictionary")
    
    # Validate log level
    if 'level' in logging_config:
        if not ConfigValidator.validate_log_level(logging_config['level']):
            raise ConfigurationError("'logging.level' must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    
    # Validate file logging configuration
    if 'file' in logging_config:
        file_config = logging_config['file']
        if not ConfigValidator.validate_dict(file_config):
            raise ConfigurationError("'logging.file' must be a dictionary")
        
        if 'enabled' in file_config:
            if not ConfigValidator.validate_boolean(file_config['enabled']):
                raise ConfigurationError("'logging.file.enabled' must be a boolean")
        
        if 'path' in file_config:
            if not ConfigValidator.validate_path(file_config['path']):
                raise ConfigurationError("'logging.file.path' must be a valid path")
        
        if 'rotation' in file_config:
            if not ConfigValidator.validate_rotation_setting(file_config['rotation']):
                raise ConfigurationError("'logging.file.rotation' has invalid format")
        
        if 'retention' in file_config:
            if not ConfigValidator.validate_retention_setting(file_config['retention']):
                raise ConfigurationError("'logging.file.retention' has invalid format")
    
    # Validate module logging configuration
    if 'module_logging' in logging_config:
        module_config = logging_config['module_logging']
        if not ConfigValidator.validate_dict(module_config):
            raise ConfigurationError("'logging.module_logging' must be a dictionary")
        
        if 'enabled' in module_config:
            if not ConfigValidator.validate_boolean(module_config['enabled']):
                raise ConfigurationError("'logging.module_logging.enabled' must be a boolean")
        
        if 'separate_files' in module_config:
            if not ConfigValidator.validate_boolean(module_config['separate_files']):
                raise ConfigurationError("'logging.module_logging.separate_files' must be a boolean")


def validate_health_section(config: Dict[str, Any]) -> None:
    """Validate the 'health' section of the configuration."""
    health_config = config.get('health', {})
    
    if not ConfigValidator.validate_dict(health_config):
        raise ConfigurationError("'health' section must be a dictionary")
    
    # Validate enabled flag
    if 'enabled' in health_config:
        if not ConfigValidator.validate_boolean(health_config['enabled']):
            raise ConfigurationError("'health.enabled' must be a boolean")
    
    # Validate interval
    if 'interval' in health_config:
        if not ConfigValidator.validate_integer(health_config['interval'], min_value=1):
            raise ConfigurationError("'health.interval' must be a positive integer")
    
    # Validate metrics thresholds
    if 'metrics' in health_config:
        metrics = health_config['metrics']
        if not ConfigValidator.validate_dict(metrics):
            raise ConfigurationError("'health.metrics' must be a dictionary")
        
        if 'memory_threshold' in metrics:
            if not ConfigValidator.validate_integer(metrics['memory_threshold'], min_value=1):
                raise ConfigurationError("'health.metrics.memory_threshold' must be a positive integer")
        
        if 'cpu_threshold' in metrics:
            if not ConfigValidator.validate_integer(metrics['cpu_threshold'], min_value=0, max_value=100):
                raise ConfigurationError("'health.metrics.cpu_threshold' must be between 0 and 100")
        
        if 'disk_threshold' in metrics:
            if not ConfigValidator.validate_integer(metrics['disk_threshold'], min_value=0, max_value=100):
                raise ConfigurationError("'health.metrics.disk_threshold' must be between 0 and 100")
    
    # Validate restart settings
    if 'restarts' in health_config:
        restarts = health_config['restarts']
        if not ConfigValidator.validate_dict(restarts):
            raise ConfigurationError("'health.restarts' must be a dictionary")
        
        if 'auto_restart_on_failure' in restarts:
            if not ConfigValidator.validate_boolean(restarts['auto_restart_on_failure']):
                raise ConfigurationError("'health.restarts.auto_restart_on_failure' must be a boolean")
        
        if 'max_restart_attempts' in restarts:
            if not ConfigValidator.validate_integer(restarts['max_restart_attempts'], min_value=0):
                raise ConfigurationError("'health.restarts.max_restart_attempts' must be a non-negative integer")
        
        if 'restart_delay' in restarts:
            if not ConfigValidator.validate_integer(restarts['restart_delay'], min_value=0):
                raise ConfigurationError("'health.restarts.restart_delay' must be a non-negative integer")


def validate_module_defaults_section(config: Dict[str, Any]) -> None:
    """Validate the 'module_defaults' section of the configuration."""
    defaults_config = config.get('module_defaults', {})
    
    if not ConfigValidator.validate_dict(defaults_config):
        raise ConfigurationError("'module_defaults' section must be a dictionary")
    
    # Validate time_trigger defaults
    if 'time_trigger' in defaults_config:
        time_trigger = defaults_config['time_trigger']
        if not ConfigValidator.validate_dict(time_trigger):
            raise ConfigurationError("'module_defaults.time_trigger' must be a dictionary")
        
        if 'type' in time_trigger:
            valid_types = {'interval', 'cron'}
            if time_trigger['type'] not in valid_types:
                raise ConfigurationError(f"'module_defaults.time_trigger.type' must be one of: {valid_types}")
        
        if 'interval' in time_trigger:
            if not ConfigValidator.validate_integer(time_trigger['interval'], min_value=1):
                raise ConfigurationError("'module_defaults.time_trigger.interval' must be a positive integer")
    
    # Validate event_trigger defaults
    if 'event_trigger' in defaults_config:
        event_trigger = defaults_config['event_trigger']
        if not ConfigValidator.validate_dict(event_trigger):
            raise ConfigurationError("'module_defaults.event_trigger' must be a dictionary")
        
        if 'type' in event_trigger:
            valid_types = {'webhook', 'file_change', 'socket'}
            if event_trigger['type'] not in valid_types:
                raise ConfigurationError(f"'module_defaults.event_trigger.type' must be one of: {valid_types}")
        
        if 'retry_on_failure' in event_trigger:
            if not ConfigValidator.validate_boolean(event_trigger['retry_on_failure']):
                raise ConfigurationError("'module_defaults.event_trigger.retry_on_failure' must be a boolean")
    
    # Validate API settings
    if 'api_settings' in defaults_config:
        api_settings = defaults_config['api_settings']
        if not ConfigValidator.validate_dict(api_settings):
            raise ConfigurationError("'module_defaults.api_settings' must be a dictionary")
        
        if 'timeout' in api_settings:
            if not ConfigValidator.validate_integer(api_settings['timeout'], min_value=1):
                raise ConfigurationError("'module_defaults.api_settings.timeout' must be a positive integer")
        
        if 'max_retries' in api_settings:
            if not ConfigValidator.validate_integer(api_settings['max_retries'], min_value=0):
                raise ConfigurationError("'module_defaults.api_settings.max_retries' must be a non-negative integer")
        
        if 'backoff_factor' in api_settings:
            if not ConfigValidator.validate_float(api_settings['backoff_factor'], min_value=1.0):
                raise ConfigurationError("'module_defaults.api_settings.backoff_factor' must be >= 1.0")


def validate_configuration(config: Dict[str, Any]) -> None:
    """Validate the entire configuration structure."""
    if not isinstance(config, dict):
        raise ConfigurationError("Configuration must be a dictionary")
    
    # Validate each major section
    validate_app_section(config)
    validate_llm_section(config)
    validate_telegram_section(config)
    validate_modules_section(config)
    validate_logging_section(config)
    validate_health_section(config)
    validate_module_defaults_section(config)
    
    logger.info("Configuration validation completed successfully")
