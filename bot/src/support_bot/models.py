from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Intent = Literal[
    "faq",
    "price",
    "booking",
    "complaint",
    "refund",
    "medical",
    "legal",
    "human_request",
    "off_topic",
]


class LLMReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    cited_chunk_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    intent: Intent
