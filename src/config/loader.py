"""
Configuration loader for TGAI-Bennet.
Handles loading configuration from YAML files and environment variables.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import copy
from dotenv import load_dotenv

from src.exceptions import ConfigurationError
from src.utils.logger import get_logger


logger = get_logger("config_loader")


class ConfigLoader:
    """
    Loads and manages configuration from various sources:
    - YAML configuration file
    - Environment variables
    - Environment (.env) file
    """
    
    def __init__(self, config_file: str = "conf.yml", env_file: str = ".env"):
        self.config_file = Path(config_file).resolve()
        self.env_file = Path(env_file).resolve()
        self.config: Dict[str, Any] = {}
        
        # Load environment variables from .env file
        self._load_env_file()
        
        # Load YAML configuration
        self._load_yaml_config()
        
        # Override with environment variables
        self._apply_env_overrides()
        
        logger.info(f"Configuration loaded successfully from {self.config_file}")
    
    def _load_env_file(self):
        """Load environment variables from .env file."""
        if not self.env_file.exists():
            logger.warning(f"Environment file not found: {self.env_file}")
            return
        
        try:
            load_dotenv(self.env_file)
            logger.info(f"Loaded environment variables from {self.env_file}")
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load environment file {self.env_file}: {str(e)}", e
            )
    
    def _load_yaml_config(self):
        """Load configuration from YAML file."""
        if not self.config_file.exists():
            raise ConfigurationError(f"Configuration file not found: {self.config_file}")
        
        try:
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f) or {}
            
            # Validate basic structure
            if not isinstance(self.config, dict):
                raise ConfigurationError("Invalid configuration format: root must be a dictionary")
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {str(e)}", e)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration file {self.config_file}: {str(e)}", e
            )
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration."""
        # Mapping of environment variables to configuration paths
        env_mappings = {
            # LLM settings
            'OLLAMA_HOST': 'llm.providers.ollama.base_url',
            'OLLAMA_MODEL': 'llm.providers.ollama.models.0',
            
            # Service settings
            'LOG_LEVEL': 'logging.level',
            'MODULE_CHECK_INTERVAL': 'modules.scan_interval',
            'HEALTH_CHECK_INTERVAL': 'health.interval',
            
            # API settings
            'MAX_RETRIES': 'module_defaults.api_settings.max_retries',
            'TIMEOUT_SECONDS': 'module_defaults.api_settings.timeout',
            'RATE_LIMIT_REQUESTS': 'telegram.max_message_length',  # Using as a proxy
            
            # Telegram settings
            'TELEGRAM_ADMIN_CHAT_ID': 'telegram.admin_chat_id'
        }
        
        for env_var, config_path in env_mappings.items():
            if env_value := os.getenv(env_var):
                self._set_nested_value(config_path, env_value)
                logger.debug(f"Applied environment override: {env_var} -> {config_path}")
    
    def _set_nested_value(self, path: str, value: Any):
        """Set a nested value in the configuration using dot notation."""
        parts = path.split('.')
        target = self.config
        
        for part in parts[:-1]:
            if part.isdigit():
                part = int(part)
                while len(target) <= part:
                    target.append({})
                target = target[part]
            else:
                if part not in target:
                    target[part] = {}
                target = target[part]
        
        # Handle array indices in the last part
        last_part = parts[-1]
        if last_part.isdigit():
            last_part = int(last_part)
            while len(target) <= last_part:
                target.append(None)
        
        # Convert value to appropriate type based on current value
        if isinstance(target, list) and isinstance(last_part, int):
            target[last_part] = self._convert_value(target[last_part] if last_part < len(target) else None, value)
        else:
            target[last_part] = self._convert_value(target.get(last_part), value)
    
    def _convert_value(self, current_value: Any, new_value: str) -> Any:
        """Convert a string value to the appropriate type based on the current value."""
        if current_value is None:
            # Try to infer type
            try:
                # Boolean
                if new_value.lower() in ('true', 'false'):
                    return new_value.lower() == 'true'
                # Integer
                if new_value.isdigit():
                    return int(new_value)
                # Float
                try:
                    if '.' in new_value:
                        return float(new_value)
                except ValueError:
                    pass
                # Default to string
                return new_value
            except Exception:
                return new_value
        
        # Convert based on current type
        try:
            if isinstance(current_value, bool):
                return new_value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(current_value, int):
                return int(new_value)
            elif isinstance(current_value, float):
                return float(new_value)
            else:
                return new_value
        except ValueError:
            logger.warning(f"Failed to convert value '{new_value}' to type {type(current_value).__name__}")
            return new_value
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Example: config.get('llm.temperature', 0.7)
        """
        parts = path.split('.')
        value = self.config
        
        for part in parts:
            if part.isdigit():
                part = int(part)
            
            if isinstance(value, dict):
                value = value.get(part, default)
            elif isinstance(value, list) and isinstance(part, int):
                value = value[part] if part < len(value) else default
            else:
                return default
        
        return value
    
    def reload(self):
        """Reload configuration from files."""
        logger.info("Reloading configuration...")
        old_config = copy.deepcopy(self.config)
        
        try:
            self._load_yaml_config()
            self._apply_env_overrides()
            logger.info("Configuration reloaded successfully")
        except Exception as e:
            # Restore old configuration on failure
            self.config = old_config
            logger.error(f"Failed to reload configuration: {str(e)}")
            raise ConfigurationError(f"Failed to reload configuration: {str(e)}", e)
    
    def save(self, path: Optional[str] = None):
        """Save current configuration to a YAML file."""
        save_path = Path(path) if path else self.config_file
        
        try:
            with open(save_path, 'w') as f:
                yaml.safe_dump(self.config, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Configuration saved to {save_path}")
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration to {save_path}: {str(e)}", e)
    
    def validate(self):
        """Validate the configuration against required fields and types."""
        # Define required fields and their expected types
        required_fields = {
            'app.name': str,
            'app.version': str,
            'llm.default_provider': str,
            'telegram.parse_mode': str,
            'modules.enabled': bool,
            'modules.directory': str,
            'logging.level': str
        }
        
        # Validate required fields
        for field_path, expected_type in required_fields.items():
            value = self.get(field_path)
            if value is None:
                raise ConfigurationError(f"Required field '{field_path}' is missing")
            
            if not isinstance(value, expected_type):
                raise ConfigurationError(
                    f"Field '{field_path}' should be of type {expected_type.__name__}, got {type(value).__name__}"
                )
        
        # Validate LLM provider configuration
        default_provider = self.get('llm.default_provider')
        if default_provider not in self.get('llm.providers', {}):
            raise ConfigurationError(f"Default LLM provider '{default_provider}' not found in providers configuration")
        
        # Validate module directory exists
        module_dir = Path(self.get('modules.directory', 'src/modules')).resolve()
        if not module_dir.exists():
            logger.warning(f"Module directory does not exist: {module_dir}")
        
        logger.info("Configuration validation passed")
    
    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to configuration."""
        return self.get(key)
    
    def __contains__(self, key: str) -> bool:
        """Check if a configuration key exists."""
        try:
            self.get(key)
            return True
        except (KeyError, IndexError):
            return False


# Global config instance
_config: Optional[ConfigLoader] = None

def get_config() -> ConfigLoader:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = ConfigLoader()
    return _config

def reload_config():
    """Reload the global configuration instance."""
    global _config
    if _config is not None:
        _config.reload()
