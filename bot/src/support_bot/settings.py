import os

from pydantic import BaseModel


class Settings(BaseModel):
    chatwoot_url: str = "http://chatwoot-rails:3000"
    chatwoot_bot_token: str = ""
    chatwoot_team_id: int | None = None
    webhook_secret: str = ""
    webhook_hmac_secret: str = ""
    llm_base_url: str = "http://host.docker.internal:11434/v1"
    llm_model: str = "qwen3:14b"
    llm_api_key: str = "ollama"
    llm_uds: str = ""
    llm_reasoning_effort: str = "none"
    llm_timeout: float = 120
    fake_llm: bool = False
    knowledge_dir: str = "/app/knowledge"
    usage_db: str = "/data/usage.sqlite3"
    max_calls_per_day: int = 200
    max_tokens_per_day: int = 400_000
    min_confidence: float = 0.6
    top_k: int = 4
    timezone: str = "Europe/Madrid"

    @classmethod
    def from_env(cls, **overrides) -> "Settings":
        values = {}
        for name in cls.model_fields:
            raw = os.environ.get(f"BOT_{name.upper()}")
            if raw not in (None, ""):
                values[name] = raw
        return cls(**(values | overrides))
