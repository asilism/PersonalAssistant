"""
LLM Client abstraction - supports multiple LLM providers
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from anthropic import AsyncAnthropic
import openai


class LLMClient(ABC):
    """Abstract LLM client interface"""

    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> str:
        """Generate a response from the LLM"""
        pass

    @abstractmethod
    async def generate_stream(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM"""
        pass


class AnthropicClient(LLMClient):
    """Anthropic Claude client"""

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncAnthropic(**kwargs)
        self.model = model

    async def generate(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> str:
        """Generate response using Anthropic API"""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages
        )
        return response.content[0].text

    async def generate_stream(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Generate streaming response using Anthropic API"""
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages
        ) as stream:
            async for text in stream.text_stream:
                yield text


class OpenAIClient(LLMClient):
    """OpenAI GPT client"""

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = openai.AsyncOpenAI(**kwargs)
        self.model = model

    async def generate(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> str:
        """Generate response using OpenAI API"""
        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

    async def generate_stream(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Generate streaming response using OpenAI API"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
            response_format={"type": "json_object"},
            stream=True
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class OpenRouterClient(LLMClient):
    """OpenRouter client (uses OpenAI-compatible API)"""

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        # Configure OpenAI client to use OpenRouter
        self.client = openai.AsyncOpenAI(
            base_url=base_url or "https://openrouter.ai/api/v1",
            api_key=api_key
        )

    async def generate(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> str:
        """Generate response using OpenRouter API"""
        # Note: response_format is intentionally NOT used for OpenRouter
        # Many OSS models (especially smaller ones) don't handle json_object mode well
        # and produce malformed responses with wrapper fields like:
        # {"assistant to=commentary code": "[actual json]"}
        # Instead, we rely on clear prompting to get proper JSON responses
        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
            extra_body={
                "provider": {
                    "order": ["DeepInfra"],
                    "quantizations": ["fp4"]
                }
            }
        )
        return response.choices[0].message.content

    async def generate_stream(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Generate streaming response using OpenRouter API"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages,
            extra_body={
                "provider": {
                    "order": ["DeepInfra"],
                    "quantizations": ["fp4"]
                }
            },
            stream=True
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


def create_llm_client(
    api_key: str,
    model: str,
    provider: str = "anthropic",
    base_url: Optional[str] = None
) -> LLMClient:
    """
    Factory function to create an LLM client based on provider
    """
    if provider == "anthropic":
        return AnthropicClient(api_key, model, base_url)
    elif provider == "openai":
        return OpenAIClient(api_key, model, base_url)
    elif provider == "openrouter":
        return OpenRouterClient(api_key, model, base_url)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
