"""Shared helpers for the 15-day sprint reminder (second Telegram bot, second Notion DB).

The sprint track is deliberately independent of the original SDE-75 scripts: nothing here
is imported by, or changes the behaviour of, nightly_reminder.py / mark_done.py. The Notion
data source ID and the bot token come from the environment, never from source.
"""

from __future__ import annotations

import os
from typing import Any

import requests

NOTION_VERSION = "2025-09-03"
TIMEOUT_SECONDS = 15
MAX_ROWS = 25


def require_env(name: str) -> str:
    """Return a required environment variable or exit with a clear message."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def notion_headers(notion_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def query_open_rows(notion_token: str, data_source_id: str) -> list[dict[str, Any]]:
    """Rows not yet Done, ordered by Day then Slot. Rows without a Day are ignored."""
    url = f"https://api.notion.com/v1/data_sources/{data_source_id}/query"
    payload: dict[str, Any] = {
        "filter": {
            "and": [
                {"property": "Status", "status": {"does_not_equal": "Done"}},
                {"property": "Day", "number": {"is_not_empty": True}},
            ]
        },
        "sorts": [
            {"property": "Day", "direction": "ascending"},
            {"property": "Slot", "direction": "ascending"},
        ],
        "page_size": MAX_ROWS,
    }
    resp = requests.post(
        url, headers=notion_headers(notion_token), json=payload, timeout=TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    results: list[dict[str, Any]] = resp.json()["results"]
    return results


def day_of(row: dict[str, Any]) -> int:
    return int(row["properties"]["Day"]["number"])


def active_day_rows(rows: list[dict[str, Any]]) -> tuple[int | None, list[dict[str, Any]]]:
    """The lowest unfinished Day and the rows that belong to it."""
    if not rows:
        return None, []
    active_day = day_of(rows[0])
    return active_day, [r for r in rows if day_of(r) == active_day]


def send_telegram(bot_token: str, chat_id: str, text: str) -> None:
    resp = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
