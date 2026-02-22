# Re-Audit Summary (2026-02-21)

## App Context (re-confirmed)
- Word quiz app uses `2890 ... _plajnova.csv` via `CSV_PATH` in `app.py` (`app.py:13`).
- `copy.csv` is not runtime input unless path is switched manually.
- Quiz entries are built from `Esperanto` + `Japanese_Trans` in `vocab_grouping.py` (`vocab_grouping.py:286-287`).
- Display logic uses EO/JA only (`app.py:1019-1023`).

## What was checked
- Full `copy.csv` (2890 rows) was re-audited for JA/ZH/KO annotation quality.
- Mechanical checks: root leakage, masking side effects, empty cells, bracket balance, readability patterns.
- Manual checks: high-risk rows with degraded readability and selected cross-language sense-balance rows.

## Applied in this pass (minimal)
- Applied file: `vocab_copy_reaudit_applied_20260221.tsv`
- Cells changed: 12
  - Japanese_Trans: 11
  - Chinese_Trans: 1
- Focus: fix clearly unnatural masked outputs without violating the "root must be shown only as 〜" rule.

## Validation after apply
- Remaining Esperanto root tokens in JA/ZH/KO annotations: 0
- Mask artifact patterns:
  - `〜 〜`: 0
  - `〜/〜`: 0
  - `=〜 〜 ...`: 0
- CSV integrity: readable, 2890 rows / 9 columns.

## Optional (not applied) proposals
- File: `vocab_copy_reaudit_optional_proposals_20260221.tsv`
- Count: 12
- Nature: mostly sense-expansion (not hard errors), held back to avoid overcorrection.

## Notes on current quality
- Hard leakage and obvious mask artifacts are controlled.
- Remaining `>>〜` / `=〜` patterns are mostly intentional cross-reference style under the masking policy.
- A small set of ZH/KO entries are semantically narrow vs JA; these are listed as optional expansions rather than forced fixes.
