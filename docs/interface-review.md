# Interface review

Reviewed on 4 November 2026, Asia/Tashkent.

## Copy and formatting

Messages use short sentences and direct actions. The answer starts with the requested fields. A seller lookup does not add currency and quantity information. Dates and meaningful calculation context remain visible; full filters and source rows are available through Sources. Bold labels use Telegram HTML formatting. Source strings are escaped after plain text is split into messages, preventing both markup injection and broken formatting across chunks.

Authored interface strings use no en dashes or em dashes. Registered company names and identifier codes stay exactly as supplied. Product descriptions and attributes use a controlled Uzbek glossary. Original product names remain available in Sources and CSV. Telegram's usual menu controls provide navigation without repeating instructions under every answer.

Writing reference: [GOV.UK, Writing for user interfaces](https://www.gov.uk/service-manual/design/writing-for-user-interfaces).

## Languages and navigation

The first `/start` offers Uzbek and Russian. This is a preference, not an access gate: a question can be answered before a language is selected. Until selection, controls use the Telegram language where supported, with Uzbek as the default.

The selected language controls menus, examples, help and commands. Each question is answered in its own language, with explicit requests for Uzbek or Russian taking priority. Menu language is never passed as a forced answer-language override. Short follow-ups retain the prior answer language when appropriate.

The persistent keyboard contains Examples, Help, Language and New chat. The same actions are available through `/examples`, `/help`, `/language` and `/reset`, with `/menu` restoring the keyboard. Changing menu language preserves conversation history. New chat clears conversation history and preserves menu language. Existing stored preferences continue to work without a state migration.

Telegram references: [Keyboards and language support](https://core.telegram.org/bots/features), [Bot API formatting](https://core.telegram.org/bots/api#formatting-options).

## Sources and CSV

The supplied qualifying rules do not prescribe these buttons or a fixed CSV schema. Sources supports the criterion that the basis for an answer should be visible. CSV is a convenience export of the query result.

A question asking for a deal number, seller name and seller tax ID produces a three-column CSV. Other questions produce different columns. Aggregated answers export the computed result; they do not pretend to export every underlying deal. A caption gives row and column counts. The applicable row limit is stated when a result is truncated. Registry rows remain capped at 100. Directories use separate bounded limits so complete seller and broker lists can be returned. No extra columns or rows are invented to make an export look larger. Empty row results retain Sources and omit an empty CSV button.

## Rule assessment

Based on the task text supplied by the team, optional menus, language preferences and exports do not conflict with the qualifying requirements. The solution still answers Uzbek/Russian questions using only the supplied data, shows its evidence, requires no extra registration or payment from judges, and has a response deadline below 90 seconds.

The official task page at https://hackathon.uzex.uz/saralash/ remained inaccessible through the browsing tools. This assessment uses the supplied task text and does not claim an independent check of changed rules or the collapsed FAQ about post-submission edits.

## Verification

119 offline tests pass, including optional onboarding, persistent keyboards, language changes without history loss, cross-language questions, explicit language requests, whitespace input, HTML escaping, CSV shape and formula protection, and no empty CSV for absent records.

Four real API requests through the Telegram service path verified both cross-language menu combinations and both explicit answer-language overrides. The repeated main evaluation passed 100/100, with P95 26.035 seconds and maximum 27.500 seconds. The repeated challenge evaluation passed 32/32, with P95 12.189 seconds and maximum 12.969 seconds. All 20 safety cases passed. These are observed finite evaluations, not a guarantee for every unseen question.

An intermediate copy commit failed the format check. The following menu commit included the formatting correction and passed GitHub Actions. Final checks run again on the complete change.

## Complete deal responses

The user reported that an earliest-deal answer still exposed Russian grade/type descriptions and described the whole registry as the period of one deal. The display now translates product descriptions and attributes by source field. Company names, tax IDs, broker identifiers and brand codes remain exact. Descriptions use a fixed glossary; no per-answer generative translation is used. Numeric formatting retains precision and identifiers, removes unnecessary fractional zeros and groups large quantities. Detailed cards use sections for the deal, product, amounts, delivery, participants and contract dates. Empty attributes are listed together; duplicate derived values and internal source-row columns remain available in CSV or Sources.

For record selections, selected dates, currencies, units and samples follow the same order and limit as the returned records. Candidate count remains separate from selected record count. Aggregate query context remains unchanged. The exact question `eng birinchi bitim haqida barcha informatsiyani ber` passed a live API check in 5.968 seconds, returning deal 100001 dated 3 January 2022 with one selected deal. All 118 query results from the prior evaluation sets were replayed without value changes. Additional regression tests cover latest-deal source order, unchanged aggregate populations, raw CSV preservation, translated attributes, protected identifiers and negative fractional values. Typing feedback refreshes only while the question is being processed, with no artificial delay.

## List and file-request conversation

The supplied chat history exposed a real delivery gap: the first ten rows were repeated after requests for all 100 entries, and a named CSV request returned another preview. Lists now have Previous/Next buttons, with global row numbers and the stored result's total. Pagination checks ownership and page bounds and uses the same saved evidence without another model call. Large lists automatically attach a CSV with every stored result row. An explicit request for 100 entries exports 100; an unbounded directory request is no longer silently limited to 100.

Directory caps are participants 15000, contracts 7000, brokers 1000 and exchange rates 2000. Registry output remains capped at 100. Only 20 preview rows are passed back to the model; the application retains the complete bounded result for pagination and download.

Named requests for `brokers.csv` or `participants.csv` with a send/download action use a separate allowlisted path. CSVs are reconstructed from the imported source fields in original row order with original headings. They preserve all parsed source rows and columns, verified against the supplied archive: 120 brokers with four columns, and 14392 participants with six columns. User text cannot supply a filesystem path or SQL for this operation. Questions about a file's contents are not treated as download commands. Arbitrary filenames and traversal paths are rejected.

The exact live follow-up sequence passed: all sellers returned 392 rows; 'hamma 100 tasi kerak' returned 100 seller rows; '100 ta broker haqida hamma malumotni ber' returned 100 broker rows; the named brokers CSV request prepared all 120 source records. File delivery and pagination are also covered by transport-level tests, including cross-chat access denial, invalid files, distinct pages and complete attachment row counts.

## Greetings

Standalone Uzbek Latin, Uzbek Cyrillic and Russian greetings receive a short greeting and an invitation to ask a question about exchange deals. Assalomu alaykum receives Va alaykum assalom. Matching ignores case, ordinary punctuation and emoji. These replies do not use the model, clear history or change the menu preference. A greeting followed by an actual question continues through the normal answer engine. Regression tests cover both routing behaviors and preserved conversation history.
