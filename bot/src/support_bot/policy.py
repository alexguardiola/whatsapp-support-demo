import re
from dataclasses import dataclass, field

from .knowledge import Chunk
from .models import LLMReply
from .text import fold

MIN_CONFIDENCE = 0.6
HANDOFF_INTENTS = {"booking", "complaint", "refund", "medical", "legal", "human_request"}
PRICE_SOURCE = "tarifas"
OFF_TOPIC_TEXT = (
    "Solo puedo ayudarte con dudas sobre Fisioterapia Ondaviva: horarios, servicios, citas, tarifas y pagos. "
    "¿Te ayudo con algo de eso?"
)

_PRECHECK = [
    ("human_request", re.compile(r"\b(humano|persona|agente|recepcionista|alguien real)\b")),
    ("complaint", re.compile(r"\b(queja|quejarme|reclamacion|reclamaciones|denuncia|denunciar)\b")),
    ("refund", re.compile(r"\b(reembolso|reembolsar|devolucion|devolv\w*\s+(el|mi)\s+dinero)\b")),
]
_AMOUNT = re.compile(r"(?:€\s*(\d+(?:[.,]\d+)?))|(?:(\d+(?:[.,]\d+)?)\s*(?:€|euros?\b|eur\b))")


@dataclass
class Decision:
    action: str
    text: str = ""
    reason: str | None = None
    cited_chunk_ids: list[str] = field(default_factory=list)
    draft: str | None = None


def precheck(message: str) -> str | None:
    folded = fold(message)
    for reason, pattern in _PRECHECK:
        if pattern.search(folded):
            return reason
    return None


def amounts(text: str) -> set[float]:
    return {float((a or b).replace(",", ".")) for a, b in _AMOUNT.findall(text)}


def handoff(reason: str, reply: LLMReply | None = None) -> Decision:
    return Decision("handoff", reason=reason, draft=reply.answer if reply else None)


def decide(reply: LLMReply | None, retrieved: list[Chunk], min_confidence: float = MIN_CONFIDENCE) -> Decision:
    if reply is None:
        return handoff("llm_error")
    if reply.intent == "off_topic":
        return Decision("reply", text=OFF_TOPIC_TEXT, reason="off_topic")
    if reply.intent in HANDOFF_INTENTS:
        return handoff(f"intent:{reply.intent}", reply)
    if not reply.answer.strip():
        return handoff("empty_answer", reply)

    by_id = {c.id: c for c in retrieved}
    valid = [cid for cid in reply.cited_chunk_ids if cid in by_id]
    if reply.intent == "price" and not any(by_id[cid].source == PRICE_SOURCE for cid in valid):
        return handoff("price_not_in_sheet", reply)
    if not reply.cited_chunk_ids:
        return handoff("no_citations", reply)
    if len(valid) != len(reply.cited_chunk_ids):
        return handoff("invalid_citation", reply)
    if reply.confidence < min_confidence:
        return handoff("low_confidence", reply)

    cited_amounts = set().union(*(amounts(by_id[cid].text) for cid in valid))
    if not amounts(reply.answer) <= cited_amounts:
        return handoff("price_not_in_sheet", reply)
    return Decision("reply", text=reply.answer.strip(), cited_chunk_ids=valid)
