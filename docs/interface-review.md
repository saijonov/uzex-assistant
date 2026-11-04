# Interface review

Reviewed on 4 November 2026, Asia/Tashkent.

## Copy and formatting

Messages use short sentences and direct actions. The answer starts with the requested fields. A seller lookup does not add currency and quantity information. Dates and meaningful calculation context remain visible; a short source reference appears in the answer and full filters and samples remain in local evidence. Bold labels use Telegram HTML formatting. Source strings are escaped after plain text is split into messages, preventing both markup injection and broken formatting across chunks.

Authored interface strings use no en dashes or em dashes. Registered company names and identifier codes stay exactly as supplied. Product descriptions and attributes use a controlled Uzbek glossary. Original product names remain available in CSV and local evidence. Telegram's usual menu controls provide navigation without repeating instructions under every answer.

Writing reference: [GOV.UK, Writing for user interfaces](https://www.gov.uk/service-manual/design/writing-for-user-interfaces).

## Languages and navigation

The first `/start` offers Uzbek and Russian. This is a preference, not an access gate: a question can be answered before a language is selected. Until selection, controls use the Telegram language where supported, with Uzbek as the default.

The selected language controls menus, examples, help and commands. Each question is answered in its own language, with explicit requests for Uzbek or Russian taking priority. Menu language is never passed as a forced answer-language override. Short follow-ups retain the prior answer language when appropriate.

The persistent keyboard contains Examples, Help, Language and New chat. The same actions are available through `/examples`, `/help`, `/language` and `/reset`, with `/menu` restoring the keyboard. Changing menu language preserves conversation history. New chat clears conversation history and preserves menu language. Existing stored preferences continue to work without a state migration.

Telegram references: [Keyboards and language support](https://core.telegram.org/bots/features), [Bot API formatting](https://core.telegram.org/bots/api#formatting-options).

## Sources and CSV

The supplied qualifying rules do not prescribe these buttons or a fixed CSV schema. The basis for an answer stays visible through its source reference, dates, record count and applicable calculation. CSV is a convenience export of the query result.

A question asking for a deal number, seller name and seller tax ID produces a three-column CSV. Other questions produce different columns. Aggregated answers export the computed result; they do not pretend to export every underlying deal. A caption gives row and column counts. The applicable row limit is stated when a result is truncated. Registry rows remain capped at 100. Directories use separate bounded limits so complete seller and broker lists can be returned. No extra columns or rows are invented to make an export look larger. Empty results send no file. New answers have no Sources or CSV buttons. A source reference appears inline.

## Rule assessment

Based on the task text supplied by the team, optional menus, language preferences and exports do not conflict with the qualifying requirements. The solution still answers Uzbek/Russian questions using only the supplied data, shows its evidence, requires no extra registration or payment from judges, and has a response deadline below 90 seconds.

The official task page at https://hackathon.uzex.uz/saralash/ remained inaccessible through the browsing tools. This assessment uses the supplied task text and does not claim an independent check of changed rules or the collapsed FAQ about post-submission edits.

## Verification

171 offline tests pass, including optional onboarding, persistent keyboards, language changes without history loss, cross-language questions, explicit language requests, whitespace input, HTML escaping, CSV shape and formula protection, and no empty CSV for absent records.

Four real API requests through the Telegram service path verified both cross-language menu combinations and both explicit answer-language overrides. The repeated main evaluation passed 100/100, with P95 26.035 seconds and maximum 27.500 seconds. The repeated challenge evaluation passed 32/32, with P95 12.189 seconds and maximum 12.969 seconds. All 20 safety cases passed. These are observed finite evaluations, not a guarantee for every unseen question.

An intermediate copy commit failed the format check. The following menu commit included the formatting correction and passed GitHub Actions. Final checks run again on the complete change.

## Complete deal responses

The user reported that an earliest-deal answer still exposed Russian grade/type descriptions and described the whole registry as the period of one deal. The display now translates product descriptions and attributes by source field. Company names, tax IDs, broker identifiers and brand codes remain exact. Descriptions use a fixed glossary; no per-answer generative translation is used. Numeric formatting retains precision and identifiers, removes unnecessary fractional zeros and groups large quantities. Detailed cards use sections for the deal, product, amounts, delivery, participants and contract dates. Empty attributes are listed together; duplicate derived values and internal source-row columns remain available in CSV or saved evidence.

For record selections, selected dates, currencies, units and samples follow the same order and limit as the returned records. Candidate count remains separate from selected record count. Aggregate query context remains unchanged. The exact question `eng birinchi bitim haqida barcha informatsiyani ber` passed a live API check in 5.968 seconds, returning deal 100001 dated 3 January 2022 with one selected deal. All 118 query results from the prior evaluation sets were replayed without value changes. Additional regression tests cover latest-deal source order, unchanged aggregate populations, raw CSV preservation, translated attributes, protected identifiers and negative fractional values. Typing feedback refreshes only while the question is being processed, with no artificial delay.

## List and file-request conversation

The supplied chat history exposed a real delivery gap: the first ten rows were repeated after requests for all 100 entries, and a named CSV request returned another preview. Lists now have Previous/Next buttons, with global row numbers and the stored result's total. Pagination checks ownership and page bounds and uses the same saved evidence without another model call. Lists longer than ten rows automatically attach a CSV with every stored result row, unless the user asks for text only. Small answers attach a CSV only on explicit request. An explicit request for 100 entries exports 100; an unbounded directory request is no longer silently limited to 100.

Directory caps are participants 15000, contracts 7000, brokers 1000 and exchange rates 2000. Registry output remains capped at 100. Only 20 preview rows are passed back to the model; the application retains the complete bounded result for pagination and download.

Named requests for `brokers.csv` or `participants.csv` with a send/download action use a separate allowlisted path. CSVs are reconstructed from the imported source fields in original row order with original headings. They preserve all parsed source rows and columns, verified against the supplied archive: 120 brokers with four columns, and 14392 participants with six columns. User text cannot supply a filesystem path or SQL for this operation. Questions about a file's contents are not treated as download commands. Arbitrary filenames and traversal paths are rejected.

The exact live follow-up sequence passed: all sellers returned 392 rows; 'hamma 100 tasi kerak' returned 100 seller rows; '100 ta broker haqida hamma malumotni ber' returned 100 broker rows; the named brokers CSV request prepared all 120 source records. File delivery and pagination are also covered by transport-level tests, including cross-chat access denial, invalid files, distinct pages and complete attachment row counts.

## Greetings

Standalone Uzbek Latin, Uzbek Cyrillic and Russian greetings receive a short greeting and an invitation to ask a question about exchange deals. Assalomu alaykum receives Va alaykum assalom. Matching ignores case, ordinary punctuation and emoji. These replies do not use the model, clear history or change the menu preference. A greeting followed by an actual question continues through the normal answer engine. Regression tests cover both routing behaviors and preserved conversation history.

## Clarification and file-delivery review

Every model request begins with a forced structured review. The application checks missing references, product-price dates and units, and ranking criteria before querying. Fixed Uzbek/Russian questions ask for the missing details. Ambiguous lookup results provide numbered choices from real records; queries cannot silently choose one. Pending questions survive restart and are isolated per chat. A new independent question replaces an unresolved one; greeting and menu actions preserve it.

Live service-path checks passed ten turns covering price period/unit clarification, a year-only count follow-up, abandoning an incomplete price question for a specific deal, explicit small CSV output, suppressing a large CSV and requesting a CSV before identifying the desired result. Another two-turn test distinguished Toshkent city from the region before calculating turnover. These checks used the real model and full database with a fake Telegram transport.

The revised main evaluation passed 100/100 and the final challenge evaluation 32/32. An intermediate challenge run returned clarification for a live-price question rather than unavailability. It invented no answer. A guard now rejects current/future prices beyond the historical dataset before asking pointless unit questions. The challenge set was rerun successfully. P95 was 13.206 seconds for the main set and 12.978 seconds for the final challenge set; the slowest response was 29.414 seconds. Finite test results cannot guarantee every unseen question.

Write `CSV qilib ber` or `Пришли CSV` after an answer to export its exact stored result. Without a valid latest result, the bot asks what to export. Text-only requests take precedence over automatic file delivery. Only pagination controls remain on new data answers; language selection and the bottom menu stay available. Old messages' export callbacks still work for their owner.

## Unnecessary clarification and random examples

The reported request `100ta random birja haqida to'liq malumot ber` was being treated as an unidentified single deal. The review instructions now distinguish list/example requests from single-record lookups. A count plus permission to choose any records is sufficient, with all available dates as the default. It does not require a tax ID, product, company or period. Existing explicit filters still apply, and ambiguous requested regions or identities still require clarification.

The application now has a bounded source-sampling tool. It draws actual identifiers once and keeps them fixed for source evidence, pagination and CSV. A 100-record full-detail answer contains 100 unique source deals and 62 fields per row. Both the original Uzbek request and a Russian equivalent passed real-model service-path tests. Follow-ups `100ta random, farqi yoq` and just `farqi yoq` also resolved the previous unnecessary identifier question. A normal ten-record list and all 120 brokers answered without extra questions. Missing-product prices, undefined best-broker rankings and ambiguous Toshkent calculations still asked the appropriate question. These nine checks use the real model and full dataset with a fake Telegram transport.

An initial test incorrectly required a ten-example request to use a deterministic order. A random selection is also valid when no order was requested. The assertion was corrected, and all nine scenarios were rerun successfully. The earlier local report is retained.
