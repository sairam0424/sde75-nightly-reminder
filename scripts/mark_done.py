import json
import os
from pathlib import Path

import requests

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

DATA_SOURCE_ID = "fcd7e8ef-19f2-49cb-ab48-d81e1a2c576d"
NOTION_VERSION = "2025-09-03"
STATE_FILE = Path(__file__).parent.parent / "state" / "telegram_offset.json"


def load_offset() -> int:
    if not STATE_FILE.exists():
        return 0
    return json.loads(STATE_FILE.read_text()).get("last_update_id", 0)


def save_offset(update_id: int) -> None:
    STATE_FILE.write_text(json.dumps({"last_update_id": update_id}))


def get_telegram_updates(offset: int):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"offset": offset, "timeout": 0} if offset else {"timeout": 0}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()["result"]


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    resp.raise_for_status()


def query_active_day_rows():
    url = f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    payload = {
        "filter": {"property": "Status", "status": {"does_not_equal": "Done"}},
        "sorts": [{"property": "Day", "direction": "ascending"}],
        "page_size": 10,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    rows = resp.json()["results"]
    if not rows:
        return None, []
    active_day = rows[0]["properties"]["Day"]["number"]
    return active_day, [
        r for r in rows if r["properties"]["Day"]["number"] == active_day
    ]


def mark_page_done(page_id: str) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    payload = {"properties": {"Status": {"status": {"name": "Done"}}}}
    resp = requests.patch(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()


def main():
    last_offset = load_offset()
    updates = get_telegram_updates(last_offset + 1 if last_offset else 0)

    if not updates:
        print("No new updates.")
        return

    max_update_id = max(u["update_id"] for u in updates)

    if last_offset == 0:
        # First-ever run: calibrate past existing history, act on nothing.
        print(
            f"Bootstrap run: skipping {len(updates)} historical update(s), calibrating offset."
        )
        save_offset(max_update_id)
        return

    acted = False
    for u in updates:
        message = u.get("message")
        if not message:
            continue
        chat_id = str(message.get("chat", {}).get("id", ""))
        if chat_id != str(TELEGRAM_CHAT_ID):
            continue
        text = (message.get("text") or "").strip().lower()
        if text.startswith("done"):
            active_day, rows = query_active_day_rows()
            if active_day is None:
                send_telegram(
                    "All 75 problems are already marked Done - nothing left to close out! \U0001f389"
                )
            else:
                for r in rows:
                    mark_page_done(r["id"])
                send_telegram(
                    f"✅ Marked Day {active_day} done ({len(rows)} problem(s)). Next reminder will move on to the following day."
                )
            acted = True

    if not acted:
        print("New message(s) received, none matched 'done'.")

    save_offset(max_update_id)


if __name__ == "__main__":
    main()
