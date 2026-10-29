from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from support_bot.hours import BusinessHours
from support_bot.knowledge import Retriever, load_chunks
from support_bot.usage import UsageCap

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
MADRID = ZoneInfo("Europe/Madrid")
OPEN_TIME = datetime(2026, 10, 27, 10, 30, tzinfo=MADRID)  # Tuesday morning
CLOSED_TIME = datetime(2026, 10, 25, 11, 0, tzinfo=MADRID)  # Sunday


@pytest.fixture
def chunks():
    return load_chunks(KNOWLEDGE_DIR)


@pytest.fixture
def retriever(chunks):
    return Retriever(chunks)


@pytest.fixture
def hours():
    return BusinessHours.default()


@pytest.fixture
def cap(tmp_path):
    return UsageCap(tmp_path / "usage.sqlite3", max_calls_per_day=3, max_tokens_per_day=10_000)


class RecordingChatwoot:
    def __init__(self):
        self.calls = []

    async def reply(self, account_id, conversation_id, text):
        self.calls.append(("reply", account_id, conversation_id, text))

    async def private_note(self, account_id, conversation_id, text):
        self.calls.append(("note", account_id, conversation_id, text))

    async def hand_off(self, account_id, conversation_id):
        self.calls.append(("handoff", account_id, conversation_id))

    def kinds(self):
        return [c[0] for c in self.calls]


@pytest.fixture
def chatwoot():
    return RecordingChatwoot()
