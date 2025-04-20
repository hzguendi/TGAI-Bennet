# TGAI-Bennet Configuration Guide

This guide provides detailed information about configuring the TGAI-Bennet application.

## Configuration Files Overview

TGAI-Bennet uses two main configuration files:

1. **`.env`** - Contains sensitive information such as API keys and tokens
2. **`conf.yml`** - Contains all other configuration settings

## Environment Variables (`.env`)

The `.env` file should be created based on the provided `.env.sample`. This file contains sensitive information and should never be committed to version control.

### Required Variables

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_ADMIN_CHAT_ID=your_telegram_chat_id_here

# LLM Provider API Keys (at least one required)
OPENAI_API_KEY=your_openai_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Ollama Configuration (for local deployment)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama2
```

### Optional Variables

```bash
# Service Configuration
SERVICE_NAME=tgai-bennet
LOG_LEVEL=INFO
MODULE_CHECK_INTERVAL=30  # Seconds between module checks
HEALTH_CHECK_INTERVAL=300  # Seconds between health checks

# Advanced Configuration
MAX_RETRIES=3
TIMEOUT_SECONDS=30
RATE_LIMIT_REQUESTS=20
RATE_LIMIT_WINDOW=60  # Seconds
```

## Application Configuration (`conf.yml`)

The `conf.yml` file is organized into sections, each controlling a different aspect of the application.

### App Section

Basic application information:

```yaml
app:
  name: "TGAI-Bennet"
  version: "1.0.0"
  debug: false
  timezone: "UTC"
```

### LLM Section

Configuration for LLM providers:

```yaml
llm:
  default_provider: "openai"  # Options: openai, openrouter, deepseek, ollama
  default_model: "gpt-4"      # Default model to use
  temperature: 0.7            # LLM temperature setting (0-1)
  max_tokens: 2000            # Maximum tokens per response
  
  providers:
    openai:
      base_url: "https://api.openai.com/v1"
      models:
        - "gpt-3.5-turbo"
        - "gpt-4"
        - "gpt-4-turbo-preview"
    
    # Other providers follow same structure
```

### Telegram Section

Telegram bot configuration:

```yaml
telegram:
  parse_mode: "Markdown"      # Options: Markdown, HTML, None
  disable_web_page_preview: true
  disable_notification: false
  reply_timeout: 30          # Seconds to wait for bot replies
  max_message_length: 4096   # Maximum message length to send
  
  commands:
    # Admin commands
    reload_modules: "/reload_modules"
    reload_config: "/reload_config" 
    status: "/status"
    stop_bot: "/stop"
    health_check: "/health"
```

### Modules Section

Module system configuration:

```yaml
modules:
  enabled: true
  directory: "src/modules"
  hot_reload: true          # Auto-detect and reload modules
  scan_interval: 60         # Seconds between module directory scans
  
  state_storage:
    enabled: true
    type: "json"            # Options: json, sqlite, redis
    path: "data/module_states.json"
  
  error_handling:
    max_retries: 3
    retry_delay: 5          # Seconds between retries
    notify_on_error: true   # Send Telegram message on module errors
```

### Logging Section

Logging system configuration:

```yaml
logging:
  level: "INFO"             # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
  
  file:
    enabled: true
    path: "logs/tgai-bennet.log"
    rotation: "1 day"       # Options: X day(s), X hour(s), X MB
    retention: "30 days"    # How long to keep old logs
    
  module_logging:
    enabled: true
    separate_files: true    # One log file per module
    path_template: "logs/modules/{module_name}.log"
```

### Health Section

Health monitoring configuration:

```yaml
health:
  enabled: true
  interval: 300             # Seconds between health checks
  
  metrics:
    memory_threshold: 500   # MB, alert if exceeded
    cpu_threshold: 80       # %, alert if exceeded
    disk_threshold: 90      # %, alert if exceeded
  
  notifications:
    telegram_errors: true   # Send errors to Telegram
    log_errors: true        # Log health errors
    
  restarts:
    auto_restart_on_failure: true
    max_restart_attempts: 3
    restart_delay: 30       # Seconds between restart attempts
```

### Module Defaults Section

Default configuration for modules:

```yaml
module_defaults:
  time_trigger:
    type: "interval"        # Options: interval, cron
    interval: 300           # Default interval in seconds
    
  event_trigger:
    type: "webhook"         # Options: webhook, file_change, socket
    retry_on_failure: true
    
  api_settings:
    timeout: 30            # API call timeout in seconds
    max_retries: 3
    backoff_factor: 1.5    # Multiplier for exponential backoff
```

## Configuration Validation

TGAI-Bennet includes a robust configuration validation system that ensures all settings are correct before startup. If any configuration issues are detected, the application will log detailed error messages and exit.

## Hot Reloading Configuration

You can reload the configuration without restarting the application by using the `/reload_config` command in Telegram. This will reload the `conf.yml` file and apply the changes immediately.

## Configuration Best Practices

1. **Security**: Keep your `.env` file secure and never share your API keys.
2. **Backups**: Regularly back up your configuration files.
3. **Comments**: Add comments to your `conf.yml` file to document custom settings.
4. **Validation**: After making changes, validate your configuration by starting the application or using the reload command.
5. **Environment Separation**: Consider maintaining separate configuration files for development and production environments.

## Module-Specific Configuration

You can add configuration for specific modules in the `conf.yml` file:

```yaml
modules:
  # Other module settings...
  
  # Module-specific settings
  WeatherAlertModule:
    api_key: "your_weather_api_key"
    location: "London,UK"
    alert_threshold: 50
  
  BTCPriceMonitorModule:
    price_threshold_low: 20000
    price_threshold_high: 45000
    percent_change_alert: 5
```

Modules can access their specific configuration using the `get_config` method:

```python
location = self.get_config('location', 'London,UK')  # Default to London if not specified
```
