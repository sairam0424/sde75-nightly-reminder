# Topics track: GenAI + Resume + Stories reminder (third bot)

A morning Telegram message (09:03 IST) with the day's GenAI topic, Resume topic and Stories
topic, each with recall questions, a read link and a task. Items from 3 and 7 days earlier
come back under "Recall". Replying `done` closes the day. It is independent of the SDE-75
and sprint reminders: own bot, own Notion database, own offset file.

The topic content lives in a private Notion database (it contains resume-defence notes),
not in this public repo. The repo only holds generic code.

## One-time setup

1. Create a third bot in BotFather, send it `/start` from your chat.
2. Add the Notion integration to the topics database (Connections). Siblings do not inherit it.
3. Repo settings: variable `TOPICS_DATA_SOURCE_ID`; secret `TOPICS_TELEGRAM_BOT_TOKEN`
   (`NOTION_TOKEN` and `TELEGRAM_CHAT_ID` are reused).
4. Run "Topics Done Listener" once (calibrates the offset, acts on nothing), then
   "Topics Morning Reminder", then reply `done`.

## Database schema (Notion)

`Name` (title), `Day` (number), `Slot` (number: 1 GenAI, 2 Resume, 3 Stories), `Status`
(status, with `Done`), `Kind` (select), `Questions` (text, one per line), `Task` (text),
`URL` (url). The reminder shows the lowest Day that still has a non-Done row.

## Tests

`python -m unittest discover -s tests -v` (offline, Notion and Telegram mocked).
