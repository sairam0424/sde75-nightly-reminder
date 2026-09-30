# Sprint track: a second, independent reminder bot

A time-boxed practice sprint (for example a 15-day interview push) runs on its **own Telegram bot**
and its **own Notion database**. The original SDE-75 reminder is not touched: different bot,
different database, different state file, different workflows.

| | SDE-75 (unchanged) | Sprint track (new) |
|---|---|---|
| Scripts | `nightly_reminder.py`, `mark_done.py` | `sprint_reminder.py`, `sprint_mark_done.py`, `sprint_common.py` |
| Workflows | Nightly DSA Reminder (19:53 IST), Telegram Done Listener | Sprint Nightly Reminder (20:08 IST), Sprint Done Listener |
| Notion database | hardcoded `DATA_SOURCE_ID` | repo variable `SPRINT_DATA_SOURCE_ID` |
| Telegram bot | `TELEGRAM_BOT_TOKEN` | `SPRINT_TELEGRAM_BOT_TOKEN` (a second bot) |
| Offset state | `state/telegram_offset.json` | `state/sprint_telegram_offset.json` |

**Why a second bot:** a bot's `getUpdates` queue is destructive (acknowledging an offset deletes older
updates). Two listeners on one bot would silently steal each other's `done` replies.

Reused as-is: the `NOTION_TOKEN` and `TELEGRAM_CHAT_ID` secrets (a private chat's id is your user id,
so it is the same for both bots).

## One-time setup, in this order

1. **Second bot.** In Telegram, message @BotFather, `/newbot`, keep the token private. Open the new
   bot and send `/start` (a bot cannot message you first, and this creates its first update).
2. **Sprint database.** Create a Notion database with the same properties the scripts read: `Name` (title), `Day` (number), `Slot` (number), `Status` (status, with a `Done` option), `Topic` (select), `Pattern` (text), `Difficulty` (select), `URL` (url); a `Mastery` select (New, Solved, Revisit, Weak) is optional. Either build it fresh (the schema above) or duplicate the SDE-75 database and delete the rows you do not want. Every row needs Day, Slot, Name, Topic, Pattern, Difficulty and URL; leave `Status` alone (new rows default to not started, and nothing may already be `Done`). Copied rows with the same `Day` numbers would merge into the sprint days, so prefer a fresh database with sprint-only rows if the SDE-75 reminder keeps running.
3. **Give the integration access.** Open the new database, `...` menu, *Connections*, add the same
   integration that `NOTION_TOKEN` belongs to.
4. **Get the data source ID** (the API version used here needs it, not the database ID): database
   `...` menu, *Manage data sources*, copy the data source ID. Alternative:
   `curl -s https://api.notion.com/v1/databases/<database_id> -H "Authorization: Bearer $NOTION_TOKEN" -H "Notion-Version: 2025-09-03"`
   and read `data_sources[0].id`.
5. **GitHub, Settings, Secrets and variables, Actions.**
   Variable `SPRINT_DATA_SOURCE_ID` = the data source ID. Secret `SPRINT_TELEGRAM_BOT_TOKEN` = the
   new bot's token.
6. **Merge to the default branch.** Scheduled workflows, and the *Run workflow* button, only exist
   for files on the default branch.

## Test before relying on it

1. Actions, *Sprint Done Listener*, **Run workflow once**. This first run only calibrates the offset
   (it skips history and commits `state/sprint_telegram_offset.json`), so do it **before** sending
   your first `done`. Otherwise that first `done` is swallowed as history.
2. Actions, *Sprint Nightly Reminder*, Run workflow. The new bot should send `Sprint Day 1`.
3. Reply `done` to the new bot, then run *Sprint Done Listener* again (or wait up to 10 minutes).
   Day 1 rows become `Done` in Notion and the bot confirms.

## Behaviour to know

- A reply starting with `done` closes **every** row of the lowest unfinished Day, so reply only
  when the whole day is finished. A missed night simply repeats the same day.
- Several `done` replies arriving in one poll close only **one** day (the SDE-75 listener would
  close one day per reply).
- Only replies from `TELEGRAM_CHAT_ID` are honoured.
- When no unfinished rows remain, the bot sends a completion message.

## During and after the sprint

- The SDE-75 reminder and the sprint reminder can run side by side: they use different bots, databases and state files, so neither affects the other. Expect two messages a night; reply `done` to each bot only for what you finished. To get a single message instead, disable *Nightly DSA Reminder* (Actions, workflow menu, *Disable workflow*) for the sprint and enable it again afterwards.
- Cleanup: disable both sprint workflows, delete the variable and the secret, archive the sprint
  database, revoke the bot with @BotFather (`/revoke`).

## Tests

`python -m unittest discover -s tests -v` (offline; Notion and Telegram are mocked).
