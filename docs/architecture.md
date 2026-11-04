# Architecture

UZEX21 answers questions about one frozen, fictional registry. It does not fetch live market prices or use model memory as a source of exchange facts.

## Data path

The importer reads the nine CSV files directly from the provided archive. Dates become typed dates, identifiers remain strings, and amounts use fixed-point decimals. Original source filenames and CSV row numbers are retained. Percent signs and spaced thousands are parsed explicitly. Import happens in a temporary database and replaces the active file only after validation.

The `registry` view contains exactly one row per deal. Contract, seller, buyer, broker and daily exchange-rate references are joined once in this view. Separate contract, company, broker and rate tables support questions without deals. Import rejects duplicate keys, missing references, invalid amounts and impossible delivered quantities.

`volume` is quantity in lots multiplied by lot size. `amount_uzs` converts USD using the supplied rate on the deal date. `mass_kg` normalizes kilograms and tonnes; it remains null for other units. Blank delivery fields stay null. Payment deadlines use calendar days from the deal; delivery deadlines use calendar days from payment.

## Model harness

The Responses API receives the schema, dataset coverage, business definitions and up to four previous conversation turns. Strict tools perform entity lookup, restricted queries, decimal ratios and finalization. The model has no shell, browser, arbitrary Python or database-write tool.

Names are resolved against actual source strings. Unicode normalization, Cyrillic transliteration and a small Uzbek product vocabulary help lookup; fuzzy suggestions are never proof of identity. Different grades and classes remain distinct. The model must clarify ambiguous identities.

SQL is parsed as an AST. One SELECT from one approved relation is allowed. Writes, external sources, schema-qualified tables, extensions, joins, subqueries, CTEs, HAVING, window functions, invented output constants and unapproved functions are rejected. Scope filters belong in WHERE so provenance covers the same records as the answer. A read-only DuckDB connection also disables external access and extension loading. Queries have an interruption timer, row cap and memory limit. Mixed currency or measurement-unit aggregates are rejected unless grouped or explicitly normalized.

Financial division uses Python Decimal with 50-digit calculation precision and explicit ROUND_HALF_UP display rounding. Model-provided numeric operands are not accepted: numerator and denominator must name columns in an executed result. Ratios, percentages and percentage changes are supported. SQL division and AVG are blocked.

The model cannot send a factual final answer as free text. It must reference an evidence ID issued by this request. The application renders source results through fixed Uzbek/Russian templates. Labels come from the executed SQL expressions, not model-written column aliases. Currency, units, status, contract types, classifications and region names use deterministic locale dictionaries; exact registered company and product names stay unchanged. This prevents the model from renaming a computed amount as a tax ID. Query validity alone does not establish that the model interpreted a question correctly; bilingual evaluation checks that separately.

Outcomes distinguish answer, no matching records, unavailable information, clarification and service failure. Empty lookups and tool errors cannot support a no-match claim. An API outage produces a service error, never a claim that the dataset has no answer.

The engine allows eight tool rounds, bounded API calls, query timeouts, four simultaneous questions and a 75-second overall deadline including queue waiting in Telegram. It never streams unchecked factual drafts.

## Telegram and durability

One long-polling process receives private messages and callbacks. Each update is committed to SQLite before its offset advances. Update IDs are unique. Jobs in a chat execute in order; other chats can run concurrently. Results are persisted before sending and multipart progress is tracked. Restarts recover unfinished jobs. Source and CSV callbacks verify the requesting chat owns the answer.

Telegram has no general idempotency key for sendMessage. A crash after Telegram accepts a message but before the local sent marker is saved can cause a repeated reply. Incoming updates and normal retries are deduplicated; absolute exactly-once external delivery is not claimed.

Menu language and conversation history are separate for each chat. The menu preference does not force answer language: answers follow the current question or its explicit Uzbek/Russian language request. First-start language selection is optional. A persistent keyboard provides examples, help, language selection and conversation reset. Messages use escaped Telegram HTML for bold labels. `/reset` clears conversation memory; operational job records remain local. Local files containing questions and results are ignored by Git. Logs contain request identifiers, timings, outcomes and sanitized errors; credentials are never logged. CSV export neutralizes spreadsheet formula prefixes.

The macOS LaunchAgent restarts the local process. Docker provides the same runtime for a Linux server. A local process lock prevents two instances sharing the same state directory. Health checks read the database and polling heartbeat without modifying job state.

## Defaults

Counts include all states unless asked otherwise. Turnover and average prices exclude cancelled deals unless explicitly included. An average unit price means a volume-weighted average in compatible units and currency. Source filters are visible through the Sources button.

Year-based questions refer to available registry records in that year, and answers show actual observed dates. Entirely unavailable periods are declined. An explicitly requested complete period beyond the snapshot needs clarification. Observed deal dates are not proof that trading occurred on every day between them.

The data snapshot is 30 October 2026. Relative dates use Asia/Tashkent. Questions about current fulfilment, current prices, predictions, company phone numbers, profit or cancellation reasons beyond the encoded unpaid status cannot be established from this dataset.

## References

- https://core.telegram.org/bots/api
- https://core.telegram.org/bots/faq
- https://docs.aiogram.dev/en/latest/dispatcher/long_polling.html
- https://developers.openai.com/api/docs/guides/function-calling
- https://developers.openai.com/api/docs/models/gpt-6.1-sol
- https://duckdb.org/docs/current/sql/data_types/numeric
