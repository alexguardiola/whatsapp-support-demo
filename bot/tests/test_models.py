import pytest
from pydantic import ValidationError

from support_bot.models import LLMReply


def test_valid_reply_parses():
    r = LLMReply.model_validate_json(
        '{"answer":"Hola","cited_chunk_ids":["a#b"],"confidence":0.9,"intent":"faq"}'
    )
    assert r.intent == "faq"


@pytest.mark.parametrize(
    "raw",
    [
        '{"answer":"x","cited_chunk_ids":[],"confidence":1.5,"intent":"faq"}',
        '{"answer":"x","cited_chunk_ids":[],"confidence":0.5,"intent":"chitchat"}',
        '{"answer":"x","confidence":0.5,"intent":"faq"}',
        "not json",
    ],
)
def test_invalid_reply_rejected(raw):
    with pytest.raises(ValidationError):
        LLMReply.model_validate_json(raw)
