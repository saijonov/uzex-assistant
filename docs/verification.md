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

Offline results for the final code: 571 tests passed and 3 skipped because the small fixture lacks those products, with lint and format checks passing. The 403 new tests use a scripted model or no model. A full 500,000-deal import was built with the new importer, and the audit's correct queries were run through the real query layer. Their results match values calculated separately in DuckDB and by `scripts/build_hard.py` from the raw CSVs. An older dataset still loads under the new code, and the new dataset loads under the old code.

## Live runs after the fixes

All runs used the real service and full dataset, with Telegram replaced by a recorder. The earlier sets ran without a forced answer language for the first time.

The first low-cost run, on `gpt-6-luna` with low effort, passed 198 of 219 and exposed 21 failures: five wrong numbers stated as fact, ten unnecessary questions, two questions instead of refusals, two defensible readings and two expectations that were too strict. The wrong numbers were "excluding cancelled" read as "only cancelled" in three Uzbek turnover cases, a cancelled share of 100% and growth of 0%. The application did not stop them, so it gained checks that do not depend on the model.

Final low-cost run on the finished code:

| Set | Passed | P95 | Slowest |
|---|---:|---:|---:|
| Natural conversations (`hard.json`) | 95/96 | 9.959 s | 13.283 s |
| Main bilingual set | 99/100 | 5.729 s | 8.262 s |
| Challenge set | 32/32 | 9.063 s | 11.556 s |

The two failures vary between runs on this cheaper model. A price per kilogram of sugar filtered on `unit='килограмм'` and reported no records, although sugar is sold in tonnes. A question about January 2027 reported no matching records instead of the unavailable outcome, which invents nothing.

Production model run on `gpt-6.1-sol` with medium effort, covering 48 conversations chosen from the critical set and every earlier failure:

| Set | Passed | P95 | Slowest |
|---|---:|---:|---:|
| Selected conversations | 33/34 | 11.009 s | 12.804 s |
| Selected earlier cases | 14/14 | 12.095 s | 12.095 s |

The one failure was a false "name not found" for the inflected word `shakarning`. After that fix, six related conversations were rerun on the production model and all passed. The other 42 were not rerun after the last three small commits. The full 228 conversations have not been run on the production model, and no real Telegram account has tested this version. These are finite results, not a guarantee for unseen questions.

An earlier production run in this round reported 0 of 48. That was a defect in the temporary test script, not in the application: a variable name clash made every request fail after its first model call.

## Fifty tricky questions, live

`evaluation/tricky.json` holds 50 questions in Uzbek and Russian, 100 in all, built to break the harness and the model. Expected values were calculated directly from the data with joins and arithmetic the bot may not use. It also holds a replay of a real chat that had gone wrong. All runs use the real service and full dataset, with Telegram replaced by a recorder.

| Run | Model | Passed | P95 | Slowest |
|---|---|---:|---:|---:|
| First run | `gpt-6.1-sol`, medium | 88/100 | 12.138 s | 17.657 s |
| After the fixes | `gpt-6.1-sol`, medium | 100/100 | 13.441 s | 22.040 s |
| 18 affected questions on the final code | `gpt-6.1-sol`, medium | 18/18 | 18.866 s | 18.866 s |
| Chat replay, 8 turns | `gpt-6.1-sol`, medium | 8/8 | 12.960 s | 12.960 s |

The first run found: amounts shown with four decimals, unpaid totals that dropped cancelled deals, an exact company name still asked about, a city treated as a region to clarify, a named deposit metric asked about as a ranking, and a 2025 filter carried into a new question. Passing answers were also read by hand, which found goods counted from two different tables depending on the language and some unreadable condition labels.

Regression on the cheap model, `gpt-6-luna` with low effort: the natural conversations scored 85/96, the main set 99/100 and the challenge set 32/32. Of the 11 conversation failures, 5 were expected values that still had four decimals. Three were real regressions from these changes: `город Ташкент` searched in the address text and reported no records, `Dona` treated as a missing product, and sugar per kilogram reported as absent. Application checks were added for all three. Rerun on the production model, 10 of those 11 passed. The other still gets the right deal, but its first reply is a question about the unit recorded as `unavailable`. The main-set miss also passed on the production model.

Offline: 785 tests passed and 3 skipped, with lint and format checks passing. The dataset was reimported for `amount_usd` and the days fields.

Limits of these results. The 100/100 run came before the last two commits, and only the 18 affected questions were repeated afterwards. The questions were written before the code and then used to fix it, so this score is not an estimate for unseen questions. The natural, main and challenge sets were run in full only on the cheap model this round. No real Telegram account has tested this version, so multi-part messages have not been seen in the Telegram app.
