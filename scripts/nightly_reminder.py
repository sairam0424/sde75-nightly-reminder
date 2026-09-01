import os

import requests

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

DATA_SOURCE_ID = "fcd7e8ef-19f2-49cb-ab48-d81e1a2c576d"
NOTION_VERSION = "2025-09-03"


def query_notion():
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
    return resp.json()["results"]


def plain_title(prop):
    items = prop.get("title") or []
    return items[0]["plain_text"] if items else "(untitled)"


def plain_rich_text(prop):
    items = prop.get("rich_text") or []
    return items[0]["plain_text"] if items else ""


def select_name(prop):
    sel = prop.get("select")
    return sel["name"] if sel else ""


def build_message(rows):
    if not rows:
        return "SDE-75 complete! All 75 problems marked Done. \U0001f389"

    next_day = rows[0]["properties"]["Day"]["number"]
    todays = sorted(
        (r for r in rows if r["properties"]["Day"]["number"] == next_day),
        key=lambda r: r["properties"]["Slot"]["number"],
    )

    lines = [f"<b>Day {next_day} — Tonight's problems</b>", ""]
    for r in todays:
        p = r["properties"]
        name = plain_title(p["Name"])
        topic = select_name(p["Topic"])
        pattern = plain_rich_text(p["Pattern"])
        difficulty = select_name(p["Difficulty"])
        url = p["URL"].get("url") or ""
        slot = p["Slot"]["number"]
        label = f"{slot}. {name} — {topic} / {pattern}, {difficulty}"
        if url:
            label = f'{slot}. <a href="{url}">{name}</a> — {topic} / {pattern}, {difficulty}'
        lines.append(label)

    return "\n".join(lines)


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()


def main():
    rows = query_notion()
    message = build_message(rows)
    send_telegram(message)
    print(message)


if __name__ == "__main__":
    main()
