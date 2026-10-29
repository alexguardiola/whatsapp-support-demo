from support_bot.webhook import parse_event


def payload(**over):
    base = {
        "event": "message_created",
        "id": 77,
        "content": "¿Abrís los sábados?",
        "message_type": "incoming",
        "private": False,
        "account": {"id": 1, "name": "Ondaviva"},
        "conversation": {"id": 12, "status": "pending", "meta": {"assignee": None}},
        "sender": {"id": 5, "type": "contact"},
    }
    base.update(over)
    return base


def test_parses_incoming_message():
    m = parse_event(payload())
    assert (m.account_id, m.conversation_id, m.message_id, m.content) == (1, 12, 77, "¿Abrís los sábados?")


def test_ignores_other_events():
    assert parse_event(payload(event="conversation_status_changed")) is None


def test_ignores_outgoing_and_private_messages():
    assert parse_event(payload(message_type="outgoing")) is None
    assert parse_event(payload(private=True)) is None


def test_ignores_conversations_already_with_a_human():
    assert parse_event(payload(conversation={"id": 12, "status": "open", "meta": {}})) is None
    assert (
        parse_event(payload(conversation={"id": 12, "status": "pending", "meta": {"assignee": {"id": 3}}}))
        is None
    )


def test_ignores_empty_content_and_garbage():
    assert parse_event(payload(content="  ")) is None
    assert parse_event(payload(content=None)) is None
    assert parse_event({"event": "message_created"}) is None
    assert parse_event("nope") is None


def test_message_type_as_integer_is_supported():
    assert parse_event(payload(message_type=0)) is not None
    assert parse_event(payload(message_type=1)) is None


def test_conversation_assigned_to_the_bot_itself_is_handled():
    conv = {"id": 12, "status": "pending", "meta": {"assignee": {"id": 1, "name": "Asistente"}, "assignee_type": "AgentBot"}}
    assert parse_event(payload(conversation=conv)) is not None


def test_conversation_assigned_to_a_person_is_ignored_even_if_pending():
    conv = {"id": 12, "status": "pending", "meta": {"assignee": {"id": 3}, "assignee_type": "User"}}
    assert parse_event(payload(conversation=conv)) is None
