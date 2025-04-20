# TGAI-Bennet

TGAI-Bennet is a modular Telegram bot that connects to various LLM providers (OpenAI, OpenRouter, DeepSeek, Ollama) and allows you to chat with them through Telegram. It also includes a flexible module system that can perform various automated tasks and send you the results.

## Features

- 🤖 Chat with various LLM providers directly through Telegram
- 🧩 Modular architecture for easy extension
- 📅 Support for time-triggered modules (run on schedule)
- 🎬 Support for event-triggered modules (respond to external events)
- 🔥 Hot reloading of modules (add/modify modules without restarting)
- 📊 Health monitoring with alerts
- 🔒 Secure configuration management
- 📝 Extensive logging
- 🚀 Easy installation with systemd service

## Requirements

- Python 3.7 or newer
- Linux system with systemd (for service installation)
- Telegram Bot token (get from [@BotFather](https://t.me/BotFather))
- API key for at least one of the supported LLM providers

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/hzguendi/TGAI-Bennet.git
   cd TGAI-Bennet
   ```

2. Run the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. Edit the `.env` file with your API keys and Telegram credentials:
   ```bash
   nano .env
   ```

4. Start the service:
   ```bash
   sudo systemctl start tgai-bennet
   ```

## Configuration

### Environment Variables

Create a `.env` file based on the provided `.env.sample` with the following variables:

```
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_ADMIN_CHAT_ID=your_telegram_chat_id_here

# LLM Provider API Keys
OPENAI_API_KEY=your_openai_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Ollama Configuration (local deployment)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2
```

### Application Configuration

The `conf.yml` file contains all the configurable parameters for the application:

- LLM providers and models
- Telegram bot settings
- Module configuration
- Logging settings
- Health monitoring thresholds

## Usage

### Basic Commands

- `/start` - Start the bot and get a welcome message
- `/help` - Show available commands

### Admin Commands

- `/reload_modules` - Reload all modules (useful after adding new modules)
- `/reload_config` - Reload configuration from `conf.yml`
- `/status` - Show bot status and statistics
- `/health` - Run and display health check
- `/stop` - Gracefully stop the bot

### Chatting with the LLM

Simply send a message to the bot, and it will respond using the configured LLM provider.

## Creating Modules

Modules are the core extensibility feature of TGAI-Bennet. To create a new module:

1. Create a new Python file in the `src/modules` directory
2. Inherit from the `BaseModule` class
3. Implement the required methods

### Example Time-Triggered Module

```python
from src.modules.base_module import BaseModule, ModuleTrigger, TriggerConfig

class MyTimerModule(BaseModule):
    def __init__(self, bot_instance, config):
        super().__init__(bot_instance, config)
        self.description = "This module runs every hour"
        self.trigger = TriggerConfig(ModuleTrigger.TIME, interval=3600)
    
    async def initialize(self) -> None:
        self.log_info("Module initialized")
    
    async def run(self) -> None:
        response = await self.generate_llm_response("Generate a daily tip")
        await self.send_telegram_message(response)
    
    async def cleanup(self) -> None:
        self.log_info("Module cleaned up")
```

### Example Event-Triggered Module

```python
from src.modules.base_module import BaseModule, ModuleTrigger, TriggerConfig

class MyEventModule(BaseModule):
    def __init__(self, bot_instance, config):
        super().__init__(bot_instance, config)
        self.description = "This module responds to events"
        self.trigger = TriggerConfig(
            ModuleTrigger.EVENT,
            event_type='webhook',
            event_config={'endpoint': '/webhook'}
        )
    
    async def initialize(self) -> None:
        self.log_info("Module initialized")
    
    async def run(self) -> None:
        # For event modules, this method sets up the event listeners
        while True:
            # Listen for events and call handle_event when they occur
            event_data = await self._listen_for_events()
            await self.handle_event('data_received', event_data)
            
    async def handle_event(self, event_type: str, event_data: dict) -> None:
        if event_type == 'data_received':
            response = await self.generate_llm_response(
                f"Analyze this data: {event_data}"
            )
            await self.send_telegram_message(response)
    
    async def cleanup(self) -> None:
        self.log_info("Module cleaned up")
```

## Sample Modules

Two sample modules are included to demonstrate the module system:

1. **Weather Alert Module** (`weather_alert.py.sample`) - Checks weather forecasts and alerts when rain is expected tomorrow
2. **BTC Price Monitor** (`btc_price_monitor.py.sample`) - Monitors Bitcoin price and sends alerts on significant changes

To use these samples, rename them to remove the `.sample` extension.

## Logging

Logs are stored in the `logs` directory:

- `logs/tgai-bennet.log` - Main application log
- `logs/modules/ModuleName.log` - Individual module logs

## Health Monitoring

The built-in health monitor checks:

- CPU usage
- Memory usage
- Disk space
- Module health
- Bot connectivity

If any issues are detected, alerts are sent via Telegram.

## Troubleshooting

If you encounter issues:

1. Check the logs: `tail -f logs/tgai-bennet.log`
2. Verify your API keys in the `.env` file
3. Check the service status: `systemctl status tgai-bennet`
4. Make sure your bot is properly set up in Telegram

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
