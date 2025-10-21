"""
LLM Client abstraction - supports multiple LLM providers
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from anthropic import Anthropic
import openai


class LLMClient(ABC):
    """Abstract LLM client interface"""

    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> str:
        """Generate a response from the LLM"""
        pass


class AnthropicClient(LLMClient):
    """Anthropic Claude client"""

    def __init__(self, api_key: str, model: str):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    async def generate(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> str:
        """Generate response using Anthropic API"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages
        )
        return response.content[0].text


class OpenAIClient(LLMClient):
    """OpenAI GPT client"""

    def __init__(self, api_key: str, model: str):
        openai.api_key = api_key
        self.model = model

    async def generate(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> str:
        """Generate response using OpenAI API"""
        response = openai.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages
        )
        return response.choices[0].message.content


class OpenRouterClient(LLMClient):
    """OpenRouter client (uses OpenAI-compatible API)"""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        # Configure OpenAI client to use OpenRouter
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

    async def generate(self, messages: List[Dict[str, str]], max_tokens: int = 4096) -> str:
        """Generate response using OpenRouter API"""
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages
        )
        return response.choices[0].message.content


def create_llm_client(api_key: str, model: str, provider: str = "anthropic") -> LLMClient:
    """
    Factory function to create an LLM client based on provider
    """
    if provider == "anthropic":
        return AnthropicClient(api_key, model)
    elif provider == "openai":
        return OpenAIClient(api_key, model)
    elif provider == "openrouter":
        return OpenRouterClient(api_key, model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
