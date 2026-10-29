from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingMessage:
    account_id: int
    conversation_id: int
    message_id: int
    content: str


def bot_may_answer(conversation: object) -> bool:
    """True while the conversation is pending and no person is assigned to it."""
    if not isinstance(conversation, dict):
        return False
    meta = conversation.get("meta") or {}
    human_assigned = meta.get("assignee") and meta.get("assignee_type") != "AgentBot"
    return conversation.get("status") == "pending" and not human_assigned


def parse_event(payload: object) -> IncomingMessage | None:
    """Return the customer message the bot should handle, or None for anything else."""
    if not isinstance(payload, dict) or payload.get("event") != "message_created":
        return None
    if payload.get("message_type") not in ("incoming", 0) or payload.get("private"):
        return None
    content = payload.get("content")
    conversation = payload.get("conversation") or {}
    account = payload.get("account") or {}
    if not isinstance(content, str) or not content.strip():
        return None
    if not bot_may_answer(conversation):
        return None
    try:
        return IncomingMessage(int(account["id"]), int(conversation["id"]), int(payload["id"]), content)
    except (KeyError, TypeError, ValueError):
        return None
