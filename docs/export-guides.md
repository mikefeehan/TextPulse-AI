# Export Guide

## iMessage / Apple Messages
Recommended order:
1. If the user has a Mac that syncs Messages, quit the Messages app and copy `~/Library/Messages/chat.db`.
2. If the user only has the iPhone, create an encrypted Finder or iTunes backup, then extract `chat.db`.
3. If they want the least technical option, use iMazing and export the thread or database there.

In the app:
1. Create the contact profile first.
2. Upload the `chat.db` file in the import hub.
3. Let TextPulse scan the database and surface likely one-to-one threads.
4. Choose the person from the suggested list, then confirm the import.

Notes:
- Quitting Messages before copying `chat.db` gives the cleanest live-Mac snapshot.
- The app can inspect the Apple Messages database and help the user choose the person, so they do not need to know the exact phone number in advance.

## WhatsApp
1. Open the chat.
2. Use `More` -> `Export Chat`.
3. Choose `Without Media` for the cleanest import.
4. Upload the exported `.txt` file.

## Telegram
1. Use Telegram Desktop and open `Settings` -> `Advanced` -> `Export Telegram data`.
2. Export the target conversation in JSON format.
3. Upload the resulting JSON file.

## Instagram DMs
1. Use `Download Your Information`.
2. Choose the `messages` dataset in JSON format.
3. Upload the conversation JSON from `messages/inbox/`.

## Android SMS Backup & Restore
1. Export messages from the SMS Backup & Restore app.
2. Upload the generated XML file.

## Generic CSV / TXT
1. Ensure each row includes a timestamp, sender, and message body.
2. Upload the file through the import hub.
3. Use paste import if the transcript is easier to copy than export.

## Screenshot OCR
1. Upload one or more screenshots from the conversation.
2. Keep the crop tight so bubbles and timestamps are readable.
3. Review the parsed preview before merging into the timeline.
