from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CRON_EXPRESSION = os.getenv("PIPELINE_REFRESH_CRON", "0 3 1 * *")


@dataclass(frozen=True)
class CronField:
    values: set[int]

    def matches(self, value: int) -> bool:
        return value in self.values


def parse_field(field: str, minimum: int, maximum: int) -> CronField:
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        if "/" in part:
            base, step_text = part.split("/", 1)
            step = int(step_text)
            if base == "*":
                start, end = minimum, maximum
            elif "-" in base:
                start_text, end_text = base.split("-", 1)
                start, end = int(start_text), int(end_text)
            else:
                start = int(base)
                end = maximum
            values.update(range(start, end + 1, step))
            continue
        if part == "*":
            values.update(range(minimum, maximum + 1))
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            values.update(range(int(start_text), int(end_text) + 1))
            continue
        values.add(int(part))
    bounded = {value for value in values if minimum <= value <= maximum}
    if not bounded:
        raise ValueError(f"Invalid cron field: {field}")
    return CronField(bounded)


def parse_cron(expression: str) -> tuple[CronField, CronField, CronField, CronField, CronField]:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("PIPELINE_REFRESH_CRON must use five fields")
    minute, hour, day, month, weekday = fields
    return (
        parse_field(minute, 0, 59),
        parse_field(hour, 0, 23),
        parse_field(day, 1, 31),
        parse_field(month, 1, 12),
        parse_field(weekday, 0, 6),
    )


def matches(schedule: tuple[CronField, CronField, CronField, CronField, CronField], instant: datetime) -> bool:
    minute, hour, day, month, weekday = schedule
    return (
        minute.matches(instant.minute)
        and hour.matches(instant.hour)
        and day.matches(instant.day)
        and month.matches(instant.month)
        and weekday.matches((instant.weekday() + 1) % 7)
    )


def next_run(after: datetime, schedule: tuple[CronField, CronField, CronField, CronField, CronField]) -> datetime:
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        if matches(schedule, candidate):
            return candidate
        candidate += timedelta(minutes=1)
    raise RuntimeError("Unable to find next scheduled run within one year")


def run_refresh() -> None:
    command = [sys.executable, str(PROJECT_ROOT / "docker" / "pipeline_release.py"), "--mode", "refresh"]
    subprocess.run(command, cwd=PROJECT_ROOT, env=os.environ.copy(), check=True)


def main() -> None:
    schedule = parse_cron(CRON_EXPRESSION)
    while True:
        now = datetime.now()
        scheduled = next_run(now, schedule)
        sleep_seconds = max(1, int((scheduled - now).total_seconds()))
        print(f"scheduler: next refresh at {scheduled.isoformat(sep=' ', timespec='minutes')}")
        time.sleep(sleep_seconds)
        try:
            run_refresh()
        except subprocess.CalledProcessError as exc:
            print(f"scheduler: refresh failed with exit code {exc.returncode}", file=sys.stderr)


if __name__ == "__main__":
    main()
