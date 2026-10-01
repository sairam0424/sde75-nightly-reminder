"""Morning reminder for the 15-day GenAI + Resume + Stories topics (third bot, own Notion DB).

Each message shows the lowest unfinished day: one GenAI topic, one Resume topic and one
Stories topic, each with recall questions and a task. Items from 3 and 7 days earlier are
listed under "Recall" as a spaced-repetition prompt. The Notion content is private; this
repo only holds generic code.
"""

from __future__ import annotations

import html
from typing import Any

import requests
from sprint_common import (
    MAX_ROWS,
    TIMEOUT_SECONDS,
    active_day_rows,
    notion_headers,
    query_open_rows,
    require_env,
    send_telegram,
)

RECALL_OFFSETS = (3, 7)
TELEGRAM_LIMIT = 3900
KIND_ICONS = {"GenAI": "\U0001f916", "Resume": "\U0001f4c4", "Behavioural": "\U0001f5e3"}


def _plain(prop: dict[str, Any], key: str) -> str:
    items = prop.get(key) or []
    return "".join(str(i["plain_text"]) for i in items)


def _select_name(prop: dict[str, Any]) -> str:
    sel = prop.get("select")
    return str(sel["name"]) if sel else ""


def _slot(row: dict[str, Any]) -> int:
    value = row["properties"].get("Slot", {}).get("number")
    return int(value) if value is not None else 0


def _day(row: dict[str, Any]) -> int:
    return int(row["properties"]["Day"]["number"])


def query_recall_rows(
    notion_token: str, data_source_id: str, days: list[int]
) -> list[dict[str, Any]]:
    """All rows (any status) for the given days, ordered by Day then Slot."""
    if not days:
        return []
    url = f"https://api.notion.com/v1/data_sources/{data_source_id}/query"
    payload: dict[str, Any] = {
        "filter": {"or": [{"property": "Day", "number": {"equals": d}} for d in days]},
        "sorts": [
            {"property": "Day", "direction": "ascending"},
            {"property": "Slot", "direction": "ascending"},
        ],
        "page_size": MAX_ROWS * 2,
    }
    resp = requests.post(
        url, headers=notion_headers(notion_token), json=payload, timeout=TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    results: list[dict[str, Any]] = resp.json()["results"]
    return results


def _item_block(row: dict[str, Any]) -> list[str]:
    props = row["properties"]
    kind = _select_name(props["Kind"])
    name = html.escape(_plain(props["Name"], "title"))
    icon = KIND_ICONS.get(kind, "•")
    url = props["URL"].get("url") or ""
    lines = [f"{icon} <b>{name}</b>"]
    if url:
        lines.append(f'Read: <a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>')
    questions = _plain(props["Questions"], "rich_text")
    if questions:
        lines.append("Say aloud, page closed:")
        lines += [html.escape(q) for q in questions.split("\n") if q.strip()]
    task = _plain(props["Task"], "rich_text")
    if task:
        lines.append(f"Task: {html.escape(task)}")
    return lines


def recall_days(active_day: int) -> list[int]:
    return [active_day - offset for offset in RECALL_OFFSETS if active_day - offset >= 1]


def build_message(
    todays: list[dict[str, Any]], active_day: int | None, recall_rows: list[dict[str, Any]]
) -> str:
    if active_day is None:
        return (
            "Topics track complete! Every GenAI, Resume and Stories day is marked Done. \U0001f389"
        )

    lines = [f"<b>Interview Topics — Day {active_day}</b>", ""]
    for row in sorted(todays, key=_slot):
        lines += _item_block(row) + [""]

    if recall_rows:
        lines.append("\U0001f501 <b>Recall</b> (answer from memory first):")
        for row in recall_rows:
            name = html.escape(_plain(row["properties"]["Name"], "title"))
            lines.append(f"• Day {_day(row)}: {name}")
        lines.append("")

    lines.append("Reply <b>done</b> here when today's three items are finished.")
    text = "\n".join(lines)
    if len(text) > TELEGRAM_LIMIT:
        text = text[: TELEGRAM_LIMIT - 1].rsplit("\n", 1)[0] + "\n…"
    return text


def main() -> None:
    notion_token = require_env("NOTION_TOKEN")
    data_source_id = require_env("TOPICS_DATA_SOURCE_ID")
    bot_token = require_env("TOPICS_TELEGRAM_BOT_TOKEN")
    chat_id = require_env("TELEGRAM_CHAT_ID")

    active_day, todays = active_day_rows(query_open_rows(notion_token, data_source_id))
    recall = (
        query_recall_rows(notion_token, data_source_id, recall_days(active_day))
        if active_day is not None
        else []
    )
    message = build_message(todays, active_day, recall)
    send_telegram(bot_token, chat_id, message)
    print(message)


if __name__ == "__main__":
    main()
