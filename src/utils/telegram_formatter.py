"""
Telegram message formatter for creating nicely formatted messages with Markdown support.
"""

import re
import textwrap
from typing import List, Dict, Any, Optional, Union
from datetime import datetime


class TelegramFormatter:
    """
    Class for formatting messages for Telegram with Markdown support.
    Handles special characters, formatting, and message length limits.
    """
    
    # Characters that need to be escaped in Markdown mode
    MARKDOWN_ESCAPE_CHARS = {
        '*': '\*',
        '_': '\_', 
        '`': '\`',
        '[': '\[',
        ']': '\]',
        '(': '\(',
        ')': '\)',
        '~': '\~',
        '>': '\>',
        '#': '\#',
        '+': '\+',
        '-': '\-',
        '=': '\=',
        '|': '\|',
        '{': '\{', 
        '}': '\}',
        '.': '\.',
        '!': '\!'
    }
    
    # Characters that ACTUALLY need to be escaped in Markdown to avoid breaking formatting
    # This excludes punctuation like periods and exclamation marks for better readability
    MINIMAL_ESCAPE_CHARS = {
        '*': '\*',
        '_': '\_', 
        '`': '\`',
        '[': '\[',
        ']': '\]',
        '(': '\(',
        ')': '\)',
        '~': '\~',
        '#': '\#',
        '<': '\<',
        '>': '\>'
    }
    
    # Maximum message length for Telegram
    MAX_MESSAGE_LENGTH = 4096
    
    # Common emojis for status messages
    EMOJIS = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
        'alert': '🚨',
        'time': '⏰',
        'module': '🧩',
        'chat': '💬',
        'bot': '🤖',
        'metrics': '📊',
        'health': '💚',
        'update': '🔄',
        'config': '⚙️',
        'save': '💾',
        'fire': '🔥',
        'money': '💰',
        'weather': '🌤️',
        'cloud': '☁️',
        'rain': '🌧️',
        'sun': '☀️',
        'temperature': '🌡️'
    }
    
    @classmethod
    def escape_markdown(cls, text: str) -> str:
        """Escape special characters for Telegram Markdown."""
        if not text:
            return ""
        
        # First escape all special characters
        for char, escaped in cls.MARKDOWN_ESCAPE_CHARS.items():
            text = text.replace(char, escaped)
        
        return text
    
    @classmethod
    def minimal_escape_markdown(cls, text: str) -> str:
        """Escape only the essential Markdown characters that break formatting.
        
        This version doesn't escape punctuation like periods and exclamation marks,
        resulting in more readable messages.
        """
        if not text:
            return ""
        
        # Apply selective escaping - only escape characters that actually break Markdown
        for char, escaped in cls.MINIMAL_ESCAPE_CHARS.items():
            text = text.replace(char, escaped)
            
        return text
    
    @classmethod
    def bold(cls, text: str) -> str:
        """Make text bold."""
        return f"*{cls.minimal_escape_markdown(text)}*"
    
    @classmethod
    def italic(cls, text: str) -> str:
        """Make text italic."""
        return f"_{cls.minimal_escape_markdown(text)}_"
    
    @classmethod
    def code(cls, text: str) -> str:
        """Format text as inline code."""
        return f"`{text}`"
    
    @classmethod
    def code_block(cls, text: str, language: str = "") -> str:
        """Format text as a code block with optional language."""
        return f"```{language}\n{text}\n```"
    
    @classmethod
    def link(cls, text: str, url: str) -> str:
        """Create a markdown link."""
        return f"[{cls.minimal_escape_markdown(text)}]({url})"
    
    @classmethod
    def header(cls, text: str, level: int = 1) -> str:
        """Create a header (level 1-3 for bold, level 4-6 for regular)."""
        if level <= 3:
            return cls.bold(text)
        else:
            return cls.minimal_escape_markdown(text)
    
    @classmethod
    def list_item(cls, text: str, level: int = 0) -> str:
        """Create a list item with indentation."""
        indent = "  " * level
        return f"{indent}• {cls.minimal_escape_markdown(text)}"
    
    @classmethod
    def numbered_list_item(cls, number: int, text: str, level: int = 0) -> str:
        """Create a numbered list item with indentation."""
        indent = "  " * level
        return f"{indent}{number}. {cls.minimal_escape_markdown(text)}"
    
    @classmethod
    def format_datetime(cls, dt: datetime) -> str:
        """Format a datetime object for display."""
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    @classmethod
    def status_message(cls, title: str, content: str, status: str = 'info') -> str:
        """
        Create a formatted status message with an emoji.
        Status can be: success, error, warning, info, alert
        
        Uses minimal escaping for readable messages.
        """
        emoji = cls.EMOJIS.get(status, cls.EMOJIS['info'])
        header = f"*{emoji} {cls.minimal_escape_markdown(title)}*"
        
        if isinstance(content, list):
            content_lines = [cls.list_item(item) for item in content]
            content_text = '\n'.join(content_lines)
        else:
            # Use minimal escaping for better readability
            content_text = cls.minimal_escape_markdown(content)
        
        return f"{header}\n\n{content_text}"
    
    @classmethod
    def module_status(cls, module_name: str, status: str, details: Optional[Dict[str, Any]] = None) -> str:
        """Create a formatted module status message."""
        emoji = cls.EMOJIS['module']
        header = cls.bold(f"{emoji} Module: {module_name}")
        
        status_emoji = cls.EMOJIS.get(status.lower(), cls.EMOJIS['info'])
        status_line = f"{status_emoji} Status: {cls.minimal_escape_markdown(status)}"
        
        message_parts = [header, status_line]
        
        if details:
            for key, value in details.items():
                formatted_key = cls.minimal_escape_markdown(key.replace('_', ' ').title())
                formatted_value = cls.minimal_escape_markdown(str(value))
                message_parts.append(f"• {formatted_key}: {formatted_value}")
        
        return '\n'.join(message_parts)
    
    @classmethod
    def health_check_message(cls, metrics: Dict[str, Any]) -> str:
        """Create a formatted health check message."""
        header = cls.bold(f"{cls.EMOJIS['health']} Health Check")
        
        message_parts = [header, ""]
        
        for metric, value in metrics.items():
            if isinstance(value, dict):
                # Nested metrics
                message_parts.append(cls.bold(f"{metric.replace('_', ' ').title()}:"))
                for sub_metric, sub_value in value.items():
                    icon = cls._get_metric_icon(sub_metric, sub_value)
                    message_parts.append(f"  {icon} {sub_metric}: {sub_value}")
            else:
                icon = cls._get_metric_icon(metric, value)
                message_parts.append(f"{icon} {metric}: {value}")
        
        return '\n'.join(message_parts)
    
    @classmethod
    def _get_metric_icon(cls, metric: str, value: Any) -> str:
        """Get an appropriate icon based on metric type and value."""
        if 'error' in metric.lower():
            return cls.EMOJIS['error'] if value else cls.EMOJIS['success']
        elif 'warning' in metric.lower():
            return cls.EMOJIS['warning'] if value else cls.EMOJIS['success']
        elif 'cpu' in metric.lower() or 'memory' in metric.lower() or 'disk' in metric.lower():
            return cls.EMOJIS['metrics']
        elif 'time' in metric.lower():
            return cls.EMOJIS['time']
        elif 'update' in metric.lower():
            return cls.EMOJIS['update']
        else:
            return cls.EMOJIS['info']
    
    @classmethod
    def error_message(cls, title: str, error: Union[str, Exception], details: Optional[Dict[str, Any]] = None) -> str:
        """Create a formatted error message."""
        header = cls.bold(f"{cls.EMOJIS['error']} Error: {title}")
        
        if isinstance(error, Exception):
            error_text = f"{type(error).__name__}: {str(error)}"
        else:
            error_text = str(error)
        
        message_parts = [header, "", cls.code_block(error_text)]
        
        if details:
            message_parts.append("")
            message_parts.append(cls.bold("Details:"))
            for key, value in details.items():
                message_parts.append(f"• {key}: {cls.minimal_escape_markdown(str(value))}")
        
        return '\n'.join(message_parts)
    
    @classmethod
    def alert_message(cls, title: str, content: str, severity: str = 'warning') -> str:
        """Create a formatted alert message."""
        severity_icons = {
            'info': cls.EMOJIS['info'],
            'warning': cls.EMOJIS['warning'],
            'error': cls.EMOJIS['error'],
            'critical': cls.EMOJIS['alert'],
            'fire': cls.EMOJIS['fire']
        }
        
        icon = severity_icons.get(severity.lower(), cls.EMOJIS['alert'])
        header = cls.bold(f"{icon} Alert: {title}")
        
        return f"{header}\n\n{cls.minimal_escape_markdown(content)}"
    
    @classmethod
    def format_key_value_pairs(cls, data: Dict[str, Any], indent: int = 0) -> str:
        """Format a dictionary of key-value pairs."""
        lines = []
        indent_str = "  " * indent
        
        for key, value in data.items():
            formatted_key = cls.minimal_escape_markdown(key.replace('_', ' ').title())
            
            if isinstance(value, dict):
                lines.append(f"{indent_str}{formatted_key}:")
                lines.append(cls.format_key_value_pairs(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{indent_str}{formatted_key}:")
                for item in value:
                    lines.append(f"{indent_str}  • {cls.minimal_escape_markdown(str(item))}")
            else:
                lines.append(f"{indent_str}{formatted_key}: {cls.minimal_escape_markdown(str(value))}")
        
        return '\n'.join(lines)
    
    @classmethod
    def split_long_message(cls, message: str) -> List[str]:
        """Split a long message into multiple messages that fit Telegram's limits."""
        if len(message) <= cls.MAX_MESSAGE_LENGTH:
            return [message]
        
        # Try to split on newlines first
        lines = message.split('\n')
        messages = []
        current_message = ""
        
        for line in lines:
            if len(current_message) + len(line) + 1 <= cls.MAX_MESSAGE_LENGTH:
                current_message += line + '\n'
            else:
                messages.append(current_message.strip())
                current_message = line + '\n'
        
        if current_message:
            messages.append(current_message.strip())
        
        return messages
    
    @classmethod
    def table(cls, headers: List[str], rows: List[List[str]], max_col_width: int = 20) -> str:
        """Create a simple text table using monospace font."""
        # Escape all cell content
        headers = [cls.minimal_escape_markdown(str(h)) for h in headers]
        rows = [[cls.minimal_escape_markdown(str(cell)) for cell in row] for row in rows]
        
        # Calculate column widths
        col_widths = [min(max_col_width, max(len(h), max(len(str(row[i])) 
                     for row in rows if i < len(row)))) for i, h in enumerate(headers)]
        
        # Create table lines
        lines = []
        
        # Header
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        lines.append(f"```\n{header_line}")
        
        # Separator
        separator = "-+-".join("-" * w for w in col_widths)
        lines.append(separator)
        
        # Rows
        for row in rows:
            # Handle cases where row might have fewer columns than headers
            padded_row = row + [''] * (len(headers) - len(row))
            row_line = " | ".join(str(cell)[:w].ljust(w) for cell, w in zip(padded_row, col_widths))
            lines.append(row_line)
        
        lines.append("```")
        
        return '\n'.join(lines)
