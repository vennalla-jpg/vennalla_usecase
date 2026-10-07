import pytest
from unittest.mock import patch

from core.llm import create_chat_model


def test_creates_github_model():
    with patch("core.llm.ChatOpenAI") as chat_openai:
        create_chat_model(
            "github",
            github_token="github-token",
            github_model="openai/gpt-4.1-mini",
            github_base_url="https://models.github.ai/inference",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            openai_base_url=None,
        )

    chat_openai.assert_called_once_with(
        api_key="github-token",
        model="openai/gpt-4.1-mini",
        base_url="https://models.github.ai/inference",
        temperature=0,
    )


def test_creates_openai_model_without_custom_base_url():
    with patch("core.llm.ChatOpenAI") as chat_openai:
        create_chat_model(
            "openai",
            github_token=None,
            github_model="openai/gpt-4.1-mini",
            github_base_url="https://models.github.ai/inference",
            openai_api_key="openai-token",
            openai_model="gpt-4o-mini",
            openai_base_url=None,
        )

    chat_openai.assert_called_once_with(
        api_key="openai-token",
        model="gpt-4o-mini",
        temperature=0,
    )


def test_requires_provider_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_chat_model(
            "openai",
            github_token=None,
            github_model="openai/gpt-4.1-mini",
            github_base_url="https://models.github.ai/inference",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            openai_base_url=None,
        )


def test_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
        create_chat_model(
            "unknown",
            github_token=None,
            github_model="openai/gpt-4.1-mini",
            github_base_url="https://models.github.ai/inference",
            openai_api_key=None,
            openai_model="gpt-4o-mini",
            openai_base_url=None,
        )
