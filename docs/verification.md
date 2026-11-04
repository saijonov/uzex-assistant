# Verification

Checked on 4 November 2026, Asia/Tashkent.

## Dataset

Archive SHA-256: `88182bf4dad3569eea5fac611e8a16db7a455110fdaa6495650e7d87e09ac258`.

Imported 500,000 deals, 6,616 contracts, 14,392 participants, 120 brokers and 1,765 exchange rates. Original inspection found no duplicate deal IDs or missing contract, company, broker or rate references. The import validator checks these relationships on every rebuild.

## Automated checks

171 offline tests passed. They cover monetary values and lot calculations, date-specific conversion, blank delivery data, compound filters, region aliases, mixed currencies and units, forbidden SQL, strict tools, fabricated evidence IDs, false no-match claims, service failures, concurrent requests, Telegram splitting, update deduplication, restart recovery, chat ordering, ownership checks and command/reply handlers.

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

A separate Telegram account received a correct factual reply and reported a localization gap in descriptive values. Currency, unit, status, contract and classification values now use deterministic Uzbek translations; Russian replies translate Uzbek region names. Exact registered company names and identifier codes remain unchanged. Product descriptions are translated for display, with the original source strings retained in saved evidence and CSV. Localization regression tests pass. A transient macOS service-reload race was fixed with bounded bootstrap retries and a regression test. The persistent job ledger confirms Telegram successfully delivered the factual reply, the Sources response and the CSV document to that account. Handler tests use a fake Telegram transport; live model tests use the real API and full dataset.

The Docker image built successfully. A non-root container with a read-only dataset read the full manifest and answered the seller question through the real API. All 118 evidence queries from the two live evaluation sets were replayed after SQL guard hardening with no result changes. The additional historical USD rate question for 31 October 2026 returned 13357.84 from usd_rates. Only one live polling instance runs during deployment tests.

## Remaining release requirements

- Keep the computer awake and online or move to an always-on server.
- Confirm the submission form, team contact details and post-submission-change rule with the organizers.
- Continue reviewing ambiguous questions and traces; zero observed fabrication is not proof that the model can never misinterpret a request.

## Menu and copy review

See [the interface review](interface-review.md) for optional onboarding, language behavior, CSV scope, rule assessment and the repeated 132-question evaluation. Four additional live requests verified that menu language does not force answer language, including explicit requests to switch the answer language.

## Structured review and delivery regression

After introducing required request review and persistent clarification state, the repeated main set passed 100/100 (92 answerable and 8 absence cases), P95 13.206 seconds and maximum 29.414 seconds. The final challenge run passed 32/32 (20 answerable and 12 safety cases), P95 12.978 seconds and maximum 14.488 seconds. An intermediate challenge run passed 31/32: a live-price question prompted for a unit instead of returning unavailable. No fabricated value was emitted. A current-price guard corrected that outcome and the whole challenge set was rerun.

Ten real-model service-path turns passed checks for period/unit follow-ups, isolated chat state, replacing a pending question, small explicit CSV, text-only large lists and CSV intent carried through clarification. A separate two-turn city/region clarification passed. Unit/transport tests also cover forced first-tool order, query bypass rejection, invented references, unresolved identity blocking, verified numbered choices, restart persistence, reset, export of stale/unavailable results, cancellation notes and removal of new export/source buttons. These service-path checks use a fake transport; they do not claim a new independent Telegram-account acceptance test after the button removal.

The updated wheel and source package built successfully. The rebuilt non-root Docker image answered the missing-product prompt through the real API with the expected clarification. The macOS service was restarted with the new code and its database and polling health check passed.

## Example requests and random selection

171 offline tests passed after adding random sampling and list-clarification regressions. The 20 added checks cover frozen identifiers and provenance, exact CSV rows, source filters and field selection, smaller/empty populations, every approved relation, bounded sizes, blocked SQL, unneeded identity/date questions and recovery from a previous unnecessary clarification.

