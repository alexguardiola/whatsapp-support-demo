import pytest

from support_bot.models import LLMReply
from support_bot.policy import HANDOFF_INTENTS, OFF_TOPIC_TEXT, decide, precheck


def reply(answer="La sesión dura 45 minutos.", ids=None, confidence=0.9, intent="faq"):
    return LLMReply(
        answer=answer,
        cited_chunk_ids=ids if ids is not None else ["servicios#fisioterapia-general"],
        confidence=confidence,
        intent=intent,
    )


@pytest.fixture
def retrieved(retriever):
    return retriever.search("cuánto dura una sesión de fisioterapia general precio", k=4)


def test_valid_cited_answer_is_sent(retrieved):
    d = decide(reply(), retrieved)
    assert d.action == "reply"
    assert d.text == "La sesión dura 45 minutos."
    assert d.cited_chunk_ids == ["servicios#fisioterapia-general"]


def test_answer_without_citations_hands_off(retrieved):
    d = decide(reply(ids=[]), retrieved)
    assert (d.action, d.reason) == ("handoff", "no_citations")


def test_citation_not_in_retrieved_chunks_hands_off(retrieved):
    d = decide(reply(ids=["servicios#fisioterapia-general", "inventado#x"]), retrieved)
    assert (d.action, d.reason) == ("handoff", "invalid_citation")


def test_low_confidence_hands_off(retrieved):
    d = decide(reply(confidence=0.4), retrieved)
    assert (d.action, d.reason) == ("handoff", "low_confidence")


@pytest.mark.parametrize("intent", sorted(HANDOFF_INTENTS))
def test_sensitive_intents_hand_off(intent, retrieved):
    d = decide(reply(intent=intent), retrieved)
    assert (d.action, d.reason) == ("handoff", f"intent:{intent}")


def test_price_from_sheet_is_answered(retrieved):
    d = decide(
        reply(
            answer="Una sesión de 45 minutos cuesta 40 €.",
            ids=["tarifas#sesion-de-fisioterapia-general"],
            intent="price",
        ),
        retrieved,
    )
    assert d.action == "reply"


def test_price_without_sheet_citation_hands_off(retrieved):
    d = decide(reply(answer="Cuesta unos 35 €.", intent="price"), retrieved)
    assert (d.action, d.reason) == ("handoff", "price_not_in_sheet")


def test_amount_not_present_in_cited_chunk_hands_off(retrieved):
    d = decide(
        reply(answer="Cuesta 35 €.", ids=["tarifas#sesion-de-fisioterapia-general"], intent="price"),
        retrieved,
    )
    assert (d.action, d.reason) == ("handoff", "price_not_in_sheet")


def test_amount_in_non_price_intent_is_also_checked(retrieved):
    d = decide(reply(answer="Son 20 € y dura 45 minutos."), retrieved)
    assert (d.action, d.reason) == ("handoff", "price_not_in_sheet")


def test_off_topic_gets_fixed_refusal_not_model_text(retrieved):
    d = decide(reply(answer="Aquí tienes un poema...", ids=[], intent="off_topic"), retrieved)
    assert d.action == "reply"
    assert d.text == OFF_TOPIC_TEXT


def test_missing_reply_hands_off(retrieved):
    d = decide(None, retrieved)
    assert (d.action, d.reason) == ("handoff", "llm_error")


def test_empty_answer_hands_off(retrieved):
    d = decide(reply(answer="   "), retrieved)
    assert (d.action, d.reason) == ("handoff", "empty_answer")


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("Quiero hablar con una persona", "human_request"),
        ("¿me pasas con un humano?", "human_request"),
        ("Quiero poner una queja, fue fatal", "complaint"),
        ("Voy a presentar una reclamación", "complaint"),
        ("Quiero que me devolváis el dinero del bono", "refund"),
        ("¿Cómo pido el reembolso?", "refund"),
    ],
)
def test_precheck_routes_without_model(message, reason):
    assert precheck(message) == reason


def test_precheck_lets_normal_questions_through():
    assert precheck("¿Abrís los sábados?") is None
