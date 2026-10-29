from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

Slots = list[tuple[time, time]]


@dataclass(frozen=True)
class BusinessHours:
    schedule: dict[int, Slots]
    tz: ZoneInfo
    summary: str

    @classmethod
    def default(cls, tz: str = "Europe/Madrid") -> "BusinessHours":
        weekday = [(time(9), time(14)), (time(16), time(20))]
        schedule = {d: weekday for d in range(5)} | {5: [(time(9), time(13))]}
        summary = "lunes a viernes de 9:00 a 14:00 y de 16:00 a 20:00; sábados de 9:00 a 13:00"
        return cls(schedule, ZoneInfo(tz), summary)

    def is_open(self, when: datetime) -> bool:
        local = when.astimezone(self.tz)
        now = local.time()
        return any(start <= now < end for start, end in self.schedule.get(local.weekday(), []))
