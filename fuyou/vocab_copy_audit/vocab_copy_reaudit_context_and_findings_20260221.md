# Re-Audit Context & Findings (2026-02-21)

## Streamlit Context (code-grounded)
- Word quiz runtime CSV is fixed to `..._plajnova.csv` in `app.py` (`app.py:13`).
- `copy.csv` is therefore an audit/edit target unless `CSV_PATH` is switched.
- Quiz entries use `Esperanto` + `Japanese_Trans` only in `vocab_grouping.py` (`vocab_grouping.py:286-287`).
- UI prompt/options consume EO/JA (`app.py:1019-1023`).
- Sentence app is separate and uses phrase CSV (`sentence_app.py:13`).

## Current Dataset Health (`copy.csv`)
- Root leakage policy check: 0 remaining unmasked Esperanto-root tokens in JA/ZH/KO annotations.
- Hard mask artifacts previously fixed (`〜 〜`, `〜/〜`, `=〜 〜`) are currently 0.
- Remaining concern is mainly readability of some JA grammar notes after strict masking.

## Findings File
- `vocab_copy_reaudit_findings_roundX_20260221.tsv`
- Rows: 19
  - High (JA readability mask artifacts): 14
  - Medium (style/coverage): 5

## Recommendation
- Apply only the High group first (low semantic risk, mostly readability restoration without root leakage).
- Re-check root leakage after any apply pass.
- Keep Medium group optional to avoid overcorrection.
