# TGAI-Bennet Module Development Guide

This guide provides detailed information about creating and developing modules for TGAI-Bennet.

## Module Architecture

Modules are the core extensibility feature of TGAI-Bennet. Each module is a Python class that inherits from the `BaseModule` class and implements specific methods. Modules can be triggered by time (running on a schedule) or by events (responding to external events).

## Module Types

TGAI-Bennet supports two types of modules:

1. **Time-Triggered Modules**: Run on a schedule (e.g., every hour, every day)
2. **Event-Triggered Modules**: Respond to external events (e.g., webhooks, file changes)

## Creating a New Module

### Basic Steps

1. Create a new Python file in the `src/modules` directory
2. Import the necessary classes from `src.modules.base_module`
3. Create a class that inherits from `BaseModule`
4. Implement the required methods
5. Define the trigger type and configuration

### Required Methods

Every module must implement the following methods:

1. **`initialize()`**: Called when the module is loaded
2. **`run()`**: Main execution method that contains the module's logic
3. **`cleanup()`**: Called when the module is unloaded

### Module Template

Here's a basic template for a new module:

```python
from src.modules.base_module import BaseModule, ModuleTrigger, TriggerConfig
from typing import Dict, Any, Optional

class MyModule(BaseModule):
    """
    Description of your module.
    """
    
    def __init__(self, bot_instance, config):
        super().__init__(bot_instance, config)
        
        # Module metadata
        self.description = "Description of what this module does"
        self.author = "Your Name"
        self.version = "1.0.0"
        
        # Set trigger type (time or event)
        self.trigger = TriggerConfig(
            ModuleTrigger.TIME,
            interval=3600  # Run every hour
        )
        
        # Module-specific configuration
        self.some_setting = self.get_config('some_setting', 'default_value')
        
        # Module state (persisted between restarts)
        self.state = {
            'last_run': None,
            'some_counter': 0
        }
    
    async def initialize(self) -> None:
        """Initialize the module."""
        self.log_info("Initializing module")
        
        # Perform any setup tasks here
        
    async def run(self) -> None:
        """Main execution method."""
        self.log_info("Running module")
        
        try:
            # Your module logic goes here
            
            # Example: Generate LLM response
            prompt = "Generate some interesting information"
            response = await self.generate_llm_response(prompt)
            
            # Example: Send message to Telegram
            await self.send_telegram_message(
                self.format_telegram_response(
                    "My Module Update",
                    response,
                    status='info'
                )
            )
            
            # Update state
            self.state['last_run'] = datetime.now().isoformat()
            self.state['some_counter'] += 1
            
        except Exception as e:
            self.log_error(f"Error running module: {str(e)}", e)
    
    async def cleanup(self) -> None:
        """Clean up resources used by the module."""
        self.log_info("Cleaning up module")
        
        # Release any resources, close connections, etc.
    
    def validate_config(self) -> bool:
        """Validate module configuration."""
        # Check if required configuration is present
        if not self.get_config('required_setting'):
            self.log_error("Missing required_setting")
            return False
        
        return True
    
    async def save_state(self) -> Dict[str, Any]:
        """Save the current state of the module."""
        return self.state
    
    async def load_state(self, state: Dict[str, Any]) -> None:
        """Load a previously saved state."""
        self.state = state
```

## Time-Triggered Modules

Time-triggered modules run on a schedule. You can configure the trigger type and interval in the constructor:

```python
self.trigger = TriggerConfig(
    ModuleTrigger.TIME,
    interval=3600  # Run every hour (in seconds)
)
```

In time-triggered modules, the `run()` method is called periodically according to the interval you specified.

### Example Time-Triggered Module

```python
from src.modules.base_module import BaseModule, ModuleTrigger, TriggerConfig
from datetime import datetime

class DailyReportModule(BaseModule):
    def __init__(self, bot_instance, config):
        super().__init__(bot_instance, config)
        self.description = "Sends a daily report"
        self.trigger = TriggerConfig(
            ModuleTrigger.TIME,
            interval=86400  # 24 hours in seconds
        )
    
    async def initialize(self) -> None:
        self.log_info("Daily Report Module initialized")
    
    async def run(self) -> None:
        self.log_info("Generating daily report")
        
        # Generate report content using LLM
        prompt = "Generate a brief daily report with weather, news, and an inspirational quote"
        report = await self.generate_llm_response(prompt)
        
        # Format and send the report
        current_date = datetime.now().strftime("%Y-%m-%d")
        message = self.format_telegram_response(
            f"Daily Report - {current_date}",
            report,
            status='info'
        )
        
        await self.send_telegram_message(message)
    
    async def cleanup(self) -> None:
        self.log_info("Daily Report Module cleaned up")
```

## Event-Triggered Modules

Event-triggered modules respond to external events. These modules need to set up their own event handling logic in the `run()` method.

```python
self.trigger = TriggerConfig(
    ModuleTrigger.EVENT,
    event_type='webhook',
    event_config={'endpoint': '/webhook'}
)
```

### Example Event-Triggered Module

