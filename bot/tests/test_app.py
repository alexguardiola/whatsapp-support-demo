from fastapi.testclient import TestClient

from support_bot.app import create_app
from support_bot.settings import Settings


def client(tmp_path, chatwoot):
    s = Settings(
        webhook_secret="s3cret",
        fake_llm=True,
        usage_db=str(tmp_path / "u.sqlite3"),
        knowledge_dir=str(__import__("conftest").KNOWLEDGE_DIR),
    )
    return TestClient(create_app(s, chatwoot=chatwoot))


def body(text="¿Abrís los sábados por la mañana?"):
    return {
        "event": "message_created",
        "id": 1,
        "content": text,
        "message_type": "incoming",
        "private": False,
        "account": {"id": 1},
        "conversation": {"id": 4, "status": "pending", "meta": {}},
    }


def test_health(tmp_path, chatwoot):
    r = client(tmp_path, chatwoot).get("/healthz")
    assert r.status_code == 200 and r.json()["llm"] == "fake"


def test_wrong_secret_rejected(tmp_path, chatwoot):
    r = client(tmp_path, chatwoot).post("/webhook/nope", json=body())
    assert r.status_code == 404
    assert chatwoot.calls == []


def test_webhook_processes_message(tmp_path, chatwoot):
    r = client(tmp_path, chatwoot).post("/webhook/s3cret", json=body())
    assert r.status_code == 200
    assert chatwoot.kinds() == ["reply"]


def test_webhook_ignores_irrelevant_event(tmp_path, chatwoot):
    r = client(tmp_path, chatwoot).post("/webhook/s3cret", json={"event": "webwidget_triggered"})
    assert r.status_code == 200 and r.json() == {"status": "ignored"}
    assert chatwoot.calls == []


def test_non_json_body_rejected(tmp_path, chatwoot):
    r = client(tmp_path, chatwoot).post("/webhook/s3cret", content=b"x", headers={"content-type": "application/json"})
    assert r.status_code == 400


def signed_client(tmp_path, chatwoot, now=1_800_000_000):
    s = Settings(
        webhook_secret="s3cret",
        webhook_hmac_secret="hmac-key",
        fake_llm=True,
        usage_db=str(tmp_path / "u.sqlite3"),
        knowledge_dir=str(__import__("conftest").KNOWLEDGE_DIR),
    )
    return TestClient(create_app(s, chatwoot=chatwoot, wall_clock=lambda: now))


def sign(raw: bytes, ts: str, key: str = "hmac-key") -> str:
    import hashlib
    import hmac

    return "sha256=" + hmac.new(key.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()


def test_valid_signature_accepted(tmp_path, chatwoot):
    import json

    raw = json.dumps(body()).encode()
    ts = "1800000000"
    r = signed_client(tmp_path, chatwoot).post(
        "/webhook/s3cret",
        content=raw,
        headers={"content-type": "application/json", "X-Chatwoot-Timestamp": ts, "X-Chatwoot-Signature": sign(raw, ts)},
    )
    assert r.status_code == 200 and r.json() == {"status": "accepted"}
    assert chatwoot.kinds() == ["reply"]


def test_missing_or_bad_signature_rejected(tmp_path, chatwoot):
    import json

    raw = json.dumps(body()).encode()
    ts = "1800000000"
    c = signed_client(tmp_path, chatwoot)
    assert c.post("/webhook/s3cret", content=raw).status_code == 401
    bad = {"X-Chatwoot-Timestamp": ts, "X-Chatwoot-Signature": sign(raw, ts, key="other")}
    assert c.post("/webhook/s3cret", content=raw, headers=bad).status_code == 401
    assert chatwoot.calls == []


def test_stale_signature_rejected(tmp_path, chatwoot):
    import json

    raw = json.dumps(body()).encode()
    ts = str(1_800_000_000 - 600)
    r = signed_client(tmp_path, chatwoot).post(
        "/webhook/s3cret", content=raw, headers={"X-Chatwoot-Timestamp": ts, "X-Chatwoot-Signature": sign(raw, ts)}
    )
    assert r.status_code == 401


def signed_post(c, raw, ts="1800000000", delivery=None, signature=None):
    headers = {"content-type": "application/json", "X-Chatwoot-Timestamp": ts, "X-Chatwoot-Signature": signature or sign(raw, ts)}
    if delivery:
        headers["X-Chatwoot-Delivery"] = delivery
    return c.post("/webhook/s3cret", content=raw, headers=headers)


def test_replayed_delivery_is_dropped(tmp_path, chatwoot):
    import json

    raw = json.dumps(body()).encode()
    c = signed_client(tmp_path, chatwoot)
    assert signed_post(c, raw, delivery="d-1").json() == {"status": "accepted"}
    again = signed_post(c, raw, delivery="d-1")
    assert again.status_code == 200 and again.json() == {"status": "duplicate"}
    assert chatwoot.kinds() == ["reply"]


def test_replay_with_a_new_delivery_id_is_dropped_by_signature(tmp_path, chatwoot):
    import json

    raw = json.dumps(body()).encode()
    c = signed_client(tmp_path, chatwoot)
    signed_post(c, raw, delivery="d-1")
    assert signed_post(c, raw, delivery="d-2").json() == {"status": "duplicate"}
    assert chatwoot.kinds() == ["reply"]


def test_new_deliveries_are_still_accepted(tmp_path, chatwoot):
    import json

    c = signed_client(tmp_path, chatwoot)
    first = json.dumps(body()).encode()
    second = json.dumps(body() | {"id": 2}).encode()
    assert signed_post(c, first, delivery="d-1").json() == {"status": "accepted"}
    assert signed_post(c, second, delivery="d-2").json() == {"status": "accepted"}


def test_replayed_delivery_without_hmac_is_dropped(tmp_path, chatwoot):
    c = client(tmp_path, chatwoot)
    assert c.post("/webhook/s3cret", json=body(), headers={"X-Chatwoot-Delivery": "d-1"}).json() == {"status": "accepted"}
    assert c.post("/webhook/s3cret", json=body(), headers={"X-Chatwoot-Delivery": "d-1"}).json() == {"status": "duplicate"}
    assert chatwoot.kinds() == ["reply"]


def test_rejected_request_does_not_burn_its_delivery_id(tmp_path, chatwoot):
    import json

    raw = json.dumps(body()).encode()
    c = signed_client(tmp_path, chatwoot)
    assert signed_post(c, raw, delivery="d-1", signature="sha256=" + "0" * 64).status_code == 401
    assert signed_post(c, raw, delivery="d-1").json() == {"status": "accepted"}


def test_non_ascii_signature_is_rejected_not_a_server_error(tmp_path, chatwoot):
    import json

    raw = json.dumps(body()).encode()
    c = signed_client(tmp_path, chatwoot)
    headers = [
        (b"content-type", b"application/json"),
        (b"x-chatwoot-timestamp", b"1800000000"),
        (b"x-chatwoot-signature", "sha256=é".encode()),
    ]
    r = c.post("/webhook/s3cret", content=raw, headers=headers)
    assert r.status_code == 401
    assert chatwoot.calls == []
