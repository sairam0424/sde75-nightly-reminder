"""Two-way listener for the system design bot: a "done" reply closes the active day.

Own bot, own offset file (state/sd_telegram_offset.json); wrapper over topics_mark_done.
"""

from __future__ import annotations

import topics_mark_done


def main() -> None:
    topics_mark_done.main(
        prefix="SD",
        label="System Design",
        state_file=topics_mark_done.STATE_DIR / "sd_telegram_offset.json",
    )


if __name__ == "__main__":
    main()
