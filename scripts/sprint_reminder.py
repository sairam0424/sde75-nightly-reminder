"""Nightly reminder for the 15-day interview sprint (second bot, separate Notion DB)."""

from __future__ import annotations

import html
from typing import Any

from sprint_common import (
    active_day_rows,
    query_open_rows,
    require_env,
    send_telegram,
)


def _plain_title(prop: dict[str, Any]) -> str:
    items = prop.get("title") or []
    return str(items[0]["plain_text"]) if items else "(untitled)"


def _plain_rich_text(prop: dict[str, Any]) -> str:
    items = prop.get("rich_text") or []
    return str(items[0]["plain_text"]) if items else ""


def _select_name(prop: dict[str, Any]) -> str:
    sel = prop.get("select")
    return str(sel["name"]) if sel else ""


def _slot(row: dict[str, Any]) -> int:
    value = row["properties"].get("Slot", {}).get("number")
    return int(value) if value is not None else 0


def build_message(rows: list[dict[str, Any]]) -> str:
    active_day, todays = active_day_rows(rows)
    if active_day is None:
        return "Sprint complete! Every sprint problem is marked Done. \U0001f389"

    lines = [f"<b>Sprint Day {active_day} — Tonight's problems</b>", ""]
    for row in sorted(todays, key=_slot):
        props = row["properties"]
        name = html.escape(_plain_title(props["Name"]))
        topic = html.escape(_select_name(props["Topic"]))
        pattern = html.escape(_plain_rich_text(props["Pattern"]))
        difficulty = html.escape(_select_name(props["Difficulty"]))
        url = props["URL"].get("url") or ""
        title = f'<a href="{html.escape(url, quote=True)}">{name}</a>' if url else name
        lines.append(f"{_slot(row)}. {title} — {topic} / {pattern}, {difficulty}")

    lines += ["", "Reply <b>done</b> here when the whole day is finished."]
    return "\n".join(lines)


def main() -> None:
    notion_token = require_env("NOTION_TOKEN")
    data_source_id = require_env("SPRINT_DATA_SOURCE_ID")
    bot_token = require_env("SPRINT_TELEGRAM_BOT_TOKEN")
    chat_id = require_env("TELEGRAM_CHAT_ID")

    message = build_message(query_open_rows(notion_token, data_source_id))
    send_telegram(bot_token, chat_id, message)
    print(message)


if __name__ == "__main__":
    main()
