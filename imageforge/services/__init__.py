# -*- coding: utf-8 -*-
"""
ImageForge Services

Services for AI image generation with different providers.
"""

from .prompt_builder import PromptBuilder
from .base_generator import BaseImageGenerator
from .gemini_generator import GeminiGenerator
from .dalle_generator import DalleGenerator, DalleEditGenerator


def get_generator(provider: str, api_key: str) -> BaseImageGenerator:
    """
    Factory function to create the right generator.

    Args:
        provider: 'google' or 'openai'
        api_key: The API key

    Returns:
        BaseImageGenerator instance

    Raises:
        ValueError: For unknown provider
    """
    providers = {
        'google': GeminiGenerator,
        'gemini': GeminiGenerator,
        'openai': DalleGenerator,
        'dalle': DalleGenerator,
    }

    generator_class = providers.get(provider.lower())
    if not generator_class:
        raise ValueError(f"Unknown provider: {provider}. Available: {list(providers.keys())}")

    return generator_class(api_key)


__all__ = [
    'PromptBuilder',
    'BaseImageGenerator',
    'GeminiGenerator',
    'DalleGenerator',
    'DalleEditGenerator',
    'get_generator',
]
