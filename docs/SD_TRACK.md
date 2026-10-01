# System design track: concept reminder (fourth bot)

A midday Telegram message (14:03 IST) with the day's system design concepts (Concept, HLD,
LLD and Resume-tie items), each with recall questions, a Notion/read link and a short task.
Items from 3 and 7 days earlier return under "Recall". Replying `done` closes the day.
Long days are split across several Telegram messages. It reuses the topics scripts
(`sd_reminder.py` and `sd_mark_done.py` are thin wrappers) with `SD_*` configuration: own bot,
own Notion database, own offset file.

The concept content lives in a private Notion database, not in this public repo.

## One-time setup

1. Create a fourth bot in BotFather; send it `/start` and one more message.
2. Add the Notion integration to the system design database (Connections).
3. Repo settings: variable `SD_DATA_SOURCE_ID`; secret `SD_TELEGRAM_BOT_TOKEN`
   (`NOTION_TOKEN` and `TELEGRAM_CHAT_ID` are reused).
4. Run "System Design Done Listener" once (calibrates the offset), then
   "System Design Reminder", then reply `done`.

## Database schema (Notion)

`Name` (title), `Day` (number), `Slot` (number), `Status` (status, with `Done`), `Kind`
(select: Concept, HLD, LLD, Resume-tie), `Questions` (text, one per line), `Task` (text),
`URL` (url).
