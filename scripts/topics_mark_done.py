"""Two-way listener for the topics bot: a "done" reply closes the active topics day.

Own Telegram bot and own offset file, so it never interacts with the SDE-75 or sprint
listeners (Telegram deletes updates older than the offset a bot acknowledges).
"""

from __future__ import annotations

import json
from pathlib import Path

from sprint_common import (
    active_day_rows,
    describe_bot,
    query_open_rows,
    require_env,
    send_telegram,
)
from sprint_mark_done import get_telegram_updates, has_done_reply, mark_page_done

STATE_DIR = Path(__file__).parent.parent / "state"
STATE_FILE = STATE_DIR / "topics_telegram_offset.json"


def load_offset(state_file: Path | None = None) -> int:
    path = state_file or STATE_FILE
    if not path.exists():
        return 0
    return int(json.loads(path.read_text()).get("last_update_id", 0))


def save_offset(update_id: int, state_file: Path | None = None) -> None:
    (state_file or STATE_FILE).write_text(json.dumps({"last_update_id": update_id}))


def main(prefix: str = "TOPICS", label: str = "Topics", state_file: Path | None = None) -> None:
    notion_token = require_env("NOTION_TOKEN")
    data_source_id = require_env(f"{prefix}_DATA_SOURCE_ID")
    bot_token = require_env(f"{prefix}_TELEGRAM_BOT_TOKEN")
    chat_id = require_env("TELEGRAM_CHAT_ID")

    print(describe_bot(bot_token))
    last_offset = load_offset(state_file)
    updates = get_telegram_updates(bot_token, last_offset + 1 if last_offset else 0)
    if not updates:
        print("No new updates.")
        return

    max_update_id = max(u["update_id"] for u in updates)

    if last_offset == 0:
        print(f"Bootstrap run: skipping {len(updates)} historical update(s), calibrating offset.")
        save_offset(max_update_id, state_file)
        return

    # Close at most one day per poll, so a second "done" cannot close tomorrow by accident.
    if has_done_reply(updates, chat_id):
        active_day, rows = active_day_rows(query_open_rows(notion_token, data_source_id))
        if active_day is None:
            send_telegram(
                bot_token, chat_id, f"Every {label.lower()} day is already Done. \U0001f389"
            )
        else:
            for row in rows:
                mark_page_done(notion_token, row["id"])
            send_telegram(
                bot_token,
                chat_id,
                f"✅ {label} Day {active_day} marked done ({len(rows)} item(s)). "
                "Tomorrow's reminder moves to the next day.",
            )
    else:
        print("New message(s) received, none matched 'done'.")

    save_offset(max_update_id, state_file)


if __name__ == "__main__":
    main()
