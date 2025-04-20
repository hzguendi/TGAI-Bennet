"""
Chat history module for TGAI-Bennet.
Manages conversation context storage and retrieval using SQLite.
"""

import sqlite3
import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import aiosqlite
import tiktoken

from src.config.loader import get_config
from src.utils.logger import get_logger
from src.exceptions import DatabaseError

logger = get_logger("chat_history")

class ChatHistoryManager:
    """
    Manages chat history and conversation context using SQLite.
    Handles storing, retrieving, and managing message history across sessions.
    """
    
    def __init__(self):
        """Initialize the chat history manager."""
        self.config = get_config()
        
        # Get database configuration
        self.db_enabled = self.config.get('chat_history.enabled', True)
        self.db_path = Path(self.config.get('chat_history.db_path', 'data/chat_history.db'))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Get conversation history settings
        self.max_history_length = self.config.get('chat_history.max_history_length', 10)
        self.max_token_limit = self.config.get('chat_history.max_token_limit', 8000)
        self.token_safety_margin = self.config.get('chat_history.token_safety_margin', 200)
        
        # Message pruning settings
        self.prune_strategy = self.config.get('chat_history.prune_strategy', 'oldest_first')
        
        # Estimated token counts for different message types
        self.system_message_token_base = self.config.get('chat_history.system_message_token_base', 50)
        self.user_message_token_base = self.config.get('chat_history.user_message_token_base', 20)
        self.assistant_message_token_base = self.config.get('chat_history.assistant_message_token_base', 20)
        
        # Default token counts per character based on common models
        self.tokens_per_character = self.config.get('chat_history.tokens_per_character', 0.25)
        
        # Tokenizer cache (initialized lazily)
        self._tokenizers = {}
        
        # Connection pool (for concurrent access)
        self._connection = None
        self._lock = asyncio.Lock()
        
        logger.info(f"Chat history manager initialized with database: {self.db_path}")
    
    async def setup(self):
        """Set up the database tables and indexes."""
        if not self.db_enabled:
            logger.info("Chat history is disabled in configuration")
            return
        
        try:
            conn = await self._get_connection()
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_message_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes for faster queries
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_chat_id ON conversations(chat_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
            
            await conn.commit()
            
            logger.info("Chat history database tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to set up chat history database: {str(e)}")
            raise DatabaseError(f"Failed to set up chat history database: {str(e)}", e)
    
    async def close(self):
        """Close the database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            logger.info("Chat history database connection closed")
    
    async def _get_connection(self):
        """Get a database connection (creating one if needed)."""
        if not self.db_enabled:
            raise DatabaseError("Chat history is disabled in configuration")
        
        async with self._lock:
            if self._connection is None:
                try:
                    self._connection = await aiosqlite.connect(self.db_path)
                    # Enable foreign keys
                    await self._connection.execute("PRAGMA foreign_keys = ON")
                    logger.debug("Established new database connection")
                except Exception as e:
                    logger.error(f"Failed to connect to database: {str(e)}")
                    raise DatabaseError(f"Failed to connect to database: {str(e)}", e)
            
            return self._connection
    
    def _get_tokenizer(self, model: str):
        """Get a tokenizer for the specified model."""
        # For non-OpenAI models, use approximations based on model name keywords
        if "gpt" in model.lower() or "text-embedding" in model.lower():
            # OpenAI models
            if model not in self._tokenizers:
                try:
                    if "gpt-4" in model.lower():
                        encoding_name = "cl100k_base"
                    else:
                        encoding_name = "cl100k_base"  # Default for most modern models
                    
                    self._tokenizers[model] = tiktoken.get_encoding(encoding_name)
                    logger.debug(f"Created tokenizer for model: {model}")
                except Exception as e:
                    logger.warning(f"Failed to create tokenizer for model {model}: {str(e)}")
                    return None
            
            return self._tokenizers[model]
        
        # Return None for unsupported models
        return None
    
    async def count_tokens(self, text: str, model: str) -> int:
        """
        Count the number of tokens in the text for the given model.
        
        Args:
            text: The text to count tokens for
            model: The model to use for tokenization
        
        Returns:
            int: Estimated token count
        """
        tokenizer = self._get_tokenizer(model)
        
        if tokenizer:
            # Use the model-specific tokenizer
            return len(tokenizer.encode(text))
        else:
            # Fall back to character-based estimation
            return self._estimate_tokens_by_chars(text)
    
    def _estimate_tokens_by_chars(self, text: str) -> int:
        """
        Estimate token count based on character length.
        This is a fallback for when a proper tokenizer isn't available.
        
        Args:
            text: The text to estimate tokens for
        
        Returns:
            int: Estimated token count
        """
        if not text:
            return 0
        
        # Use token_per_character ratio from config
        estimated_tokens = int(len(text) * self.tokens_per_character)
        
        # Ensure minimum token count of 1 for non-empty text
        return max(1, estimated_tokens)
    
    async def start_conversation(self, chat_id: int, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Start a new conversation.
        
        Args:
            chat_id: Telegram chat ID
            metadata: Optional metadata for the conversation
        
        Returns:
            int: Conversation ID
        """
        if not self.db_enabled:
            logger.info("Chat history is disabled, returning dummy conversation ID")
            return -1
        
        try:
            metadata_json = json.dumps(metadata) if metadata else None
            
            conn = await self._get_connection()
            cursor = await conn.execute(
                """
                INSERT INTO conversations (chat_id, metadata)
                VALUES (?, ?)
                """,
                (chat_id, metadata_json)
            )
            await conn.commit()
            
            conversation_id = cursor.lastrowid
            logger.info(f"Started new conversation {conversation_id} for chat {chat_id}")
            
            return conversation_id
                
        except Exception as e:
            logger.error(f"Failed to start conversation: {str(e)}")
            raise DatabaseError(f"Failed to start conversation: {str(e)}", e)
    
    async def get_or_create_conversation(self, chat_id: int) -> int:
        """
        Get the current conversation ID for a chat or create a new one.
        
        Args:
            chat_id: Telegram chat ID
        
        Returns:
            int: Conversation ID
        """
        if not self.db_enabled:
            logger.info("Chat history is disabled, returning dummy conversation ID")
            return -1
        
        try:
            conn = await self._get_connection()
            # Get the most recent conversation for this chat
            cursor = await conn.execute(
                """
                SELECT id FROM conversations
                WHERE chat_id = ?
                ORDER BY last_message_time DESC
                LIMIT 1
                """,
                (chat_id,)
            )
            result = await cursor.fetchone()
            
            if result:
                conversation_id = result[0]
                logger.debug(f"Found existing conversation {conversation_id} for chat {chat_id}")
                return conversation_id
            else:
                # Start a new conversation if none exists
                return await self.start_conversation(chat_id)
                
        except Exception as e:
            logger.error(f"Failed to get or create conversation: {str(e)}")
            raise DatabaseError(f"Failed to get or create conversation: {str(e)}", e)
    
    async def add_message(
        self,
        chat_id: int,
        role: str,
        content: str,
        conversation_id: Optional[int] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add a message to the conversation history.
        
        Args:
            chat_id: Telegram chat ID
            role: Message role ('system', 'user', or 'assistant')
            content: Message content
            conversation_id: Optional conversation ID (gets current if not provided)
            model: Optional model name for token counting
            metadata: Optional metadata for the message
        
        Returns:
            int: Message ID
        """
        if not self.db_enabled:
            logger.info("Chat history is disabled, skipping message addition")
            return -1
        
        try:
            # Get conversation ID if not provided
            if conversation_id is None:
                conversation_id = await self.get_or_create_conversation(chat_id)
            
            # Count tokens if model is provided
            token_count = None
            if model:
                token_count = await self.count_tokens(content, model)
                logger.debug(f"Counted {token_count} tokens for message")
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            conn = await self._get_connection()
            # Add the message
            cursor = await conn.execute(
                """
                INSERT INTO messages (conversation_id, chat_id, role, content, token_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conversation_id, chat_id, role, content, token_count, metadata_json)
            )
            
            # Update the conversation's last message time
            await conn.execute(
                """
                UPDATE conversations 
                SET last_message_time = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,)
            )
            
            await conn.commit()
            
            message_id = cursor.lastrowid
            logger.debug(f"Added {role} message {message_id} to conversation {conversation_id}")
            
            return message_id
                
        except Exception as e:
            logger.error(f"Failed to add message: {str(e)}")
            raise DatabaseError(f"Failed to add message: {str(e)}", e)
    
    async def get_conversation_history(
        self,
        chat_id: int,
        max_messages: Optional[int] = None,
        include_system: bool = True,
        conversation_id: Optional[int] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get the conversation history for a chat.
        
        Args:
            chat_id: Telegram chat ID
            max_messages: Maximum number of messages to return
            include_system: Whether to include system messages
            conversation_id: Optional conversation ID (gets current if not provided)
            max_tokens: Maximum number of tokens to include
            model: Model name for token counting
        
        Returns:
            List[Dict]: List of messages in the conversation
        """
        if not self.db_enabled:
            logger.info("Chat history is disabled, returning empty history")
            return []
        
        try:
            # Use provided max_messages or the configured default
            max_messages = max_messages or self.max_history_length
            
            # Use provided max_tokens or the configured default
            max_tokens = max_tokens or self.max_token_limit
            
            # Apply safety margin to token limit
            max_tokens = max(0, max_tokens - self.token_safety_margin)
            
            # Get conversation ID if not provided
            if conversation_id is None:
                conversation_id = await self.get_or_create_conversation(chat_id)
            
            conn = await self._get_connection()
            # Build the query based on whether to include system messages
            query = """
                SELECT id, role, content, token_count, timestamp, metadata
                FROM messages
                WHERE conversation_id = ?
            """
            
            if not include_system:
                query += " AND role != 'system'"
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            
            cursor = await conn.execute(query, (conversation_id, max_messages))
            messages = await cursor.fetchall()
            
            # Process the messages
            result = []
            total_tokens = 0
            
            # Start with most recent messages and work backwards (messages are in reverse order)
            for msg in messages:
                msg_id, role, content, token_count, timestamp, metadata_json = msg
                
                # Parse metadata if present
                metadata = json.loads(metadata_json) if metadata_json else {}
                
                # Count tokens if not already counted and model is provided
                if token_count is None and model:
                    token_count = await self.count_tokens(content, model)
                    
                    # Update the token count in the database
                    await conn.execute(
                        "UPDATE messages SET token_count = ? WHERE id = ?",
                        (token_count, msg_id)
                    )
                    await conn.commit()
                
                # Use approximate token count if still None
                if token_count is None:
                    token_count = self._estimate_tokens_by_chars(content)
                
                # Check if adding this message would exceed the token limit
                if max_tokens > 0 and total_tokens + token_count > max_tokens:
                    # Skip this message and all older ones
                    logger.debug(f"Token limit reached ({total_tokens}/{max_tokens}), skipping older messages")
                    break
                
                # Add the message to the result
                result.append({
                    'id': msg_id,
                    'role': role,
                    'content': content,
                    'timestamp': timestamp,
                    'token_count': token_count,
                    'metadata': metadata
                })
                
                total_tokens += token_count
            
            # Reverse the list to get chronological order
            result.reverse()
            
            logger.debug(f"Retrieved {len(result)} messages ({total_tokens} tokens) for conversation {conversation_id}")
            
            return result
                
        except Exception as e:
            logger.error(f"Failed to get conversation history: {str(e)}")
            raise DatabaseError(f"Failed to get conversation history: {str(e)}", e)
    
    async def create_chat_context(
        self,
        chat_id: int,
        system_message: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        include_system: bool = True
    ) -> List[Dict[str, str]]:
        """
        Create a chat context suitable for sending to an LLM.
        
        Args:
            chat_id: Telegram chat ID
            system_message: System message to include at the beginning
            model: Optional model name for token counting
            max_tokens: Optional maximum token limit
            include_system: Whether to include system messages from history
        
        Returns:
            List[Dict]: List of message dictionaries for the LLM
        """
        if not self.db_enabled:
            # If chat history is disabled, just return the system message
            logger.info("Chat history is disabled, returning only system message")
            return [{"role": "system", "content": system_message}]
        
        try:
            # Get the conversation history
            history = await self.get_conversation_history(
                chat_id=chat_id,
                include_system=include_system,
                max_tokens=max_tokens,
                model=model
            )
            
            # Count system message tokens
            system_message_tokens = 0
            if model:
                system_message_tokens = await self.count_tokens(system_message, model)
            else:
                system_message_tokens = self._estimate_tokens_by_chars(system_message)
            
            # Create the LLM context
            context = [{"role": "system", "content": system_message}]
            
            # Add history messages in the format expected by LLMs
            for msg in history:
                context.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Calculate total tokens
            total_tokens = system_message_tokens + sum(msg.get('token_count', 0) for msg in history)
            logger.debug(f"Created chat context with {len(context)} messages ({total_tokens} tokens)")
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to create chat context: {str(e)}")
            raise DatabaseError(f"Failed to create chat context: {str(e)}", e)
    
    async def clear_chat_history(self, chat_id: int, conversation_id: Optional[int] = None):
        """
        Clear the chat history for a conversation.
        
        Args:
            chat_id: Telegram chat ID
            conversation_id: Optional conversation ID (clears all for chat if not provided)
        """
        if not self.db_enabled:
            logger.info("Chat history is disabled, nothing to clear")
            return
        
        try:
            conn = await self._get_connection()
            if conversation_id:
                # Clear messages for the specific conversation
                await conn.execute(
                    "DELETE FROM messages WHERE conversation_id = ? AND chat_id = ?",
                    (conversation_id, chat_id)
                )
                logger.info(f"Cleared messages for conversation {conversation_id}")
            else:
                # Get all conversation IDs for this chat
                cursor = await conn.execute(
                    "SELECT id FROM conversations WHERE chat_id = ?",
                    (chat_id,)
                )
                conversations = await cursor.fetchall()
                
                # Clear messages for all conversations
                for conversation in conversations:
                    await conn.execute(
                        "DELETE FROM messages WHERE conversation_id = ?",
                        (conversation[0],)
                    )
                
                logger.info(f"Cleared messages for all conversations of chat {chat_id}")
            
            await conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to clear chat history: {str(e)}")
            raise DatabaseError(f"Failed to clear chat history: {str(e)}", e)
    
    async def get_system_message(
        self, 
        module_name: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> str:
        """
        Get the system message to use for conversations.
        
        Args:
            module_name: Optional module name for module-specific instructions
            model_name: Optional model name to include in the system message
        
        Returns:
            str: System message for the LLM
        """
        config_key = 'chat_history.system_message'
        if module_name:
            # Try module-specific system message first
            module_config_key = f'modules.{module_name}.system_message'
            system_message = self.config.get(module_config_key)
            if system_message:
                return system_message
        
        # Fall back to default system message
        system_message = self.config.get(config_key, "")
        
        if not system_message:
            # Build a default system message if none is configured
            app_name = self.config.get('app.name', 'TGAI-Bennet')
            system_message = (
                f"You are {app_name}, a helpful AI assistant in a Telegram chat. "
                f"Be concise but informative."
            )
            
            if module_name:
                system_message += f"\nYou are currently responding to a message from the {module_name} module."
            
            if model_name:
                system_message += f"\nYou are running on the {model_name} model."
        
        return system_message
