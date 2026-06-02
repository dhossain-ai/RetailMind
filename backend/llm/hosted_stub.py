from backend.llm.base import LLMProvider


class HostedProvider(LLMProvider):
    # Swap complete() for a real API call (e.g. Anthropic) when prod credentials exist.
    def complete(self, prompt: str) -> str:
        raise NotImplementedError(
            "Hosted LLM provider is not configured. "
            "Set LLM_PROVIDER=ollama for local development."
        )