```python
from src.modules.base_module import BaseModule, ModuleTrigger, TriggerConfig
import aiohttp
import asyncio

class StockPriceAlertModule(BaseModule):
    def __init__(self, bot_instance, config):
        super().__init__(bot_instance, config)
        self.description = "Monitors stock prices and sends alerts"
        self.trigger = TriggerConfig(
            ModuleTrigger.EVENT,
            event_type='price_check',
            event_config={'check_interval': 60}  # Check every minute
        )
        
        self.stock_symbol = self.get_config('stock_symbol', 'AAPL')
        self.threshold = self.get_config('price_threshold', 200.0)
        self.running = False
    
    async def initialize(self) -> None:
        self.log_info(f"Stock Price Alert Module initialized for {self.stock_symbol}")
    
    async def run(self) -> None:
        self.running = True
        
        while self.running:
            try:
                # Check stock price
                price = await self._fetch_stock_price(self.stock_symbol)
                
                # If price crosses threshold, trigger an event
                if price > self.threshold:
                    await self.handle_event('price_threshold_crossed', {
                        'symbol': self.stock_symbol,
                        'price': price,
                        'threshold': self.threshold
                    })
                
                # Wait for the next check
                await asyncio.sleep(self.trigger.event_config['check_interval'])
                
            except asyncio.CancelledError:
                self.running = False
                break
            except Exception as e:
                self.log_error(f"Error checking stock price: {str(e)}", e)
                await asyncio.sleep(60)  # Wait before retrying
    
    async def handle_event(self, event_type: str, event_data: dict) -> None:
        if event_type == 'price_threshold_crossed':
            symbol = event_data['symbol']
            price = event_data['price']
            
            # Generate alert using LLM
            prompt = f"Generate a stock price alert for {symbol} which is now at ${price:.2f}"
            alert = await self.generate_llm_response(prompt)
            
            # Send the alert
            message = self.format_telegram_response(
                f"Stock Alert: {symbol}",
                alert,
                status='warning'
            )
            
            await self.send_telegram_message(message)
    
    async def _fetch_stock_price(self, symbol: str) -> float:
        # Example implementation using a stock API
        url = f"https://some-stock-api.com/price/{symbol}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['price'])
                else:
                    raise Exception(f"Failed to fetch stock price: {response.status}")
    
    async def cleanup(self) -> None:
        self.running = False
        self.log_info("Stock Price Alert Module cleaned up")
```

## Module State Management

Modules can maintain state between runs and even across service restarts. The state is stored in the `self.state` dictionary and is automatically saved and loaded by the module manager.

### Saving State

```python
async def save_state(self) -> Dict[str, Any]:
    # Add any additional dynamic state
    self.state['last_run'] = datetime.now().isoformat()
    return self.state
```

### Loading State

```python
async def load_state(self, state: Dict[str, Any]) -> None:
    self.state = state
    self.log_info(f"Loaded state: {state}")
```

## Using the LLM

Modules can generate responses from the LLM provider:

```python
async def generate_response(self):
    prompt = "Create a weather forecast for tomorrow"
    system_message = "You are a helpful weather assistant"
    
    response = await self.generate_llm_response(
        prompt=prompt,
        system_message=system_message,
        temperature=0.7,
        max_tokens=200
    )
    
    return response
```

## Sending Telegram Messages

Modules can send messages to the Telegram chat:

```python
await self.send_telegram_message(
    "This is a message from my module",
    chat_id=None  # Defaults to admin chat ID
)
```

## Formatting Telegram Messages

Use the formatting helper to create consistent messages:

```python
message = self.format_telegram_response(
    "Module Alert",
    "This is the content of the alert",
    status='warning',  # Options: info, success, warning, error
    code_block="Optional code block content"
)

await self.send_telegram_message(message)
```

## Logging

Modules have access to logging methods:

```python
self.log_info("This is an info message")
self.log_warning("This is a warning message")
self.log_error("This is an error message", exception)
self.log_debug("This is a debug message")
```

## Module Testing

It's recommended to test your modules before deploying them. You can create test files in the project root:

```python
# test_my_module.py
import asyncio
from src.modules.my_module import MyModule
from unittest.mock import MagicMock

async def test_module():
    # Create mock objects
    bot_mock = MagicMock()
    config_mock = MagicMock()
    config_mock.get.return_value = None
    
    # Initialize the module
    module = MyModule(bot_mock, config_mock)
    
    # Test initialization
    await module.initialize()
    
    # Test running
    await module.run()
    
    # Test cleanup
    await module.cleanup()
    
    print("Test completed successfully")

if __name__ == "__main__":
    asyncio.run(test_module())
```

## Best Practices

1. **Error Handling**: Always handle exceptions in your module to prevent crashes.
2. **Resource Management**: Clean up resources in the `cleanup()` method.
3. **Configurability**: Make your module configurable using the `get_config()` method.
4. **Logging**: Use the provided logging methods for better debugging.
5. **State Management**: Use the state mechanism for persistent data.
6. **Efficiency**: Be mindful of resource usage, especially in frequently running modules.
7. **Validation**: Implement the `validate_config()` method to check required settings.
8. **Documentation**: Add docstrings and comments to document your module.
9. **Concurrency**: Be careful with shared resources in concurrent operations.
10. **Idempotency**: Make your module idempotent to avoid problems with repeated execution.

## Module Hot Reloading

TGAI-Bennet supports hot reloading of modules. You can add, modify, or remove modules without restarting the service. The module manager will automatically detect changes and reload the affected modules.

To trigger a manual reload, use the `/reload_modules` command in Telegram.
