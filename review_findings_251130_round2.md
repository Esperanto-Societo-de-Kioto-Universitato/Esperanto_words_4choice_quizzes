# Review Findings (Round 2)

Target: `phrases_eo_en_ja_zh_ko_ru_fulfilled_251130.csv`
Focus: consistency and naturalness across Esperanto + JA/ZH/KO in sentence-app context.

## App context re-check
- `sentence_app.py` uses this CSV as source for phrase quiz.
- Quiz prompt/options are EO <-> JA, but same row quality affects user trust and future multilingual extensions.
- Phrase audio lookup depends on `PhraseID` + Esperanto text slug (`_phrase_audio_key`), so EO edits require corresponding audio updates.

## Additional high-confidence fixes applied
- `PhraseID 1978` (KO): `연결` -> `환승` for flight transfer semantics.
- `PhraseID 1989` (JA/ZH/KO): social "connection" wording -> transfer wording (`乗り継ぎ/转机/환승`).
- `PhraseID 2035` (JA/ZH/KO): baggage storage wording -> baggage weighing wording (`計量/称重/무게를 재다`) to match EO `pesi`.
- `PhraseID 2053` (ZH): `出租车站` -> `出租车乘车点` (taxi rank phrasing).
- `PhraseID 2479` (JA/KO): `停車駅/정차역` -> `停留所/정류장` to align with EO `haltejo`.
- `PhraseID 2484` (JA): `どの駅` -> `どの停留所` for `haltejo` consistency.
- `PhraseID 2491` (JA): stop-count phrasing unified to `停留所`.
- `PhraseID 2492` (JA): stop-count phrasing unified to `停留所`.
- `PhraseID 2499` (JA/ZH/KO): imperative sentence style -> noun label style for "Request stop" (`リクエストストップ/按需停靠站/요청 정차`).
- `PhraseID 2518` (KO): generic station wording -> "missed your stop on train" wording.
- `PhraseID 2536` (ZH): `出租车站` -> `出租车乘车点` for consistency with 2053.

## Regenerated change lists
- `corrections_list_251130_clean.tsv`
- `corrections_list_251130_eo_ja_zh_ko.tsv`