Nine real-model service-path scenarios passed. The exact reported Uzbek request returned 100 deals and 62 fields per record; its Russian equivalent also returned 100 complete records. Both `100ta random, farqi yoq` and `farqi yoq` resolved a pending identifier question. An ordinary ten-record list and all 120 brokers needed no clarification. Missing product, ranking metric and city/region cases continued to clarify. These tests used a fake Telegram transport, not a new independent Telegram-account acceptance test.

The complete main set passed 100/100 (P95 11.145 seconds, maximum 17.100 seconds). The separate challenge set passed 32/32 (P95 13.111 seconds, maximum 17.065 seconds). All 20 safety/absence cases passed. The package and updated Docker image built successfully. The local service was restarted and its health check passed. A full-data formatting smoke check kept all 100 source rows and 62 columns in CSV; the first ten full cards were split into five messages with only a next-page control. These are finite development results, not a guarantee for every future question.

## Audit of real conversations and fixes

An audit replayed 113 natural conversations through the real service, model and full dataset, and compared results with separately calculated values. It found failures the earlier 132 cases could not detect: those cases contained no follow-ups, returned one row each, forced the answer language and used none of the query shapes that crashed.

Findings fixed afterwards:

| Finding | Evidence before the fix |
|---|---|
| `COUNT(DISTINCT ...)` crashed rendering | No reply after 69 seconds in Russian, a generic error after 82 seconds in Uzbek; also seen in the live log |
| City or region reply could not settle Toshkent | 0 of 11 attempts succeeded |
| Unit words such as `tonnada` and `в килограммах` were not recognised | The same question repeated |
| An invented filter value was reported as absence | `currency='USD'` produced "no records" |
| History was cut at 10,000 characters | A sum over 10 random deals used 6 |
| Spellings split rankings | The top product showed 11,798 instead of 23,881 |
| Query rules refused answerable questions | Median, groups over a threshold, buyers without deals, broker rankings |
| File intent matched word fragments | `nomini csv qilib ber` sent no file |

Offline results for the fixed code: 392 tests passed, lint and format checks passed. The 221 new tests use a scripted model or no model. A full 500,000-deal import was built with the new importer, and the audit's correct queries were run through the real query layer. Their results match values calculated separately in DuckDB and by `scripts/build_hard.py` from the raw CSVs. An older dataset still loads under the new code, and the new dataset loads under the old code.

**Not yet verified with the production model.** The prompt and the new about_previous_result tool change how the model behaves, and offline tests cannot show that it will use them as intended. No accuracy claim for `gpt-6.1-sol` should be made until these sets are rerun on it.

## Low-cost model run

All three sets ran through the real service and full dataset on `gpt-6-luna` with low reasoning effort, to limit spending. The earlier sets ran without a forced answer language for the first time. These results describe that cheaper model, not the production model.

| Set | Passed | P95 | Slowest |
|---|---:|---:|---:|
| Natural conversations (`hard.json`) | 73/87 | 10.358 s | 12.541 s |
| Main bilingual set | 97/100 | 8.413 s | 10.215 s |
| Challenge set | 28/32 | 8.026 s | 17.834 s |

The run used 673 requests, 4,475,952 input tokens (4,139,978 cached) and 33,534 output tokens, with no API errors.

The 21 failures:

| Group | Cases | What happened |
|---|---:|---|
| Wrong number stated as fact | 5 | "Excluding cancelled" read as "only cancelled" in three Uzbek turnover cases; a cancelled share of 100%; growth of 0% |
| Unnecessary question | 10 | Asked which product when the question named it (including `Shakar narxi`), asked city or region after `в городе Ташкент`, and asked for a record during a ranking |
| Question instead of refusal | 2 | Profit and paid VAT |
| Different but defensible reading | 2 | Median grouped by currency; Fergana counted by company registration instead of warehouse, with the filter shown in the answer |
| Expectation too strict | 2 | A correct share list ordered by region pushed the expected row to page two; a correct broker name without its code |

The application did not stop the wrong numbers, so they need checks that do not depend on the model.
