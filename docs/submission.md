# Submission draft

## Prototype

UZEX21: https://t.me/uzex21_bot

No allowlist, subscription, payment or additional registration is required. Judges open Telegram, press Start and ask questions in Russian or Uzbek.

## Solution description

UZEX21 is a bilingual Telegram assistant for the supplied fictional exchange registry. Python and aiogram handle Telegram. DuckDB stores the 500,000 deals, contract cards, participants, brokers and daily USD rates. Monetary values use exact decimal types. Answers include a source reference, record count and calculation where applicable. Long lists can be paged and attach a CSV; small answers attach one on request. Text-only requests suppress files.

The OpenAI Responses API interprets questions using strict tools. A required structured review checks missing details before querying; the bot asks targeted follow-up questions and remembers replies across restarts. The model can search actual entity names and request validated, read-only queries. It cannot write to the database, access external files, browse for facts or send an unchecked factual answer. Returned values are rendered by the application, with the filters behind them. Follow-ups use the complete stored result, and questions about a result are answered from its evidence. Unsupported questions, missing records, ambiguities and service failures have separate responses.

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
- Test from a separate Telegram account, including missing-detail follow-ups, CSV requests, text-only lists, language switching and reset.
- Confirm API billing and limits can handle evaluation traffic.
- The bot runs on the server in Docker and restarts by itself; the macOS service is disabled. Keep only one polling instance active.
- Confirm the FAQ rule about changes after submission; direct access to the official page returned HTTP 403 during research.
- Keep source private and do not share the team's implementation with other teams.
