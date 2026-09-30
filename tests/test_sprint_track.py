"""Offline tests for the sprint track: Notion and Telegram are mocked, nothing hits the network.

Run:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sprint_common  # noqa: E402
import sprint_mark_done  # noqa: E402
import sprint_reminder  # noqa: E402

ENV = {
    "NOTION_TOKEN": "notion-test",
    "SPRINT_DATA_SOURCE_ID": "ds-test",
    "SPRINT_TELEGRAM_BOT_TOKEN": "bot-test",
    "TELEGRAM_CHAT_ID": "42",
}


def make_row(
    page_id: str, day: int, slot: int, name: str, url: str | None = None
) -> dict[str, Any]:
    return {
        "id": page_id,
        "properties": {
            "Name": {"title": [{"plain_text": name}]},
            "Day": {"number": day},
            "Slot": {"number": slot},
            "Topic": {"select": {"name": "Stack"}},
            "Pattern": {"rich_text": [{"plain_text": "Monotonic stack"}]},
            "Difficulty": {"select": {"name": "Medium"}},
            "URL": {"url": url},
        },
    }


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class MessageTests(unittest.TestCase):
    def test_lists_only_the_lowest_open_day_ordered_by_slot(self) -> None:
        rows = [
            make_row("b", 1, 2, "84 Largest Rectangle", "https://leetcode.com/problems/x/"),
            make_row(
                "a", 1, 1, "739 Daily <Temperatures> & co", "https://leetcode.com/problems/y/"
            ),
            make_row("c", 2, 1, "146 LRU Cache"),
        ]
        text = sprint_reminder.build_message(rows)
        self.assertIn("Sprint Day 1", text)
        self.assertNotIn("LRU Cache", text)
        self.assertLess(text.index("739"), text.index("84 Largest"))
        self.assertIn("&lt;Temperatures&gt; &amp; co", text)  # HTML-escaped for Telegram
        self.assertIn("Reply <b>done</b>", text)

    def test_row_without_url_renders_plain_title(self) -> None:
        text = sprint_reminder.build_message([make_row("a", 6, 1, "MOCK 2 sealed", None)])
        self.assertIn("1. MOCK 2 sealed", text)
        self.assertNotIn("<a href", text)

    def test_completion_message_when_nothing_is_open(self) -> None:
        self.assertIn("Sprint complete", sprint_reminder.build_message([]))


class ReminderMainTests(unittest.TestCase):
    def test_queries_notion_then_sends_via_the_sprint_bot(self) -> None:
        rows = [make_row("a", 1, 1, "739 Daily Temperatures", "https://leetcode.com/problems/y/")]
        with (
            mock.patch.dict(os.environ, ENV, clear=True),
            mock.patch.object(
                sprint_common.requests,
                "post",
                side_effect=[FakeResponse({"results": rows}), FakeResponse({})],
            ) as post,
        ):
            sprint_reminder.main()
        notion_call, telegram_call = post.call_args_list
        self.assertIn("/data_sources/ds-test/query", notion_call.args[0])
        self.assertEqual(notion_call.kwargs["json"]["sorts"][0]["property"], "Day")
        self.assertIn("/botbot-test/sendMessage", telegram_call.args[0])
        self.assertEqual(telegram_call.kwargs["data"]["chat_id"], "42")

    def test_missing_configuration_fails_loudly(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(SystemExit) as ctx:
            sprint_reminder.main()
        self.assertIn("NOTION_TOKEN", str(ctx.exception))


def update(update_id: int, text: str, chat_id: int = 42) -> dict[str, Any]:
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": text}}


class DoneListenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "sprint_telegram_offset.json"
        patcher = mock.patch.object(sprint_mark_done, "STATE_FILE", self.state)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, updates: list[dict[str, Any]], open_rows: list[dict[str, Any]]):
        with (
            mock.patch.dict(os.environ, ENV, clear=True),
            mock.patch.object(sprint_mark_done, "get_telegram_updates", return_value=updates),
            mock.patch.object(sprint_mark_done, "query_open_rows", return_value=open_rows),
            mock.patch.object(sprint_mark_done, "mark_page_done") as done,
            mock.patch.object(sprint_mark_done, "send_telegram") as send,
        ):
            sprint_mark_done.main()
        return done, send

    def test_first_run_calibrates_offset_and_acts_on_nothing(self) -> None:
        done, send = self.run_main([update(10, "done")], [make_row("a", 1, 1, "x")])
        done.assert_not_called()
        send.assert_not_called()
        self.assertEqual(json.loads(self.state.read_text())["last_update_id"], 10)

    def test_done_closes_every_row_of_the_active_day_only(self) -> None:
        self.state.write_text(json.dumps({"last_update_id": 10}))
        rows = [make_row("a", 1, 1, "x"), make_row("b", 1, 2, "y"), make_row("c", 2, 1, "z")]
        done, send = self.run_main([update(11, "Done!")], rows)
        self.assertEqual([c.args[1] for c in done.call_args_list], ["a", "b"])
        self.assertIn("Sprint Day 1 marked done (2 problem(s))", send.call_args.args[2])
        self.assertEqual(json.loads(self.state.read_text())["last_update_id"], 11)

    def test_two_done_replies_in_one_poll_close_only_one_day(self) -> None:
        self.state.write_text(json.dumps({"last_update_id": 10}))
        rows = [make_row("a", 1, 1, "x"), make_row("c", 2, 1, "z")]
        done, _ = self.run_main([update(11, "done"), update(12, "done")], rows)
        self.assertEqual([c.args[1] for c in done.call_args_list], ["a"])

    def test_messages_from_other_chats_and_other_words_are_ignored(self) -> None:
        self.state.write_text(json.dumps({"last_update_id": 10}))
        rows = [make_row("a", 1, 1, "x")]
        done, send = self.run_main([update(11, "done", chat_id=99), update(12, "hello")], rows)
        done.assert_not_called()
        send.assert_not_called()
        self.assertEqual(json.loads(self.state.read_text())["last_update_id"], 12)

    def test_done_with_nothing_open_sends_a_friendly_note(self) -> None:
        self.state.write_text(json.dumps({"last_update_id": 10}))
        done, send = self.run_main([update(11, "done")], [])
        done.assert_not_called()
        self.assertIn("already Done", send.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
