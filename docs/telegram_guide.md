# TGAI-Bennet Telegram Bot Configuration Guide

This guide provides detailed instructions for setting up and configuring the Telegram bot for TGAI-Bennet.

## Creating a Telegram Bot

Before configuring TGAI-Bennet, you need to create a Telegram bot and get its token.

### Steps to Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Start a chat with BotFather by clicking "Start"
3. Send the command `/newbot`
4. Follow the prompts to choose a name and username for your bot
   - The name can be anything
   - The username must end with "bot" (e.g., `tgai_bennet_bot`)
5. BotFather will give you a token for your new bot
6. Copy this token - you'll need it for TGAI-Bennet configuration

Example token: `1234567890:ABCDefGhIJKlmnOPQRstUVwxYZ`

### Setting Bot Commands (Optional)

You can set the available commands for your bot to make them easier to discover:

1. Send `/mybots` to BotFather
2. Select your bot
3. Select "Edit Bot" > "Edit Commands"
4. Send the following list of commands:

```
start - Start the bot
help - Show available commands
reload_modules - Reload all modules
reload_config - Reload configuration
status - Show bot status and statistics
health - Run and display health check
stop - Gracefully stop the bot
```

## Finding Your Telegram Chat ID

The TGAI-Bennet bot needs your chat ID to send you messages. Here's how to find it:

### Method 1: Using @userinfobot

1. Open Telegram and search for `@userinfobot`
2. Start a chat with the bot by clicking "Start"
3. The bot will respond with your information, including your ID

### Method 2: Using @RawDataBot

1. Open Telegram and search for `@RawDataBot`
2. Start a chat with the bot by clicking "Start"
3. The bot will send you a message with your information
4. Look for the `"id"` field in the `"from"` section

### Method 3: Through API

If you already have your bot token, you can:

1. Send a message to your bot
2. Access this URL: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   (replace `<YOUR_TOKEN>` with your actual bot token)
3. Look for the `"id"` field in the `"from"` section

## Configuring TGAI-Bennet for Telegram

Once you have your bot token and chat ID, you need to add them to the TGAI-Bennet configuration.

### Adding Credentials to .env

Open the `.env` file in the TGAI-Bennet directory and add:

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCDefGhIJKlmnOPQRstUVwxYZ
TELEGRAM_ADMIN_CHAT_ID=123456789
```

Replace the example values with your actual bot token and chat ID.

### Configuring Telegram Settings in conf.yml

The `conf.yml` file contains additional Telegram settings:

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

These settings control how messages are formatted and sent.

## Message Formatting

TGAI-Bennet supports Markdown formatting for Telegram messages. Here are some examples:

### Markdown Mode

When `parse_mode` is set to `"Markdown"`:

- `*bold text*` → **bold text**
- `_italic text_` → *italic text*
- `` `code` `` → `code`
- ```` ```code block``` ```` → code block
- `[text](URL)` → hyperlink

Example in a module:

```python
await self.send_telegram_message(
    "*Bold Title*\n\nThis is a message with _italic_ text and `code`.",
    parse_mode="Markdown"
)
```

### HTML Mode

When `parse_mode` is set to `"HTML"`:

- `<b>bold text</b>` → **bold text**
- `<i>italic text</i>` → *italic text*
- `<code>code</code>` → `code`
- `<pre>code block</pre>` → code block
- `<a href="URL">text</a>` → hyperlink

Example in a module:

```python
await self.send_telegram_message(
    "<b>Bold Title</b>\n\nThis is a message with <i>italic</i> text and <code>code</code>.",
    parse_mode="HTML"
)
```

## Using TelegramFormatter

TGAI-Bennet includes a `TelegramFormatter` class to help format messages consistently. Modules can use the following helper method:

```python
message = self.format_telegram_response(
    "Module Alert",                  # Title
    "This is the alert content",     # Content
    status='warning',                # Status (info, success, warning, error)
    code_block="Optional code"       # Optional code block
)

await self.send_telegram_message(message)
```

The formatter handles escaping special characters and adding appropriate emojis.

## Handling Long Messages

Telegram has a 4096 character limit for messages. TGAI-Bennet automatically splits long messages into multiple parts. You can configure the maximum message length in `conf.yml`:

```yaml
telegram:
  max_message_length: 4096   # Maximum message length to send
```

## Bot Commands

TGAI-Bennet comes with several built-in commands:

- `/start` - Start the bot and get a welcome message
- `/help` - Show available commands
- `/reload_modules` - Reload all modules
- `/reload_config` - Reload configuration
- `/status` - Show bot status and statistics
- `/health` - Run and display health check
- `/stop` - Gracefully stop the bot

You can customize the command names in `conf.yml`:

```yaml
telegram:
  commands:
    reload_modules: "/reload_modules"
    reload_config: "/reload_config" 
    status: "/status"
    stop_bot: "/stop"
    health_check: "/health"
```

## Security Considerations

1. **Bot Token**: Keep your bot token secure. Anyone with your token can control your bot.
2. **Chat ID**: Restrict your bot to only respond to your chat ID to prevent unauthorized access.
3. **Public Commands**: Be careful when exposing commands that could be used maliciously.
4. **Sensitive Information**: Avoid sending sensitive information through Telegram.

## Troubleshooting

### Bot Not Responding

If your bot isn't responding:

1. Check if the bot is running: `systemctl status tgai-bennet`
2. Verify your bot token in `.env`
3. Make sure you've started a chat with your bot by sending `/start`
4. Check the logs: `tail -f logs/tgai-bennet.log`

### Formatting Issues

If message formatting isn't working:

1. Check that `parse_mode` is set correctly in `conf.yml`
2. Ensure you're using the correct syntax for the selected parse mode
3. Some special characters need to be escaped in Markdown mode

### Permission Issues

If your bot can't send messages:

1. Make sure you've started a chat with the bot
2. Check that the bot has permission to send messages (not restricted by Telegram)
3. Verify that your chat ID is correct in `.env`

## Future Improvements

TGAI-Bennet is designed to be extended to support multiple users in the future. The current version is restricted to a single admin user for simplicity and security.

Future versions may include:

1. Multiple user support with access control
2. Group chat support
3. Custom command handling for modules
4. Interactive UI elements (buttons, inline keyboards)
5. Message scheduling and queueing
