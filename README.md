# SDE-75 Nightly Reminder

Sends a Telegram push notification every night at 10pm IST with the next 2
unfinished problems from the "SDE-75 Revision Tracker" Notion database.

Query logic: finds the lowest `Day` number where `Status != Done`, so it
self-corrects if you skip a night or get ahead of schedule.

## One-time setup (do this before the schedule will work)

1. **Create a Notion integration**: notion.so/my-integrations -> New
   integration -> capabilities: Read content only -> Save. Copy the secret
   token.
2. **Share the database with it**: open "SDE-75 Revision Tracker" in Notion
   -> "..." menu (top right) -> Add connections -> select the integration
   from step 1. Skipping this step is the #1 cause of "Could not find
   object" errors.
3. **Create a Telegram bot**: message @BotFather in Telegram -> `/newbot` ->
   follow the prompts -> copy the bot token. Then message your new bot once
   (e.g. "hi") - bots can't DM you first. Visit
   `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and read
   `result[0].message.chat.id` - that's your chat_id.
4. **Add repo secrets**: Settings -> Secrets and variables -> Actions on
   this repo, add `NOTION_TOKEN`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
5. **Test it**: Actions tab -> "Nightly DSA Reminder" -> "Run workflow" to
   trigger it manually and confirm the Telegram message arrives.

The schedule (`.github/workflows/nightly-dsa-reminder.yml`) then runs
unattended every night at 16:30 UTC (22:00 IST, no DST adjustment needed).
