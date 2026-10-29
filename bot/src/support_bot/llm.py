import json
import re
from importlib import resources
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import ValidationError

from .models import LLMReply
from .prompt import neutralise
from .text import fold

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_CUSTOMER = re.compile(r"<customer_message>\n(.*)\n</customer_message>", re.DOTALL)


class LLMError(Exception):
    pass


class LLM(Protocol):
    async def complete(self, messages: list[dict]) -> tuple[LLMReply, int]: ...


class OpenAICompatLLM:
    """Any OpenAI-compatible /chat/completions endpoint; defaults target a local Ollama."""

    def __init__(self, base_url: str, model: str, api_key: str = "ollama", timeout: float = 120, reasoning_effort: str = "none", uds: str | None = None):
        self.model, self.reasoning_effort = model, reasoning_effort
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=httpx.AsyncHTTPTransport(uds=uds) if uds else None,
        )

    async def complete(self, messages: list[dict]) -> tuple[LLMReply, int]:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "support_reply", "strict": True, "schema": LLMReply.model_json_schema()},
            },
        }
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        try:
            r = await self.client.post("/chat/completions", json=body)
            r.raise_for_status()
            data = r.json()
            content = _THINK.sub("", data["choices"][0]["message"]["content"]).strip()
            reply = LLMReply.model_validate_json(content)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise LLMError(type(exc).__name__) from exc
        return reply, int((data.get("usage") or {}).get("total_tokens") or 0)


class FakeLLM:
    """Replays recorded model outputs keyed by the customer message, for tests, CI and offline demos."""

    UNKNOWN = LLMReply(answer="", cited_chunk_ids=[], confidence=0.1, intent="faq")

    def __init__(self, recordings: dict[str, LLMReply]):
        self.recordings = {fold(neutralise(k)).strip(): v for k, v in recordings.items()}

    @classmethod
    def from_file(cls, path: str | Path) -> "FakeLLM":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls({item["message"]: LLMReply.model_validate(item["reply"]) for item in raw})

    @classmethod
    def default(cls) -> "FakeLLM":
        with resources.as_file(resources.files(__package__) / "recordings.json") as path:
            return cls.from_file(path)

    async def complete(self, messages: list[dict]) -> tuple[LLMReply, int]:
        match = _CUSTOMER.search(messages[-1]["content"])
        key = fold(match.group(1)).strip() if match else ""
        return self.recordings.get(key, self.UNKNOWN), 0
