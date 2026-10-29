import sys

import support_bot.__main__ as entry


def test_server_runs_without_access_log_so_the_webhook_path_secret_is_not_logged(monkeypatch, tmp_path):
    from conftest import KNOWLEDGE_DIR

    seen = {}
    monkeypatch.setattr(entry.uvicorn, "run", lambda app, **kw: seen.update(kw))
    monkeypatch.setenv("BOT_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setenv("BOT_KNOWLEDGE_DIR", str(KNOWLEDGE_DIR))
    monkeypatch.setenv("BOT_USAGE_DB", str(tmp_path / "u.sqlite3"))
    monkeypatch.setattr(sys, "argv", ["support-bot", "--fake-llm"])
    entry.main()
    assert seen["access_log"] is False
