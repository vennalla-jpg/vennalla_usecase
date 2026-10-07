"""Shared chat-model factory for the medallion agents."""

from langchain_openai import ChatOpenAI


def create_chat_model(
    provider: str,
    *,
    github_token: str | None,
    github_model: str,
    github_base_url: str,
    openai_api_key: str | None,
    openai_model: str,
    openai_base_url: str | None,
):
    """Create the configured OpenAI-compatible chat model.

    GitHub Models and OpenAI both use the ChatOpenAI adapter. The optional
    OpenAI-compatible base URL also supports compatible hosted endpoints.
    """
    if provider == "github":
        if not github_token:
            raise ValueError("GITHUB_TOKEN is required when LLM_PROVIDER=github")
        return ChatOpenAI(
            api_key=github_token,
            model=github_model,
            base_url=github_base_url,
            temperature=0,
        )

    if provider in {"openai", "openai_compatible"}:
        if not openai_api_key:
            raise ValueError(
                f"OPENAI_API_KEY is required when LLM_PROVIDER={provider}"
            )
        model_args = {
            "api_key": openai_api_key,
            "model": openai_model,
            "temperature": 0,
        }
        if openai_base_url:
            model_args["base_url"] = openai_base_url
        return ChatOpenAI(**model_args)

    raise ValueError(
        f"Unsupported LLM_PROVIDER '{provider}'. Use github, openai, or openai_compatible"
    )
