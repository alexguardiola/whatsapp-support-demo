import importlib.util
import os
import stat
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "envfile.py"


def load_envfile():
    spec = importlib.util.spec_from_file_location("envfile", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_update_env_creates_the_temp_file_private_without_relying_on_chmod(tmp_path, monkeypatch):
    envfile = load_envfile()
    path = tmp_path / ".env"
    path.write_text("A=1\n", encoding="utf-8")
    old_umask = os.umask(0)
    try:
        monkeypatch.setattr(envfile.os, "chmod", lambda *a, **k: None)
        envfile.update_env({"B": "2"}, path)
    finally:
        os.umask(old_umask)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert envfile.read_env(path) == {"A": "1", "B": "2"}


def test_update_env_replaces_a_leftover_world_readable_temp_file(tmp_path):
    envfile = load_envfile()
    path = tmp_path / ".env"
    path.write_text("A=1\n", encoding="utf-8")
    leftover = path.with_suffix(".tmp")
    leftover.write_text("stale", encoding="utf-8")
    leftover.chmod(0o644)
    envfile.update_env({"A": "3"}, path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert envfile.read_env(path) == {"A": "3"}
    assert not leftover.exists()
