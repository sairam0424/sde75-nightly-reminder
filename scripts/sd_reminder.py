"""Midday reminder for the 15-day system design concepts (fourth bot, own Notion DB).

Thin wrapper over topics_reminder: same message format, SD_* configuration.
"""

from __future__ import annotations

import topics_reminder


def main() -> None:
    topics_reminder.main(prefix="SD", title="System Design")


if __name__ == "__main__":
    main()
