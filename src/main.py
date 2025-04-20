"""
Main entry point for TGAI-Bennet.
Initializes all components and runs the service.
"""

import asyncio
import signal
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

from src.config.loader import get_config, ConfigLoader
from src.config.validators import validate_configuration
from src.core.bot import TGAIBennet
from src.core.module_manager import ModuleManager
from src.core.health_monitor import HealthMonitor
from src.utils.logger import get_logger
from src.exceptions import ConfigurationError, ServiceError, HealthCheckError


# Initialize logger
logger = get_logger("main")


class TGAIBennetService:
    """Main service class that coordinates all components."""
    
    def __init__(self):
        self.config = None
        self.bot = None
        self.module_manager = None
        self.health_monitor = None
        self.shutdown_flag = asyncio.Event()
        self.restart_required = False
        
    async def initialize(self):
        """Initialize all components of the service."""
        try:
            logger.info("Starting TGAI-Bennet Service initialization...")
            
            # Load and validate configuration
            self.config = get_config()
            validate_configuration(self.config.config)
            logger.info("Configuration loaded and validated successfully")
            
            # Initialize bot
            self.bot = TGAIBennet()
            await self.bot.setup()
            logger.info("Telegram bot initialized successfully")
            
            # Initialize module manager
            self.module_manager = ModuleManager(self.bot)
            self.bot.set_module_manager(self.module_manager)
            await self.module_manager.start()
            logger.info("Module manager initialized successfully")
            
            # Initialize health monitor
            self.health_monitor = HealthMonitor(self.bot, self.module_manager)
            self.bot.set_health_monitor(self.health_monitor)
            await self.health_monitor.start()
            logger.info("Health monitor initialized successfully")
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.error(f"Service initialization failed: {str(e)}")
            raise ServiceError(f"Service initialization failed: {str(e)}", e)
    
    async def start(self):
        """Start the service and all components."""
        try:
            logger.info("Starting TGAI-Bennet Service...")
            
            # Start the bot
            await self.bot.start()
            
            logger.info("TGAI-Bennet Service started successfully")
            
            # Wait for shutdown signal
            await self.shutdown_flag.wait()
            
        except Exception as e:
            logger.error(f"Service start failed: {str(e)}")
            raise ServiceError(f"Service start failed: {str(e)}", e)
    
    async def stop(self):
        """Stop the service and all components gracefully."""
        try:
            logger.info("Stopping TGAI-Bennet Service...")
            
            # Stop health monitor
            if self.health_monitor:
                await self.health_monitor.stop()
            
            # Stop module manager
            if self.module_manager:
                await self.module_manager.stop()
            
            # Stop bot
            if self.bot:
                await self.bot.stop()
            
            logger.info("TGAI-Bennet Service stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during service shutdown: {str(e)}")
            raise ServiceError(f"Error during service shutdown: {str(e)}", e)
    
    def signal_handler(self, sig):
        """Handle shutdown signals."""
        logger.info(f"Received signal {sig}. Initiating shutdown...")
        self.shutdown_flag.set()
    
    async def handle_restart(self):
        """Handle service restart requests."""
        logger.info("Service restart requested")
        self.restart_required = True
        self.shutdown_flag.set()


async def main():
    """Main entry point for the application."""
    try:
        # Change working directory to project root
        project_root = Path(__file__).parent.parent
        os.chdir(project_root)
        
        # Load environment variables
        env_path = project_root / ".env"
        if not env_path.exists():
            logger.error(".env file not found. Please copy .env.sample to .env and configure it.")
            sys.exit(1)
        
        load_dotenv(env_path)
        
        # Create service instance
        service = TGAIBennetService()
        
        # Set up signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: service.signal_handler(s))
        
        # Initialize and start service
        await service.initialize()
        await service.start()
        
        # Clean shutdown
        await service.stop()
        
        # Check if restart is required
        if service.restart_required:
            logger.info("Restarting service...")
            os.execv(sys.executable, ['python'] + sys.argv)
        
    except KeyboardInterrupt:
        logger.info("Service stopped by keyboard interrupt")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {str(e)}")
        sys.exit(2)
    except HealthCheckError as e:
        logger.error(f"Health check error: {str(e)}")
        sys.exit(3)
    except Exception as e:
        logger.exception(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
