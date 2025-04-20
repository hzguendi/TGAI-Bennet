"""
Module manager for TGAI-Bennet.
Handles dynamic loading, running, and hot-reloading of modules.
"""

import os
import sys
import json
import time
import asyncio
import importlib
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Type, Callable
from datetime import datetime, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import inspect

from src.exceptions import (
    ModuleLoadError, 
    ModuleExecutionError, 
    ModuleNotFoundError,
    ModuleConfigurationError
)
from src.config.loader import get_config
from src.utils.logger import get_logger
from src.modules.base_module import BaseModule, ModuleTrigger


logger = get_logger("module_manager")


class ModuleFileHandler(FileSystemEventHandler):
    """Handler for module file system events."""
    
    def __init__(self, manager):
        self.manager = manager
        
    def on_created(self, event: FileSystemEvent):
        if not event.is_directory and event.src_path.endswith('.py'):
            logger.info(f"New module file detected: {event.src_path}")
            self.manager.schedule_reload()
    
    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory and event.src_path.endswith('.py'):
            logger.info(f"Module file modified: {event.src_path}")
            self.manager.schedule_reload()
    
    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory and event.src_path.endswith('.py'):
            logger.info(f"Module file deleted: {event.src_path}")
            self.manager.schedule_reload()


class ModuleManager:
    """
    Manages loading, running, and hot-reloading of modules.
    """
    
    def __init__(self, bot_instance):
        """
        Initialize the module manager.
        
        Args:
            bot_instance: Reference to the main bot instance for sending messages
        """
        self.config = get_config()
        self.bot = bot_instance
        
        # Get module directory from config
        self.module_dir = Path(self.config.get('modules.directory', 'src/modules')).resolve()
        if not self.module_dir.exists():
            self.module_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created module directory: {self.module_dir}")
        
        # Module storage
        self.modules: Dict[str, BaseModule] = {}
        self.module_tasks: Dict[str, asyncio.Task] = {}
        self.module_errors: Dict[str, List[str]] = {}
        
        # State management
        self.state_file = Path(self.config.get('modules.state_storage.path', 'data/module_states.json'))
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.states: Dict[str, Dict[str, Any]] = self._load_states()
        
        # File system observer for hot reloading
        self.observer = None
        self.reload_scheduled = False
        self.reload_lock = asyncio.Lock()
        
        # Module configuration
        self.enabled = self.config.get('modules.enabled', True)
        self.hot_reload = self.config.get('modules.hot_reload', True)
        self.scan_interval = self.config.get('modules.scan_interval', 60)
        
        # Error handling configuration
        self.max_retries = self.config.get('modules.error_handling.max_retries', 3)
        self.retry_delay = self.config.get('modules.error_handling.retry_delay', 5)
        self.notify_on_error = self.config.get('modules.error_handling.notify_on_error', True)
        
        # Start time for uptime tracking
        self.start_time = datetime.now()
        
        logger.info(f"Module manager initialized with directory: {self.module_dir}")
    
    def _load_states(self) -> Dict[str, Dict[str, Any]]:
        """Load module states from storage."""
        if not self.state_file.exists():
            return {}
        
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load module states: {str(e)}")
            return {}
    
    def _save_states(self):
        """Save module states to storage."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.states, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save module states: {str(e)}")
    
    def _get_module_state(self, module_name: str) -> Dict[str, Any]:
        """Get state for a specific module."""
        return self.states.get(module_name, {})
    
    def _set_module_state(self, module_name: str, state: Dict[str, Any]):
        """Set state for a specific module."""
        self.states[module_name] = state
        self._save_states()
    
    async def _discover_modules(self) -> List[Path]:
        """Discover Python files in the modules directory."""
        modules = []
        if not self.module_dir.exists():
            logger.warning(f"Module directory does not exist: {self.module_dir}")
            return modules
        
        for file_path in self.module_dir.glob("*.py"):
            if file_path.name.startswith("_") or file_path.name == "base_module.py":
                continue
            modules.append(file_path)
        
        return modules
    
    def _load_module_class(self, module_path: Path) -> Optional[Type[BaseModule]]:
        """Load a module class from a Python file."""
        module_name = module_path.stem
        
        try:
            # Add modules directory to path if not already there
            module_dir_str = str(self.module_dir.parent.parent)
            if module_dir_str not in sys.path:
                sys.path.insert(0, module_dir_str)
            
            # Import the module
            spec = importlib.util.spec_from_file_location(
                f"src.modules.{module_name}",
                str(module_path)
            )
            
            if spec is None or spec.loader is None:
                raise ModuleLoadError(f"Failed to load module spec for {module_name}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"src.modules.{module_name}"] = module
            spec.loader.exec_module(module)
            
            # Find the module class
            module_class = None
            for item_name, item in inspect.getmembers(module, inspect.isclass):
                if (item_name != 'BaseModule' and 
                    issubclass(item, BaseModule) and 
                    item.__module__ == module.__name__):
                    module_class = item
                    break
            
            if module_class is None:
                raise ModuleLoadError(
                    f"No valid module class found in {module_name}. "
                    f"Ensure the module has a class that inherits from BaseModule."
                )
            
            return module_class
            
        except Exception as e:
            logger.error(f"Failed to load module {module_name}: {str(e)}")
            raise ModuleLoadError(f"Failed to load module {module_name}: {str(e)}", e)
    
    async def _initialize_module(self, module_class: Type[BaseModule]) -> BaseModule:
        """Initialize a module instance."""
        try:
            # Create module instance with necessary dependencies
            module_name = module_class.__name__
            module_instance = module_class(self.bot, self.config)
            
            # Validate module configuration
            if not module_instance.validate_config():
                raise ModuleConfigurationError(f"Module {module_name} configuration validation failed")
            
            # Load previous state if exists
            state = self._get_module_state(module_name)
            if state:
                await module_instance.load_state(state)
            
            # Initialize the module
            await module_instance.initialize()
            
            return module_instance
            
        except Exception as e:
            raise ModuleLoadError(f"Failed to initialize module: {str(e)}", e)
    
    async def load_module(self, module_path: Path) -> bool:
        """Load a single module from a file path."""
        module_name = module_path.stem
        
        try:
            # Check if module is already loaded
            if module_name in self.modules:
                logger.warning(f"Module {module_name} is already loaded")
                return False
            
            # Load and initialize the module
            module_class = self._load_module_class(module_path)
            if module_class:
                module_instance = await self._initialize_module(module_class)
                self.modules[module_name] = module_instance
                logger.info(f"Successfully loaded module: {module_name}")
                
                # Start the module
                await self.start_module(module_name)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to load module {module_name}: {str(e)}")
            if module_name not in self.module_errors:
                self.module_errors[module_name] = []
            self.module_errors[module_name].append(str(e))
            
            if self.notify_on_error and self.bot:
                await self.bot.send_message(
                    f"❌ Failed to load module '{module_name}': {str(e)}"
                )
            
            return False
    
    async def unload_module(self, module_name: str) -> bool:
        """Unload a specific module."""
        if module_name not in self.modules:
            logger.warning(f"Module {module_name} not found")
            return False
        
        try:
            # Stop the module task
            if module_name in self.module_tasks:
                task = self.module_tasks[module_name]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.module_tasks[module_name]
            
            # Save module state
            module = self.modules[module_name]
            state = await module.save_state()
            if state:
                self._set_module_state(module_name, state)
            
            # Cleanup the module
            await module.cleanup()
            
            # Remove from modules dict
            del self.modules[module_name]
            
            # Remove module from sys.modules
            module_full_name = f"src.modules.{module_name}"
            if module_full_name in sys.modules:
                del sys.modules[module_full_name]
            
            logger.info(f"Successfully unloaded module: {module_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload module {module_name}: {str(e)}")
            return False
    
    async def start_module(self, module_name: str):
        """Start a loaded module."""
        if module_name not in self.modules:
            raise ModuleNotFoundError(f"Module {module_name} not found")
        
        module = self.modules[module_name]
        
        # Stop existing task if any
        if module_name in self.module_tasks:
            task = self.module_tasks[module_name]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Create new task based on trigger type
        if module.trigger.type == ModuleTrigger.TIME:
            task = asyncio.create_task(self._run_time_based_module(module))
        elif module.trigger.type == ModuleTrigger.EVENT:
            task = asyncio.create_task(self._run_event_based_module(module))
        else:
            raise ModuleConfigurationError(f"Unknown trigger type for module {module_name}: {module.trigger.type}")
        
        self.module_tasks[module_name] = task
    
    async def _run_time_based_module(self, module: BaseModule):
        """Run a time-based module."""
        module_name = module.__class__.__name__
        interval = module.trigger.interval
        next_run = datetime.now() + timedelta(seconds=interval)
        retry_count = 0
        
        while True:
            try:
                current_time = datetime.now()
                
                if current_time >= next_run:
                    logger.info(f"Running time-based module: {module_name}")
                    
                    try:
                        await module.run()
                        retry_count = 0  # Reset retry count on success
                        
                    except Exception as e:
                        logger.error(f"Error running module {module_name}: {str(e)}")
                        
                        if retry_count < self.max_retries:
                            retry_count += 1
                            logger.info(f"Retrying module {module_name} ({retry_count}/{self.max_retries})")
                            await asyncio.sleep(self.retry_delay)
                            continue
                        else:
                            logger.error(f"Module {module_name} failed after {self.max_retries} retries")
                            if self.notify_on_error and self.bot:
                                await self.bot.send_message(
                                    f"❌ Module '{module_name}' failed after {self.max_retries} retries: {str(e)}"
                                )
                            retry_count = 0
                    
                    next_run = current_time + timedelta(seconds=interval)
                
                # Sleep for a short time to prevent busy waiting
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                logger.info(f"Time-based module {module_name} task cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in time-based module {module_name}: {str(e)}")
                await asyncio.sleep(5)  # Wait before restarting the loop
    
    async def _run_event_based_module(self, module: BaseModule):
        """Run an event-based module."""
        module_name = module.__class__.__name__
        retry_count = 0
        
        try:
            logger.info(f"Starting event-based module: {module_name}")
            
            # The module should implement its own event handling logic
            await module.run()
            
        except asyncio.CancelledError:
            logger.info(f"Event-based module {module_name} task cancelled")
        except Exception as e:
            logger.error(f"Error in event-based module {module_name}: {str(e)}")
            
            if self.notify_on_error and self.bot:
                await self.bot.send_message(
                    f"❌ Event-based module '{module_name}' failed: {str(e)}"
                )
    
    async def reload_modules(self) -> Dict[str, int]:
        """Reload all modules."""
        async with self.reload_lock:
            logger.info("Starting module reload process")
            
            # Track reload statistics
            stats = {
                'loaded': 0,
                'unloaded': 0,
                'errors': 0
            }
            
            # Discover current modules
            module_files = await self._discover_modules()
            current_module_names = {f.stem for f in module_files}
            loaded_module_names = set(self.modules.keys())
            
            # Unload modules that no longer exist
            for module_name in loaded_module_names:
                if module_name not in current_module_names:
                    logger.info(f"Unloading removed module: {module_name}")
                    if await self.unload_module(module_name):
                        stats['unloaded'] += 1
                    else:
                        stats['errors'] += 1
            
            # Load new or modified modules
            for module_file in module_files:
                module_name = module_file.stem
                
                # Check if module needs reloading
                if module_name in self.modules:
                    try:
                        # Get file modification time
                        mtime = module_file.stat().st_mtime
                        
                        # Check if module has been modified
                        module_instance = self.modules[module_name]
                        if hasattr(module_instance, '_load_time') and mtime <= module_instance._load_time:
                            continue  # Module hasn't been modified
                        
                        # Unload the existing module
                        if await self.unload_module(module_name):
                            stats['unloaded'] += 1
                        else:
                            stats['errors'] += 1
                            continue
                    except Exception as e:
                        logger.error(f"Error checking module {module_name} modification time: {str(e)}")
                        stats['errors'] += 1
                        continue
                
                # Load or reload the module
                try:
                    if await self.load_module(module_file):
                        stats['loaded'] += 1
                    else:
                        stats['errors'] += 1
                except Exception as e:
                    logger.error(f"Error loading module {module_name}: {str(e)}")
                    stats['errors'] += 1
            
            self.reload_scheduled = False
            
            logger.info(
                f"Module reload complete. Loaded: {stats['loaded']}, "
                f"Unloaded: {stats['unloaded']}, Errors: {stats['errors']}"
            )
            
            return stats
    
    def schedule_reload(self):
        """Schedule a module reload to avoid too frequent reloads."""
        if not self.reload_scheduled:
            self.reload_scheduled = True
            # Use the main event loop to schedule reloads
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(lambda: asyncio.create_task(self._delayed_reload()))
                logger.info("Module reload scheduled")
            except RuntimeError:
                # Handle the case when no event loop is running
                logger.info("Module file change detected - will reload on next opportunity")

    
    async def _delayed_reload(self):
        """Perform a delayed reload to batch file system changes."""
        await asyncio.sleep(2)  # Wait for 2 seconds to batch changes
        await self.reload_modules()
    
    async def start(self):
        """Start the module manager."""
        if not self.enabled:
            logger.info("Module manager is disabled in configuration")
            return
        
        # Initial module load
        await self.reload_modules()
        
        # Set up file system observer for hot reloading
        if self.hot_reload:
            self.observer = Observer()
            event_handler = ModuleFileHandler(self)
            self.observer.schedule(event_handler, str(self.module_dir), recursive=False)
            self.observer.start()
            logger.info("Hot reload enabled - watching for module changes")
        
        logger.info("Module manager started")
    
    async def stop(self):
        """Stop the module manager and all modules."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        # Stop all module tasks
        for module_name, task in self.module_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Save states and cleanup all modules
        for module_name, module in self.modules.items():
            try:
                state = await module.save_state()
                if state:
                    self._set_module_state(module_name, state)
                await module.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up module {module_name}: {str(e)}")
        
        self.modules.clear()
        self.module_tasks.clear()
        
        logger.info("Module manager stopped")
    
    def get_module_status(self) -> List[Dict[str, Any]]:
        """Get status of all loaded modules."""
        status = []
        
        for module_name, module in self.modules.items():
            task = self.module_tasks.get(module_name)
            
            module_info = {
                'name': module_name,
                'description': module.description,
                'trigger_type': module.trigger.type.value,
                'interval': module.trigger.interval if module.trigger.type == ModuleTrigger.TIME else None,
                'status': 'running' if task and not task.done() else 'stopped',
                'errors': self.module_errors.get(module_name, [])
            }
            
            status.append(module_info)
        
        return status
    
    def get_module_errors(self) -> Dict[str, List[str]]:
        """Get errors for all modules."""
        return self.module_errors.copy()
    
    def clear_module_errors(self, module_name: Optional[str] = None):
        """Clear errors for a specific module or all modules."""
        if module_name:
            if module_name in self.module_errors:
                del self.module_errors[module_name]
        else:
            self.module_errors.clear()
