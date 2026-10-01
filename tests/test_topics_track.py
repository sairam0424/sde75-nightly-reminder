"""Offline tests for the topics track: Notion and Telegram are mocked.

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
import topics_mark_done  # noqa: E402
import topics_reminder  # noqa: E402

ENV = {
    "NOTION_TOKEN": "notion-test",
    "TOPICS_DATA_SOURCE_ID": "ds-topics",
    "TOPICS_TELEGRAM_BOT_TOKEN": "bot-topics",
    "TELEGRAM_CHAT_ID": "42",
}


def make_row(
    page_id: str,
    day: int,
    slot: int,
    name: str,
    kind: str = "GenAI",
    questions: str = "1. What is X?\n2. Why Y?",
    task: str = "Read <it> & write",
    url: str | None = "https://example.com/a",
) -> dict[str, Any]:
    return {
        "id": page_id,
        "properties": {
            "Name": {"title": [{"plain_text": name}]},
            "Day": {"number": day},
            "Slot": {"number": slot},
            "Kind": {"select": {"name": kind}},
            "Questions": {"rich_text": [{"plain_text": questions}]},
            "Task": {"rich_text": [{"plain_text": task}]},
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
    def test_lists_three_items_of_the_active_day_in_slot_order(self) -> None:
        rows = [
            make_row("b", 2, 2, "Resume D2", "Resume", url=None),
            make_row("a", 2, 1, "GenAI D2 <MCP> & co"),
            make_row("c", 2, 3, "Stories D2", "Behavioural", url=None),
        ]
        text = topics_reminder.build_message(rows, 2, [])
        self.assertIn("Interview Topics — Day 2", text)
        self.assertLess(text.index("GenAI D2"), text.index("Resume D2"))
        self.assertLess(text.index("Resume D2"), text.index("Stories D2"))
        self.assertIn("&lt;MCP&gt; &amp; co", text)  # title HTML-escaped
        self.assertIn("Task: Read &lt;it&gt; &amp; write", text)
        self.assertIn("1. What is X?", text)
        self.assertIn("Reply <b>done</b>", text)

    def test_item_without_url_has_no_read_line(self) -> None:
        text = topics_reminder.build_message([make_row("a", 1, 2, "R", "Resume", url=None)], 1, [])
        self.assertNotIn("Read:", text)

    def test_recall_section_lists_earlier_days(self) -> None:
        recall = [make_row("x", 1, 1, "GenAI D1"), make_row("y", 5, 2, "Resume D5", "Resume")]
        text = topics_reminder.build_message([make_row("a", 8, 1, "GenAI D8")], 8, recall)
        self.assertIn("Recall", text)
        self.assertIn("Day 1: GenAI D1", text)
        self.assertIn("Day 5: Resume D5", text)

    def test_recall_days_only_include_positive_days(self) -> None:
        self.assertEqual(topics_reminder.recall_days(2), [])
        self.assertEqual(topics_reminder.recall_days(4), [1])
        self.assertEqual(topics_reminder.recall_days(10), [7, 3])

    def test_completion_message_and_length_cap(self) -> None:
        self.assertIn("complete", topics_reminder.build_message([], None, []))
        huge = make_row("a", 1, 1, "T", task="x " * 3000)
        self.assertLessEqual(len(topics_reminder.build_message([huge], 1, [])), 4000)


class ReminderMainTests(unittest.TestCase):
    def test_queries_open_rows_then_recall_then_sends_via_topics_bot(self) -> None:
        open_rows = [make_row("a", 4, 1, "GenAI D4")]
        recall_rows = [make_row("x", 1, 1, "GenAI D1")]
        with (
            mock.patch.dict(os.environ, ENV, clear=True),
            mock.patch.object(
                sprint_common.requests,
                "post",
                side_effect=[
                    FakeResponse({"results": open_rows}),
                    FakeResponse({"results": recall_rows}),
                    FakeResponse({}),
                ],
            ) as post,
        ):
            topics_reminder.main()
        calls = post.call_args_list
        self.assertIn("/data_sources/ds-topics/query", calls[0].args[0])
        self.assertEqual(
            calls[1].kwargs["json"]["filter"],
            {"or": [{"property": "Day", "number": {"equals": 1}}]},
        )
        self.assertIn("/botbot-topics/sendMessage", calls[2].args[0])
        self.assertEqual(calls[2].kwargs["data"]["chat_id"], "42")

    def test_missing_configuration_fails_loudly(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(SystemExit) as ctx:
            topics_reminder.main()
        self.assertIn("NOTION_TOKEN", str(ctx.exception))


def update(update_id: int, text: str, chat_id: int = 42) -> dict[str, Any]:
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": text}}


class DoneListenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "topics_telegram_offset.json"
        patcher = mock.patch.object(topics_mark_done, "STATE_FILE", self.state)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, updates: list[dict[str, Any]], open_rows: list[dict[str, Any]]):
        with (
            mock.patch.dict(os.environ, ENV, clear=True),
            mock.patch.object(topics_mark_done, "describe_bot", return_value="Bot @t"),
            mock.patch.object(topics_mark_done, "get_telegram_updates", return_value=updates),
            mock.patch.object(topics_mark_done, "query_open_rows", return_value=open_rows),
            mock.patch.object(topics_mark_done, "mark_page_done") as done,
            mock.patch.object(topics_mark_done, "send_telegram") as send,
        ):
            topics_mark_done.main()
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
        self.assertIn("Topics Day 1 marked done (2 item(s))", send.call_args.args[2])

    def test_two_done_replies_in_one_poll_close_only_one_day(self) -> None:
        self.state.write_text(json.dumps({"last_update_id": 10}))
        rows = [make_row("a", 1, 1, "x"), make_row("c", 2, 1, "z")]
        done, _ = self.run_main([update(11, "done"), update(12, "done")], rows)
        self.assertEqual([c.args[1] for c in done.call_args_list], ["a"])

    def test_other_chats_and_other_words_are_ignored(self) -> None:
        self.state.write_text(json.dumps({"last_update_id": 10}))
        done, send = self.run_main(
            [update(11, "done", chat_id=99), update(12, "hello")], [make_row("a", 1, 1, "x")]
        )
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
