# UZEX21

A Telegram assistant from team 21 for the UZEX qualifying challenge. It answers Uzbek and Russian questions about the supplied fictional registry, shows source evidence and declines unsupported questions.

Bot: https://t.me/uzex21_bot

Start with `/start` to choose a menu language, or ask a question immediately. The bottom menu has examples, help, language selection and a new conversation. Answers follow the question language, including an explicit request for Uzbek or Russian. Answers include a short source reference and the filters they applied. If a necessary detail is missing, the bot asks once and remembers your reply; `farqi yo‘q` or `неважно` accepts the defaults. Follow-ups use the complete stored result, and questions about it, such as `bu to‘liq malumotmi?` or `buni qanday hisobladingiz?`, are answered in words. Example and random-list requests do not require an identifier: `100ta random birja haqida to‘liq ma’lumot ber` returns 100 source deals with full details. Lists have Previous/Next buttons. Results longer than ten rows attach a CSV; small results attach one only when requested. Ask for text only to suppress a file, or write `CSV qilib ber` / `Пришли CSV` to export the latest answer. Excel requests receive the same CSV. Ask for `brokers.csv` to receive all 120 brokers with the original source columns.

## Local setup

Install Python 3.12 and uv, then run:

```sh
uv sync --locked
cp .env.example .env
chmod 600 .env
```

Fill in `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` in `.env`. Never commit this file. The default model is `gpt-6.1-sol` with medium reasoning; API billing is separate from a chat subscription.

Put the original `uzex_spot_data.zip` in the project root:

```sh
make import
make test
make bot
```

On macOS, install the local restart service instead of running a foreground bot:

```sh
PYTHONPATH=src uv run uzex install-service
make health
```

The service starts at login and restarts after failures. It does not keep a sleeping computer online. Keep the computer awake during judging, for example with `caffeinate -i` in a separate terminal. Logs are in `var/bot.log`.

Stop or restart the macOS service:

```sh
launchctl bootout gui/$(id -u)/uzex21.assistant
PYTHONPATH=src uv run uzex install-service
```

Use only one polling instance for the token. The importer must not replace the dataset while the bot is running. Stop the bot before reimporting.

The import builds derived fields such as merged product names, so after updating to a version that changes them, stop the bot, run `make import` and start it again:

```sh
launchctl bootout gui/$(id -u)/uzex21.assistant
make import
PYTHONPATH=src uv run uzex install-service
make health
```

Do not keep `data/registry.duckdb` open in a database tool such as Beekeeper Studio while the bot runs. A writable connection locks the file and every data question fails until it closes. Inspect a copy, or connect read-only.

## Checks and evaluation

```sh
make test
PYTHONPATH=src uv run uzex ask 'Кто продавец по сделке 100001?'
PYTHONPATH=src uv run uzex evaluate
PYTHONPATH=src uv run uzex evaluate --cases evaluation/challenge.json --output reports/challenge.json
PYTHONPATH=src uv run uzex evaluate --cases evaluation/hard.json --category critical --output reports/hard-critical.json
PYTHONPATH=src uv run uzex evaluate --cases evaluation/hard.json --output reports/hard.json
PYTHONPATH=src uv run uzex evaluate --cases evaluation/tricky.json --output reports/tricky.json
```

`evaluation/hard.json` holds natural multi-turn conversations, run through the real service with Telegram replaced by a recorder and graded on the text and files a user receives. The `critical` category is a low-cost subset of 20 conversations covering the main failures found so far. `evaluation/tricky.json` holds 50 questions in both languages built to break the harness and the model. Live evaluation spends API credits.

Offline tests use a small sample of the supplied fictional CSVs. Full live evaluation requires the original imported dataset and funded API access. Expected values are calculated independently from CSVs by `scripts/build_evaluation.py`, `scripts/build_challenge.py` and `scripts/build_hard.py`; they are not generated from model answers. Runtime reports and chat state are excluded from Git. Read [verification results](docs/verification.md) before making accuracy claims.

## Server deployment

On a Linux Docker host, copy the project, `.env` and prepared `data/` directory. Prepare writable state for the container user:

```sh
sudo install -d -o 10001 -g 10001 var
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 50 bot
```

Stop the local macOS instance before starting the server instance. Keep credentials out of image build arguments and source control. The container runs as user 10001, mounts the dataset read-only and stores jobs in the persistent `var/` directory. Docker health checks verify the dataset and polling heartbeat.

## Documentation

- [Architecture and calculation rules](docs/architecture.md)
- [Verification results and limits](docs/verification.md)
- [Interface and qualifying-rule review](docs/interface-review.md)
- [Submission description and checklist](docs/submission.md)

All companies, tax IDs, rates and amounts are fictional. The deals cover 3 January 2022 through 30 October 2026. Exchange rates separately cover 1 January 2022 through 31 October 2026. No live market predictions are provided.
