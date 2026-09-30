"""Two-way listener for the 15-day sprint bot: a "done" reply closes the active sprint day.

Runs on its own Telegram bot, so its getUpdates queue and offset never interact with the
original SDE-75 listener (Telegram deletes updates older than the offset a bot acknowledges).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests
from sprint_common import (
    TIMEOUT_SECONDS,
    active_day_rows,
    describe_bot,
    notion_headers,
    query_open_rows,
    require_env,
    send_telegram,
)

STATE_FILE = Path(__file__).parent.parent / "state" / "sprint_telegram_offset.json"


def load_offset() -> int:
    if not STATE_FILE.exists():
        return 0
    return int(json.loads(STATE_FILE.read_text()).get("last_update_id", 0))


def save_offset(update_id: int) -> None:
    STATE_FILE.write_text(json.dumps({"last_update_id": update_id}))


def get_telegram_updates(bot_token: str, offset: int) -> list[dict[str, Any]]:
    params = {"offset": offset, "timeout": 0} if offset else {"timeout": 0}
    resp = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getUpdates",
        params=params,
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    updates: list[dict[str, Any]] = resp.json()["result"]
    return updates


def mark_page_done(notion_token: str, page_id: str) -> None:
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=notion_headers(notion_token),
        json={"properties": {"Status": {"status": {"name": "Done"}}}},
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()


def has_done_reply(updates: list[dict[str, Any]], chat_id: str) -> bool:
    """True if any update from the configured chat starts with 'done'."""
    for update in updates:
        message = update.get("message")
        if not message:
            continue
        if str(message.get("chat", {}).get("id", "")) != str(chat_id):
            continue
        if (message.get("text") or "").strip().lower().startswith("done"):
            return True
    return False


def main() -> None:
    notion_token = require_env("NOTION_TOKEN")
    data_source_id = require_env("SPRINT_DATA_SOURCE_ID")
    bot_token = require_env("SPRINT_TELEGRAM_BOT_TOKEN")
    chat_id = require_env("TELEGRAM_CHAT_ID")

    print(describe_bot(bot_token))
    last_offset = load_offset()
    updates = get_telegram_updates(bot_token, last_offset + 1 if last_offset else 0)
    if not updates:
        print("No new updates.")
        return

    max_update_id = max(u["update_id"] for u in updates)

    if last_offset == 0:
        # First-ever run: calibrate past existing history, act on nothing.
        print(f"Bootstrap run: skipping {len(updates)} historical update(s), calibrating offset.")
        save_offset(max_update_id)
        return

    # Close at most one day per poll, even if several "done" replies arrived together;
    # otherwise the second reply would close the following day by accident.
    if has_done_reply(updates, chat_id):
        active_day, rows = active_day_rows(query_open_rows(notion_token, data_source_id))
        if active_day is None:
            send_telegram(bot_token, chat_id, "Every sprint problem is already Done. \U0001f389")
        else:
            for row in rows:
                mark_page_done(notion_token, row["id"])
            send_telegram(
                bot_token,
                chat_id,
                f"✅ Sprint Day {active_day} marked done ({len(rows)} problem(s)). "
                "Tomorrow's reminder moves to the next day.",
            )
    else:
        print("New message(s) received, none matched 'done'.")

    save_offset(max_update_id)


if __name__ == "__main__":
    main()
