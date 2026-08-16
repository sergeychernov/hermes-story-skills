#!/usr/bin/env python3
"""Normalize a Russian recording-date phrase to YYYY-MM-DD."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKDAYS_RU = {
    "понедельник": 0, "понедельника": 0,
    "вторник": 1, "вторника": 1,
    "среда": 2, "среду": 2,
    "четверг": 3, "четверга": 3,
    "пятница": 4, "пятницу": 4,
    "суббота": 5, "субботу": 5,
    "воскресенье": 6,
}


def _parse_today(value: str | None, timezone: str) -> date:
    if value:
        return date.fromisoformat(value)
    try:
        return datetime.now(ZoneInfo(timezone)).date()
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone}") from exc


def normalize_recording_date(phrase: str, *, today: str | None, timezone: str) -> dict[str, str]:
    anchor = _parse_today(today, timezone)
    text = " ".join(phrase.strip().casefold().replace("ё", "е").split())
    if not text:
        raise ValueError("recording date phrase is empty")
    try:
        resolved = date.fromisoformat(text)
        interpretation = "exact-date"
    except ValueError:
        if text == "сегодня":
            resolved, interpretation = anchor, "today"
        elif text == "вчера":
            resolved, interpretation = anchor - timedelta(days=1), "yesterday"
        elif text == "позавчера":
            resolved, interpretation = anchor - timedelta(days=2), "day-before-yesterday"
        else:
            raw_tokens = text.replace("во ", "").replace("в ", "").split()
            previous = any(token.startswith("прошл") for token in raw_tokens)
            tokens = [token for token in raw_tokens if not token.startswith("прошл")]
            weekday = next((WEEKDAYS_RU[token] for token in tokens if token in WEEKDAYS_RU), None)
            if weekday is None:
                raise ValueError("unsupported recording date; use YYYY-MM-DD, сегодня, вчера, позавчера or a Russian weekday")
            delta = (anchor.weekday() - weekday) % 7
            if previous and delta == 0:
                delta = 7
            resolved = anchor - timedelta(days=delta)
            interpretation = "most-recent-weekday"
    if resolved > anchor:
        raise ValueError("recording date cannot be in the future")
    return {
        "input": phrase,
        "today": anchor.isoformat(),
        "timezone": timezone,
        "date": resolved.isoformat(),
        "interpretation": interpretation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phrase")
    parser.add_argument("--today", help="Explicit local anchor date YYYY-MM-DD; omit to use current date in --timezone")
    parser.add_argument("--timezone", default="UTC")
    args = parser.parse_args()
    try:
        result = normalize_recording_date(args.phrase, today=args.today, timezone=args.timezone)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
