# Verification

Checked on 4 November 2026, Asia/Tashkent.

## Dataset

Archive SHA-256: `88182bf4dad3569eea5fac611e8a16db7a455110fdaa6495650e7d87e09ac258`.

Imported 500,000 deals, 6,616 contracts, 14,392 participants, 120 brokers and 1,765 exchange rates. Original inspection found no duplicate deal IDs or missing contract, company, broker or rate references. The import validator checks these relationships on every rebuild.

## Automated checks

51 offline tests passed. They cover monetary values and lot calculations, date-specific conversion, blank delivery data, compound filters, region aliases, mixed currencies and units, forbidden SQL, strict tools, fabricated evidence IDs, false no-match claims, service failures, concurrent requests, Telegram splitting, update deduplication, restart recovery, chat ordering, ownership checks and command/reply handlers.

Lint and format checks passed. CI repeats offline checks on every push and builds the Python package without credentials or the full private dataset.

## Live model evaluation

Model: `gpt-6.1-sol`, medium reasoning, Responses API. Three concurrent requests.

| Set | Answerable | Safety/absence | Passed | P95 | Slowest |
|---|---:|---:|---:|---:|---:|
| Main bilingual set | 92 | 8 | 100/100 | 7.341 s | 12.023 s |
| Separate challenge set | 20 | 12 | 32/32 | 11.040 s | 11.206 s |

Expected values come from independent CSV processing with Python Decimal. The main set covers yearly counts, cancelled/completed states, currency conversion, turnover, buyer rankings, broker roles, exact sellers and unit prices. The challenge set adds warehouse regions, Uzbek Cyrillic, contract fields, calendar deadlines, partial and blank delivery, kg/tonne normalization, weighted sugar prices, fictitious companies, prompt injection, unsupported VAT/profit/live-price questions and incompatible dimensions.

The main set was used during development and fixes. The separate challenge set was generated afterward and passed on its first live run. These are finite prototype tests, not a guarantee about unseen judging questions. Numeric grading checks required values and outcome/language; it does not establish that every possible interpretation of a question is supported.

An earlier 12-question development run exposed over-restrictive year coverage and missing unpaid-cancellation definitions. Another smoke check exposed SQL AST handling of AND/OR. Those issues were corrected and the full main set rerun successfully. Failures are retained in local development reports rather than hidden from the development record.

## Telegram and deployment

Telegram getMe validated the token and confirmed `uzex21_bot` / `UZEX21`. The macOS restart service started successfully and its polling heartbeat passed the health check. No allowlist or additional sign-up is configured.

A separate Telegram account received a correct factual reply and reported a localization gap in descriptive values. Currency, unit, status, contract and classification values now use deterministic Uzbek translations; Russian replies translate Uzbek region names. Exact registered company and product names remain unchanged. Localization regression tests pass. A transient macOS service-reload race was fixed with bounded bootstrap retries and a regression test. The persistent job ledger confirms Telegram successfully delivered the factual reply, the Sources response and the CSV document to that account. Handler tests use a fake Telegram transport; live model tests use the real API and full dataset.

The Docker image built successfully. A non-root container with a read-only dataset read the full manifest and answered the seller question through the real API. All 118 evidence queries from the two live evaluation sets were replayed after SQL guard hardening with no result changes. The additional historical USD rate question for 31 October 2026 returned 13357.84 from usd_rates. Only one live polling instance runs during deployment tests.

## Remaining release requirements

- Keep the computer awake and online or move to an always-on server.
- Confirm the submission form, team contact details and post-submission-change rule with the organizers.
- Continue reviewing ambiguous questions and traces; zero observed fabrication is not proof that the model can never misinterpret a request.
