"""Test utilities for real LLM testing."""

import os
import pytest
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from new_backend_ruminate.infrastructure.llm.openai_llm import OpenAILLM


class LLMTestHelper:
    """Helper class for easy LLM testing with real OpenAI calls."""
    
    @staticmethod
    def load_test_env() -> None:
        """Load environment variables from the correct .env file."""
        load_dotenv("/Users/jaidenreddy/Documents/projects/all_dreams/backend_dream/.env", override=True)
    
    @staticmethod
    def check_api_key() -> Optional[str]:
        """Check if OpenAI API key is available and return it, or None if not."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        if not api_key.startswith("sk-proj-zrtT"):
            return None
        return api_key
    
    @staticmethod
    def skip_if_no_api_key() -> str:
        """Skip test if API key is not available, otherwise return the key."""
        api_key = LLMTestHelper.check_api_key()
        if not api_key:
            pytest.skip("OPENAI_API_KEY not available or incorrect format")
        return api_key
    
    @staticmethod
    def create_test_llm(model: str = "gpt-5-mini") -> OpenAILLM:
        """Create a test LLM instance with the correct API key."""
        api_key = LLMTestHelper.skip_if_no_api_key()
        return OpenAILLM(model=model, api_key=api_key)
    
    @staticmethod
    def create_all_llm_variants() -> Dict[str, OpenAILLM]:
        """Create all common LLM variants for testing."""
        api_key = LLMTestHelper.skip_if_no_api_key()
        return {
            "mini": OpenAILLM(model="gpt-5-mini", api_key=api_key),
            "standard": OpenAILLM(model="gpt-5", api_key=api_key),
            "turbo": OpenAILLM(model="gpt-5-nano", api_key=api_key),
        }


# Load environment on import
LLMTestHelper.load_test_env()


# Convenient pytest fixtures
@pytest.fixture
def test_llm():
    """Pytest fixture for a basic test LLM."""
    return LLMTestHelper.create_test_llm()


@pytest.fixture
def test_llm_fast():
    """Pytest fixture for fastest/cheapest LLM."""
    return LLMTestHelper.create_test_llm("gpt-5-mini")


@pytest.fixture
def test_llm_smart():
    """Pytest fixture for most capable LLM."""
    return LLMTestHelper.create_test_llm("gpt-5")


@pytest.fixture
def all_test_llms():
    """Pytest fixture that provides all LLM variants."""
    return LLMTestHelper.create_all_llm_variants()


# Pytest markers for easy test categorization
def requires_llm(func):
    """Decorator that marks a test as requiring LLM and skips if not available."""
    return pytest.mark.skipif(
        not LLMTestHelper.check_api_key(),
        reason="OPENAI_API_KEY not available or incorrect format"
    )(func)


def llm_integration_test(func):
    """Decorator for LLM integration tests - adds marker and timeout."""
    return pytest.mark.asyncio(pytest.mark.timeout(30)(requires_llm(func)))


# Quick test helpers
async def quick_llm_test(prompt: str, model: str = "gpt-5-mini") -> str:
    """Quick function to test an LLM with a simple prompt."""
    llm = LLMTestHelper.create_test_llm(model)
    messages = [{"role": "user", "content": prompt}]
    return await llm.generate_response(messages)


async def quick_structured_llm_test(
    prompt: str, 
    json_schema: Dict[str, Any], 
    model: str = "gpt-5-mini"
) -> Dict[str, Any]:
    """Quick function to test structured LLM output."""
    llm = LLMTestHelper.create_test_llm(model)
    messages = [{"role": "user", "content": prompt}]
    return await llm.generate_structured_response(
        messages=messages,
        response_format={"type": "json_object"},
        json_schema=json_schema
    )