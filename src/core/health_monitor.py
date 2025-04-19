"""
Health monitoring module for TGAI-Bennet.
Monitors system resources, module health, and sends alerts when issues are detected.
"""

import os
import time
import psutil
import asyncio
import platform
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json

from src.exceptions import HealthCheckError
from src.config.loader import get_config
from src.utils.logger import get_logger
from src.utils.telegram_formatter import TelegramFormatter


logger = get_logger("health_monitor")


class HealthMonitor:
    """
    Health monitoring system for TGAI-Bennet.
    Monitors CPU, memory, disk usage, and module health.
    """
    
    def __init__(self, bot_instance, module_manager):
        """
        Initialize the health monitor.
        
        Args:
            bot_instance: Reference to the main bot instance for sending alerts
            module_manager: Reference to the module manager for checking module health
        """
        self.config = get_config()
        self.bot = bot_instance
        self.module_manager = module_manager
        
        # Configuration
        self.enabled = self.config.get('health.enabled', True)
        self.check_interval = self.config.get('health.interval', 300)  # 5 minutes default
        
        # Thresholds
        self.memory_threshold = self.config.get('health.metrics.memory_threshold', 500)  # MB
        self.cpu_threshold = self.config.get('health.metrics.cpu_threshold', 80)  # Percent
        self.disk_threshold = self.config.get('health.metrics.disk_threshold', 90)  # Percent
        
        # Notification settings
        self.telegram_errors = self.config.get('health.notifications.telegram_errors', True)
        self.log_errors = self.config.get('health.notifications.log_errors', True)
        
        # Restart settings
        self.auto_restart = self.config.get('health.restarts.auto_restart_on_failure', True)
        self.max_restart_attempts = self.config.get('health.restarts.max_restart_attempts', 3)
        self.restart_delay = self.config.get('health.restarts.restart_delay', 30)
        
        # Tracking
        self.start_time = datetime.now()
        self.restart_count = 0
        self.last_check_time = None
        self.health_task = None
        self.last_alert_time: Dict[str, datetime] = {}
        self.alert_cooldown = 300  # 5 minutes cooldown between similar alerts
        
        # Current metrics
        self.current_metrics: Dict[str, Any] = {}
        
        logger.info("Health monitor initialized")
    
    def _should_send_alert(self, alert_type: str) -> bool:
        """Check if an alert should be sent based on cooldown."""
        now = datetime.now()
        last_alert = self.last_alert_time.get(alert_type)
        
        if last_alert is None:
            return True
        
        time_since_last = (now - last_alert).total_seconds()
        return time_since_last >= self.alert_cooldown
    
    def _record_alert_sent(self, alert_type: str):
        """Record when an alert was sent."""
        self.last_alert_time[alert_type] = datetime.now()
    
    def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        return psutil.cpu_percent(interval=1)
    
    def _get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage."""
        memory = psutil.virtual_memory()
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info()
        
        return {
            'total_gb': memory.total / (1024 ** 3),
            'available_gb': memory.available / (1024 ** 3),
            'used_percent': memory.percent,
            'process_rss_mb': process_memory.rss / (1024 ** 2),  # Resident Set Size
            'process_vms_mb': process_memory.vms / (1024 ** 2)   # Virtual Memory Size
        }
    
    def _get_disk_usage(self) -> Dict[str, float]:
        """Get disk usage for the current working directory."""
        disk = psutil.disk_usage(os.getcwd())
        
        return {
            'total_gb': disk.total / (1024 ** 3),
            'used_gb': disk.used / (1024 ** 3),
            'free_gb': disk.free / (1024 ** 3),
            'used_percent': disk.percent
        }
    
    def _get_system_info(self) -> Dict[str, str]:
        """Get basic system information."""
        return {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'hostname': platform.node(),
            'cpu_count': psutil.cpu_count(),
            'boot_time': datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')
        }
    
    async def _check_cpu(self) -> Dict[str, Any]:
        """Check CPU usage and alert if threshold exceeded."""
        cpu_usage = self._get_cpu_usage()
        
        result = {
            'usage': cpu_usage,
            'threshold': self.cpu_threshold,
            'exceeded': cpu_usage > self.cpu_threshold
        }
        
        if result['exceeded'] and self._should_send_alert('cpu'):
            alert_message = TelegramFormatter.alert_message(
                "High CPU Usage",
                f"CPU usage is at {cpu_usage:.1f}% (threshold: {self.cpu_threshold}%)",
                severity='warning' if cpu_usage < 90 else 'error'
            )
            
            await self._send_alert(alert_message, 'cpu')
        
        return result
    
    async def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage and alert if threshold exceeded."""
        memory_info = self._get_memory_usage()
        process_memory_mb = memory_info['process_rss_mb']
        
        result = {
            'usage_mb': process_memory_mb,
            'threshold_mb': self.memory_threshold,
            'exceeded': process_memory_mb > self.memory_threshold,
            'system_memory': memory_info
        }
        
        if result['exceeded'] and self._should_send_alert('memory'):
            alert_message = TelegramFormatter.alert_message(
                "High Memory Usage",
                f"Process memory usage is at {process_memory_mb:.1f} MB (threshold: {self.memory_threshold} MB)\n"
                f"System memory: {memory_info['used_percent']:.1f}% used",
                severity='warning' if process_memory_mb < self.memory_threshold * 1.5 else 'error'
            )
            
            await self._send_alert(alert_message, 'memory')
        
        return result
    
    async def _check_disk(self) -> Dict[str, Any]:
        """Check disk usage and alert if threshold exceeded."""
        disk_info = self._get_disk_usage()
        disk_percent = disk_info['used_percent']
        
        result = {
            'usage_percent': disk_percent,
            'threshold_percent': self.disk_threshold,
            'exceeded': disk_percent > self.disk_threshold,
            'disk_info': disk_info
        }
        
        if result['exceeded'] and self._should_send_alert('disk'):
            alert_message = TelegramFormatter.alert_message(
                "High Disk Usage",
                f"Disk usage is at {disk_percent:.1f}% (threshold: {self.disk_threshold}%)\n"
                f"Free space: {disk_info['free_gb']:.1f} GB",
                severity='warning' if disk_percent < 95 else 'critical'
            )
            
            await self._send_alert(alert_message, 'disk')
        
        return result
    
    async def _check_modules(self) -> Dict[str, Any]:
        """Check health of all modules."""
        if not self.module_manager:
            return {'status': 'Module manager not available'}
        
        module_status = self.module_manager.get_module_status()
        module_errors = self.module_manager.get_module_errors()
        
        result = {
            'total_modules': len(module_status),
            'running_modules': sum(1 for m in module_status if m['status'] == 'running'),
            'stopped_modules': sum(1 for m in module_status if m['status'] == 'stopped'),
            'modules_with_errors': sum(1 for _, errors in module_errors.items() if errors),
            'module_details': module_status,
            'error_summary': {name: len(errors) for name, errors in module_errors.items() if errors}
        }
        
        # Alert on module errors
        if result['modules_with_errors'] > 0 and self._should_send_alert('modules'):
            error_details = []
            for name, errors in module_errors.items():
                if errors:
                    error_details.append(f"• {name}: {len(errors)} errors")
            
            alert_message = TelegramFormatter.alert_message(
                "Module Errors Detected",
                f"{result['modules_with_errors']} module(s) have errors:\n" + '\n'.join(error_details),
                severity='error'
            )
            
            await self._send_alert(alert_message, 'modules')
        
        return result
    
    async def _check_bot_connection(self) -> Dict[str, Any]:
        """Check if the bot is connected to Telegram."""
        try:
            if not self.bot or not self.bot.bot:
                return {'connected': False, 'error': 'Bot instance not available'}
            
            # Try to get bot info
            bot_info = await self.bot.bot.get_me()
            
            return {
                'connected': True,
                'bot_username': bot_info.username,
                'bot_id': bot_info.id
            }
            
        except Exception as e:
            logger.error(f"Bot connection check failed: {str(e)}")
            
            if self._should_send_alert('bot_connection'):
                alert_message = TelegramFormatter.alert_message(
                    "Bot Connection Error",
                    f"Failed to connect to Telegram: {str(e)}",
                    severity='critical'
                )
                
                await self._send_alert(alert_message, 'bot_connection')
            
            return {
                'connected': False,
                'error': str(e)
            }
    
    async def _send_alert(self, message: str, alert_type: str):
        """Send an alert message via Telegram and/or logs."""
        if self.log_errors:
            logger.error(f"Health alert [{alert_type}]: {message}")
        
        if self.telegram_errors and self.bot:
            try:
                await self.bot.send_message(message)
                self._record_alert_sent(alert_type)
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {str(e)}")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        uptime = datetime.now() - self.start_time
        
        # Perform all health checks
        cpu_check = await self._check_cpu()
        memory_check = await self._check_memory()
        disk_check = await self._check_disk()
        module_check = await self._check_modules()
        bot_check = await self._check_bot_connection()
        
        # Compile overall status
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'uptime': str(uptime),
            'restart_count': self.restart_count,
            'last_check': self.last_check_time.isoformat() if self.last_check_time else None,
            'system_info': self._get_system_info(),
            'cpu': cpu_check,
            'memory': memory_check,
            'disk': disk_check,
            'modules': module_check,
            'bot_connection': bot_check,
            'overall_status': 'healthy'  # Will be updated based on checks
        }
        
        # Determine overall status
        if (not bot_check['connected'] or 
            cpu_check['exceeded'] or 
            memory_check['exceeded'] or 
            disk_check['exceeded'] or 
            module_check.get('modules_with_errors', 0) > 0):
            health_status['overall_status'] = 'unhealthy'
        
        self.current_metrics = health_status
        return health_status
    
    async def _handle_critical_issues(self, health_status: Dict[str, Any]):
        """Handle critical issues that may require restart."""
        if not self.auto_restart:
            return
        
        # Check for critical conditions
        critical_conditions = [
            not health_status['bot_connection']['connected'],
            health_status['cpu']['usage'] > 95,
            health_status['memory']['usage_mb'] > self.memory_threshold * 2,
            health_status['disk']['usage_percent'] > 99
        ]
        
        if any(critical_conditions) and self.restart_count < self.max_restart_attempts:
            logger.warning("Critical condition detected - attempting restart")
            
            alert_message = TelegramFormatter.alert_message(
                "Service Restart",
                f"Critical condition detected. Attempting restart ({self.restart_count + 1}/{self.max_restart_attempts})",
                severity='critical'
            )
            
            await self._send_alert(alert_message, 'service_restart')
            
            self.restart_count += 1
            
            # Wait before restart
            await asyncio.sleep(self.restart_delay)
            
            # Signal restart (main application should handle this)
            raise HealthCheckError("Service restart required due to critical conditions")
    
    async def _run_health_check(self):
        """Run periodic health checks."""
        while True:
            try:
                logger.debug("Running health check")
                health_status = await self.get_health_status()
                self.last_check_time = datetime.now()
                
                # Handle critical issues
                await self._handle_critical_issues(health_status)
                
                # Log summary
                if health_status['overall_status'] == 'unhealthy':
                    logger.warning(f"Health check: UNHEALTHY - {health_status}")
                else:
                    logger.info(f"Health check: HEALTHY")
                
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Health check task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check: {str(e)}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def start(self):
        """Start the health monitor."""
        if not self.enabled:
            logger.info("Health monitor is disabled in configuration")
            return
        
        self.health_task = asyncio.create_task(self._run_health_check())
        logger.info("Health monitor started")
    
    async def stop(self):
        """Stop the health monitor."""
        if self.health_task and not self.health_task.done():
            self.health_task.cancel()
            try:
                await self.health_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitor stopped")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current health metrics."""
        return self.current_metrics
