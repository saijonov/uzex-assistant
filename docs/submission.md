# Submission draft

## Prototype

UZEX21: https://t.me/uzex21_bot

No allowlist, subscription, payment or additional registration is required. Judges open Telegram, press Start and ask questions in Russian or Uzbek.

## Solution description

UZEX21 is a bilingual Telegram assistant for the supplied fictional exchange registry. Python and aiogram handle Telegram. DuckDB stores the 500,000 deals, contract cards, participants, brokers and daily USD rates. Monetary values use exact decimal types. Each answer has a Sources button containing the executed calculation, record count and original CSV references.

The OpenAI Responses API interprets questions using strict tools. The model can search actual entity names and request validated, read-only queries. It cannot write to the database, access external files, browse for facts or send an unchecked factual answer. Returned values are rendered by the application. Unsupported questions, missing records, ambiguities and service failures have separate responses.

Automated tests cover import integrity, financial calculations, mixed currencies and units, safe query execution, evidence ownership, isolated conversations, duplicate updates, restart recovery and Telegram handlers. A separate bilingual live evaluation compares answers against independent calculations from the original CSV files. See `docs/verification.md` for measured results and remaining release checks.

## Form information to provide

- Prototype URL: https://t.me/uzex21_bot
- Team name: 21
- Team leader: fill in name and phone number
- Team members: fill in up to three first and last names
- Technology/method description: adapt the description above

## Release checks

- Confirm the correct submission form through the official hackathon page or Telegram channel.
- Submit before 5 November 2026, 18:00 Asia/Tashkent; target internal release by 16:00.
- Test from a separate Telegram account, including Sources, CSV, language switching and reset.
- Confirm API billing and limits can handle evaluation traffic.
- Keep the computer awake and online or transfer to the server before judging.
- Keep only one polling instance active when moving between computer and server.
- Confirm the FAQ rule about changes after submission; direct access to the official page returned HTTP 403 during research.
- Keep source private and do not share the team's implementation with other teams.
