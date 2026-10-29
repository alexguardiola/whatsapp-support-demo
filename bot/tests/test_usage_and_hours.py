from datetime import datetime, timedelta

from conftest import CLOSED_TIME, MADRID, OPEN_TIME
from support_bot.usage import UsageCap


def test_cap_allows_until_limit_then_blocks(cap):
    assert [cap.try_consume(OPEN_TIME) for _ in range(4)] == [True, True, True, False]


def test_cap_resets_next_day(cap):
    for _ in range(3):
        cap.try_consume(OPEN_TIME)
    assert cap.try_consume(OPEN_TIME + timedelta(days=1))


def test_token_budget_blocks(tmp_path):
    cap = UsageCap(tmp_path / "u.sqlite3", max_calls_per_day=100, max_tokens_per_day=1000)
    assert cap.try_consume(OPEN_TIME)
    cap.record_tokens(OPEN_TIME, 1200)
    assert not cap.try_consume(OPEN_TIME)
    assert cap.snapshot(OPEN_TIME) == {"calls": 1, "tokens": 1200}


def test_cap_persists_across_instances(tmp_path):
    path = tmp_path / "u.sqlite3"
    UsageCap(path, 1, 1000).try_consume(OPEN_TIME)
    assert not UsageCap(path, 1, 1000).try_consume(OPEN_TIME)


def test_business_hours(hours):
    assert hours.is_open(OPEN_TIME)
    assert not hours.is_open(CLOSED_TIME)
    assert not hours.is_open(datetime(2026, 10, 27, 15, 0, tzinfo=MADRID))  # lunch break
    assert hours.is_open(datetime(2026, 10, 31, 12, 59, tzinfo=MADRID))  # Saturday
    assert not hours.is_open(datetime(2026, 10, 31, 13, 0, tzinfo=MADRID))


def test_business_hours_converts_utc(hours):
    utc = datetime(2026, 10, 27, 9, 30, tzinfo=MADRID).astimezone(tz=None)
    assert hours.is_open(utc)
