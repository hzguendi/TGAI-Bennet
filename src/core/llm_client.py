"""
LLM client module for TGAI-Bennet.
Provides a unified interface for connecting to different LLM providers.
"""

import os
import json
import time
import asyncio
import aiohttp
from typing import Dict, List, Optional, Union, Any, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

import requests
import openai

from src.exceptions import LLMProviderError, RateLimitError
from src.config.loader import get_config
from src.utils.logger import get_logger


logger = get_logger("llm_client")


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


@dataclass
class LLMResponse:
    """Standard response format from LLM providers."""
    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMClient:
    """
    Unified client for multiple LLM providers.
    Handles authentication, retries, rate limiting, and provides a consistent interface.
    """
    
    def __init__(self, provider: Optional[str] = None):
        """
        Initialize the LLM client.
        
        Args:
            provider: Optional provider name. If not provided, uses config default.
        """
        self.config = get_config()
        self.provider = provider or self.config.get('llm.default_provider', 'openai')
        self.provider_config = self.config.get(f'llm.providers.{self.provider}', {})
        
        # Validate provider
        if self.provider not in [p.value for p in LLMProvider]:
            raise LLMProviderError(f"Unsupported provider: {self.provider}")
        
        # Set up API client
        self._setup_client()
        
        # Rate limiting
        self.request_count = 0
        self.last_request_time = 0
        self.rate_limit_window = self.config.get('RATE_LIMIT_WINDOW', 60)
        self.rate_limit_requests = self.config.get('RATE_LIMIT_REQUESTS', 20)
        
        logger.info(f"LLM client initialized with provider: {self.provider}")
    
    def _setup_client(self):
        """Set up the appropriate client based on provider."""
        self.api_key = os.getenv(f"{self.provider.upper()}_API_KEY")
        self.base_url = self.provider_config.get('base_url')
        
        if not self.api_key and self.provider != LLMProvider.OLLAMA.value:
            raise LLMProviderError(f"API key not found for provider: {self.provider}")
        
        if self.provider == LLMProvider.OPENAI.value:
            # Use global openai configuration for v0.x API
            openai.api_key = self.api_key
            # No need to explicitly create a client in v0.x
            self.sync_client = None
            self.async_client = None
        elif self.provider in [LLMProvider.OPENROUTER.value, LLMProvider.DEEPSEEK.value]:
            # Use global openai configuration for v0.x API but customize base URL
            openai.api_key = self.api_key
            openai.api_base = self.base_url
            self.sync_client = None
            self.async_client = None
        elif self.provider == LLMProvider.OLLAMA.value:
            # For Ollama, we'll use direct HTTP requests
            self.sync_client = None
            self.async_client = None
            self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        current_time = time.time()
        
        # Reset counter if window has passed
        if current_time - self.last_request_time > self.rate_limit_window:
            self.request_count = 0
            self.last_request_time = current_time
        
        # Check if we're over the limit
        if self.request_count >= self.rate_limit_requests:
            wait_time = self.rate_limit_window - (current_time - self.last_request_time)
            if wait_time > 0:
                logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds.")
                await asyncio.sleep(wait_time)
                self.request_count = 0
                self.last_request_time = time.time()
        
        self.request_count += 1
    
    async def _retry_with_backoff(
        self, 
        func, 
        max_retries: Optional[int] = None, 
        backoff_factor: float = 1.5
    ):
        """Execute a function with exponential backoff retry."""
        max_retries = max_retries or self.config.get('module_defaults.api_settings.max_retries', 3)
        delay = 1.0
        
        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                
                if isinstance(e, RateLimitError):
                    # For rate limit errors, use a longer delay
                    delay = 60
                
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """
        Send a chat completion request to the LLM provider.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model to use (provider-specific)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            stream: Whether to stream the response
            **kwargs: Additional provider-specific parameters
        
        Returns:
            LLMResponse object or async generator yielding tokens if streaming
        """
        await self._check_rate_limit()
        
        # Use configured defaults if not provided
        model = model or self.config.get('llm.default_model')
        temperature = temperature or self.config.get('llm.temperature', 0.7)
        max_tokens = max_tokens or self.config.get('llm.max_tokens', 2000)
        
        if self.provider == LLMProvider.OLLAMA.value:
            # Special handling for Ollama
            return await self._ollama_chat(messages, model, temperature, max_tokens, stream)
        
        async def request_func():
            # Use openai v0.x API with asyncio
            loop = asyncio.get_event_loop()
            
            # Create common parameters
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": stream,
                **kwargs
            }
            
            # Use loop.run_in_executor to make the synchronous API call asynchronous
            if stream:
                response = await loop.run_in_executor(
                    None, 
                    lambda: openai.ChatCompletion.create(**params)
                )
                return self._process_stream_v0(response)
            else:
                response = await loop.run_in_executor(
                    None, 
                    lambda: openai.ChatCompletion.create(**params)
                )
                return self._process_response_v0(response)
        
        try:
            result = await self._retry_with_backoff(request_func)
            return result
        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}")
            raise LLMProviderError(f"Chat completion failed: {str(e)}", e)
    
    async def _ollama_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Handle chat requests for Ollama."""
        url = f"{self.ollama_host}/api/chat"
        
        # Transform messages to Ollama format
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        payload = {
            "model": model or self.config.get('OLLAMA_MODEL', 'llama2'),
            "messages": ollama_messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise LLMProviderError(f"Ollama request failed: {error_text}")
                
                if stream:
                    return self._ollama_stream_generator(response)
                else:
                    data = await response.json()
                    return LLMResponse(
                        content=data.get('message', {}).get('content', ''),
                        model=model,
                        provider=self.provider,
                        metadata=data
                    )
    
    async def _ollama_stream_generator(self, response):
        """Generate streamed responses from Ollama."""
        async for line in response.content:
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    if 'message' in data and 'content' in data['message']:
                        yield data['message']['content']
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode Ollama stream line: {line}")
    
    def _process_response_v0(self, response) -> LLMResponse:
        """Process a non-streaming response from v0 API into standardized format."""
        choice = response['choices'][0]
        
        return LLMResponse(
            content=choice['message']['content'],
            model=response['model'],
            provider=self.provider,
            tokens_used=response['usage']['total_tokens'] if 'usage' in response else None,
            finish_reason=choice['finish_reason'],
            metadata={
                'id': response['id'],
                'created': response['created'],
                'system_fingerprint': response.get('system_fingerprint')
            }
        )
    
    async def _process_stream_v0(self, response):
        """Process a streaming response from v0 API, yielding tokens."""
        for chunk in response:
            if 'choices' in chunk and len(chunk['choices']) > 0:
                delta = chunk['choices'][0].get('delta', {})
                if 'content' in delta and delta['content']:
                    yield delta['content']
    
    def sync_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Synchronous version of chat_completion.
        Note: Streaming is not supported in sync mode.
        """
        # Check rate limit
        current_time = time.time()
        if current_time - self.last_request_time < self.rate_limit_window:
            if self.request_count >= self.rate_limit_requests:
                wait_time = self.rate_limit_window - (current_time - self.last_request_time)
                if wait_time > 0:
                    logger.warning(f"Rate limit reached. Waiting {wait_time:.2f} seconds.")
                    time.sleep(wait_time)
                    self.request_count = 0
                    self.last_request_time = time.time()
        else:
            self.request_count = 0
            self.last_request_time = current_time
        
        self.request_count += 1
        
        # Use configured defaults if not provided
        model = model or self.config.get('llm.default_model')
        temperature = temperature or self.config.get('llm.temperature', 0.7)
        max_tokens = max_tokens or self.config.get('llm.max_tokens', 2000)
        
        if self.provider == LLMProvider.OLLAMA.value:
            return self._sync_ollama_chat(messages, model, temperature, max_tokens)
        
        try:
            # Use openai v0.x synchronous API
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            return self._process_response_v0(response)
        except Exception as e:
            logger.error(f"Error in synchronous chat completion: {str(e)}")
            raise LLMProviderError(f"Synchronous chat completion failed: {str(e)}", e)
    
    def _sync_ollama_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int
    ) -> LLMResponse:
        """Handle synchronous chat requests for Ollama."""
        url = f"{self.ollama_host}/api/chat"
        
        # Transform messages to Ollama format
        ollama_messages = []
        for msg in messages:
            ollama_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        payload = {
            "model": model or self.config.get('OLLAMA_MODEL', 'llama2'),
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code != 200:
            raise LLMProviderError(f"Ollama request failed: {response.text}")
        
        data = response.json()
        return LLMResponse(
            content=data.get('message', {}).get('content', ''),
            model=model,
            provider=self.provider,
            metadata=data
        )
    
    def supports_streaming(self) -> bool:
        """Check if the current provider supports streaming responses."""
        # All providers support streaming
        return True
    
    def available_models(self) -> List[str]:
        """Get list of available models for the current provider."""
        return self.provider_config.get('models', [])
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics about the client's performance."""
        return {
            'provider': self.provider,
            'requests_count': self.request_count,
            'rate_limit_window': self.rate_limit_window,
            'rate_limit_requests': self.rate_limit_requests,
            'current_window_requests': self.request_count,
            'last_request_time': self.last_request_time
        }
