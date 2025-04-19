"""
Advanced logging system for TGAI-Bennet with module-specific loggers and rotation.
"""

import os
import sys
from typing import Dict, Optional
from loguru import logger
import yaml
from datetime import datetime
from pathlib import Path


class BennetLogger:
    """
    Custom logger class that handles:
    - Main application logging
    - Module-specific logging with separate files
    - Log rotation
    - Different log levels per module
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.module_loggers: Dict[str, logger] = {}
        self._setup_main_logger()
        
    def _load_config(self, config_path: Optional[str] = None) -> dict:
        """Load logging configuration from YAML file."""
        if config_path:
            with open(config_path, 'r') as f:
                full_config = yaml.safe_load(f)
                return full_config.get('logging', {})
        else:
            # Default configuration
            return {
                'level': 'INFO',
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                'file': {
                    'enabled': True,
                    'path': 'logs/tgai-bennet.log',
                    'rotation': '1 day',
                    'retention': '30 days'
                },
                'module_logging': {
                    'enabled': True,
                    'separate_files': True,
                    'path_template': 'logs/modules/{module_name}.log'
                }
            }
    
    def _parse_rotation(self, rotation: str) -> dict:
        """Parse rotation string into loguru parameters."""
        if 'MB' in rotation:
            size = int(rotation.replace('MB', '').strip())
            return {'rotation': f"{size} MB"}
        elif 'day' in rotation:
            days = int(rotation.replace('day', '').replace('s', '').strip())
            return {'rotation': f"{days} days"}
        elif 'hour' in rotation:
            hours = int(rotation.replace('hour', '').replace('s', '').strip())
            return {'rotation': f"{hours} hours"}
        else:
            # Default to daily rotation
            return {'rotation': '1 day'}
    
    def _setup_main_logger(self):
        """Configure the main application logger."""
        # Remove default logger configuration
        logger.remove()
        
        # Add console handler
        logger.add(
            sys.stdout,
            level=self.config.get('level', 'INFO'),
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            colorize=True
        )
        
        # Add file handler if enabled
        if self.config.get('file', {}).get('enabled', True):
            log_path = self.config['file'].get('path', 'logs/tgai-bennet.log')
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            
            rotation_params = self._parse_rotation(
                self.config['file'].get('rotation', '1 day')
            )
            
            retention = self.config['file'].get('retention', '30 days')
            
            logger.add(
                log_path,
                level=self.config.get('level', 'INFO'),
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                retention=retention,
                compression="zip",
                enqueue=True,
                catch=True,
                **rotation_params
            )
        
        logger.info("Main logger initialized")
    
    def get_module_logger(self, module_name: str, level: Optional[str] = None) -> logger:
        """Get or create a logger for a specific module."""
        if module_name in self.module_loggers:
            return self.module_loggers[module_name]
        
        # Create a new module-specific logger
        module_logger = logger.bind(module=module_name)
        
        # If separate files for modules are enabled
        if (self.config.get('module_logging', {}).get('enabled', True) and 
            self.config.get('module_logging', {}).get('separate_files', True)):
            
            path_template = self.config['module_logging'].get(
                'path_template', 'logs/modules/{module_name}.log'
            )
            module_log_path = path_template.format(module_name=module_name)
            os.makedirs(os.path.dirname(module_log_path), exist_ok=True)
            
            rotation_params = self._parse_rotation(
                self.config['file'].get('rotation', '1 day')
            )
            
            retention = self.config['file'].get('retention', '30 days')
            
            # Add file handler for module
            module_logger.add(
                module_log_path,
                level=level or self.config.get('level', 'INFO'),
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
                retention=retention,
                compression="zip",
                enqueue=True,
                catch=True,
                filter=lambda record: record["extra"].get("module") == module_name,
                **rotation_params
            )
        
        self.module_loggers[module_name] = module_logger
        logger.info(f"Logger initialized for module: {module_name}")
        return module_logger
    
    def log_exception(self, exc: Exception, module_name: Optional[str] = None):
        """Log an exception with full traceback."""
        if module_name and module_name in self.module_loggers:
            self.module_loggers[module_name].exception(str(exc))
        else:
            logger.exception(str(exc))
    
    def log_metrics(self, metrics: dict, module_name: Optional[str] = None):
        """Log metrics in a standardized format."""
        log_msg = f"Metrics: {metrics}"
        if module_name and module_name in self.module_loggers:
            self.module_loggers[module_name].info(log_msg)
        else:
            logger.info(log_msg)
    
    def set_log_level(self, level: str, module_name: Optional[str] = None):
        """Change log level for main logger or specific module."""
        if module_name and module_name in self.module_loggers:
            # Note: Changing log level dynamically for specific handlers in loguru is complex
            # This is a placeholder for the functionality
            logger.warning(f"Dynamic log level change for modules is not fully implemented. Level: {level}")
        else:
            logger.remove()
            self.config['level'] = level
            self._setup_main_logger()


# Global logger instance
bennet_logger = None

def get_logger(module_name: Optional[str] = None) -> logger:
    """Get the main logger or a module-specific logger."""
    global bennet_logger
    
    if bennet_logger is None:
        bennet_logger = BennetLogger()
    
    if module_name:
        return bennet_logger.get_module_logger(module_name)
    else:
        return logger
