import json
import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

from .chatwoot import Inbox
from .hours import BusinessHours
from .knowledge import Retriever
from .llm import LLM, LLMError
from .policy import MIN_CONFIDENCE, Decision, decide, precheck
from .prompt import build_messages
from .usage import UsageCap
from .webhook import IncomingMessage

log = logging.getLogger("support_bot")

REASONS_ES = {
    "human_request": "el cliente pide hablar con una persona",
    "complaint": "queja",
    "refund": "petición de devolución",
    "daily_cap": "tope diario de uso del bot alcanzado; el bot queda en pausa hasta mañana",
    "llm_error": "el modelo no respondió o devolvió un formato no válido",
    "empty_answer": "el modelo no dio respuesta",
    "no_citations": "respuesta sin fuentes citadas",
    "invalid_citation": "cita a una fuente que no estaba en el contexto",
    "low_confidence": "confianza baja",
    "price_not_in_sheet": "precio que no está en la hoja de tarifas",
    "intent:booking": "quiere reservar, cambiar o cancelar una cita",
    "intent:complaint": "queja",
    "intent:refund": "petición de devolución",
    "intent:medical": "consulta médica o de síntomas",
    "intent:legal": "consulta legal o de datos personales",
    "intent:human_request": "el cliente pide hablar con una persona",
}


class SupportBot:
    def __init__(
        self,
        retriever: Retriever,
        llm: LLM,
        cap: UsageCap,
        hours: BusinessHours,
        chatwoot: Inbox,
        top_k: int = 4,
        min_confidence: float = MIN_CONFIDENCE,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.retriever, self.llm, self.cap, self.hours, self.chatwoot = retriever, llm, cap, hours, chatwoot
        self.top_k, self.min_confidence, self.clock = top_k, min_confidence, clock

    async def handle(self, msg: IncomingMessage) -> Decision:
        started, now = time.monotonic(), self.clock()
        is_open = self.hours.is_open(now)
        chunks, tokens, reply = [], 0, None

        if reason := precheck(msg.content):
            decision = Decision("handoff", reason=reason)
        elif not self.cap.try_consume(now):
            decision = Decision("handoff", reason="daily_cap")
        else:
            chunks = self.retriever.search(msg.content, self.top_k)
            try:
                reply, tokens = await self.llm.complete(build_messages(msg.content, chunks))
            except LLMError as exc:
                log.warning("llm error: %s", exc)
            self.cap.record_tokens(now, tokens)
            decision = decide(reply, chunks, self.min_confidence)

        if decision.action == "reply":
            await self.chatwoot.reply(msg.account_id, msg.conversation_id, decision.text)
        else:
            await self.chatwoot.reply(msg.account_id, msg.conversation_id, self.handoff_text(is_open))
            await self.chatwoot.private_note(msg.account_id, msg.conversation_id, self.note(decision, reply, chunks, is_open))
            await self.chatwoot.hand_off(msg.account_id, msg.conversation_id)

        log.info(
            json.dumps(
                {
                    "conversation": msg.conversation_id,
                    "action": decision.action,
                    "reason": decision.reason,
                    "intent": reply.intent if reply else None,
                    "confidence": reply.confidence if reply else None,
                    "retrieved": [c.id for c in chunks],
                    "cited": decision.cited_chunk_ids,
                    "tokens": tokens,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                }
            )
        )
        return decision

    def handoff_text(self, is_open: bool) -> str:
        if is_open:
            return "Te paso con una persona del equipo, que te responderá en breve por este mismo chat."
        return (
            "Ahora estamos cerrados. Te paso con una persona del equipo, que te responderá por este chat "
            f"en cuanto abramos ({self.hours.summary})."
        )

    def note(self, decision: Decision, reply, chunks, is_open: bool) -> str:
        lines = [
            f"Bot: paso a persona. Motivo: {REASONS_ES.get(decision.reason, decision.reason)} ({decision.reason}).",
            "En horario." if is_open else "Fuera de horario: el cliente sabe que se le responderá al abrir.",
        ]
        if reply:
            lines.append(f"Intención detectada: {reply.intent}; confianza {reply.confidence:.2f}.")
        if chunks:
            lines.append("Fuentes recuperadas: " + ", ".join(c.id for c in chunks) + ".")
        if decision.draft:
            lines.append(f"Borrador del bot (NO enviado): {decision.draft}")
        return "\n".join(lines)
