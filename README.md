# SDE-75 Nightly Reminder

Two small GitHub Actions workflows that turn a Notion database of DSA
practice problems into a nightly Telegram habit-tracker:

- **Nightly DSA Reminder** — every night, sends a Telegram message with the
  next 2 unfinished problems from a Notion database (a "SDE-75"-style
  revision tracker: one row per problem, with `Day`, `Slot`, `Status`,
  `Name`, `Topic`, `Pattern`, `Difficulty`, `URL` properties).
- **Telegram Done Listener** — polls every 10 minutes for a reply of
  "done" in that same Telegram chat, and if found, marks the active day's
  rows `Done` in Notion directly — no need to go back into Notion by hand.

## How it decides what to send

Rather than computing "today's day number" from a fixed start date (which
goes stale the moment you skip a night or get ahead), both scripts query
Notion for the **lowest `Day` number where `Status != Done`**. That means:

- Skip a night → the same pair gets sent again until you clear it.
- Get ahead of schedule → the reminder immediately reflects the next
  genuinely-unfinished day.
- Reply "done" → the listener marks exactly that active day complete and
  the very next scheduled reminder moves on.

## Cost

**$0, and not "free within a monthly quota" — genuinely unlimited.**
GitHub Actions minutes on `ubuntu-latest` runners are metered only for
*private* repositories (2,000 min/month on the Free plan, shared across
your whole account). Public repositories get unlimited free minutes on
standard runners. This repo is public specifically so its ~150 tiny job
runs/day (mostly the 10-minute listener poll) never compete with your
other private repos' CI budget.

## Architecture

```
GitHub Actions (cron)              GitHub Actions (cron, every 10 min)
        |                                    |
        v                                    v
scripts/nightly_reminder.py         scripts/mark_done.py
   query Notion (lowest              query Telegram getUpdates
   unfinished Day) --> Telegram      --> if "done" reply seen -->
   sendMessage                       PATCH Notion pages to Status=Done
```

Both scripts talk directly to the Notion REST API and the Telegram Bot
API via plain HTTP (`requests`) — no SDKs, no server, no persistent
process. The listener's only piece of state is
`state/telegram_offset.json`, a single integer (the last processed
Telegram `update_id`), committed back to the repo after each poll so it
never reprocesses an old message.

## One-time setup

This repo is wired to one specific personal Notion database
(`DATA_SOURCE_ID` is hardcoded in both scripts). To use it yourself:

1. **Fork this repo**, then replace `DATA_SOURCE_ID` in
   `scripts/nightly_reminder.py` and `scripts/mark_done.py` with your own
   Notion data source ID. Your database needs matching properties: `Name`
   (title), `Day` (number), `Slot` (number), `Status` (status, with a
   `Done` option), `Topic` (select), `Pattern` (rich text), `Difficulty`
   (select), `URL` (url).
2. **Create a Notion integration**: notion.so/my-integrations -> New
   integration -> capabilities: Read content only (the listener needs
   write too - Notion internal integrations get whatever capabilities you
   pick at creation, so pick Read+Update content). Copy the secret token.
3. **Share your database with it**: open your database in Notion -> "..."
   menu (top right) -> Add connections -> select the integration from
   step 2. Skipping this step is the #1 cause of "Could not find object"
   errors.
4. **Create a Telegram bot**: message @BotFather in Telegram -> `/newbot`
   -> follow the prompts -> copy the bot token. Then message your new bot
   once (e.g. "hi") - bots can't DM you first. Visit
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and read
   `result[0].message.chat.id` - that's your chat_id.
5. **Add repo secrets**: Settings -> Secrets and variables -> Actions,
   add `NOTION_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
6. **Make the repo public** (Settings -> General -> Danger Zone -> Change
   visibility) if you want the unlimited-minutes benefit described above.
   Not required for correctness - only for cost, and only relevant if
   your account's private-repo Actions minutes are shared with other
   busy repos.
7. **Test both workflows**: Actions tab -> pick each workflow -> "Run
   workflow", then confirm in your Telegram chat.

## Adjusting the schedule

`nightly-dsa-reminder.yml`'s cron is currently `23 14 * * *` (14:23 UTC =
19:53 IST) - deliberately an off-peak minute (not `:00`/`:15`/`:30`/`:45`,
which see the heaviest queueing across all of GitHub's scheduled
workflows) and a couple of hours before a 10pm solving window, so a
modest queue delay still lands before you start. GitHub does not
guarantee exact-time delivery for scheduled workflows; if it's
consistently landing later than expected, move the configured time
earlier and/or try a different off-peak minute.

`telegram-done-listener.yml` polls every 10 minutes
(`*/10 * * * *`) - safe to make more or less frequent since it's now
running on a public repo with no minutes budget to protect.

## Known limitations

- **"Done" only, no partial completion.** Replying "done" marks *both*
  of that night's problems complete. There's no built-in way to mark just
  one via chat - do that directly in Notion if you only finished one.
- **No retry queue.** If the Telegram API or Notion API is briefly down
  during a scheduled run, that run fails and waits for the next
  scheduled trigger (nightly reminder: next night; listener: next 10-min
  poll) rather than retrying immediately.
- **Personal, not general-purpose.** The hardcoded Notion property names
  (`Name`, `Day`, `Slot`, `Status`, `Topic`, `Pattern`, `Difficulty`,
  `URL`) must match your database exactly, or Notion property lookups
  will `KeyError`.
