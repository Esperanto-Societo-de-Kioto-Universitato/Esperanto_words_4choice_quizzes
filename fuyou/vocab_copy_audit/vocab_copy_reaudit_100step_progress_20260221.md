# Re-Audit 100-Step Progress (2026-02-21)

## Method
- Reviewed with 100-row batch framing.
- For each batch:
  - root leakage check (Esperanto root literal exposure)
  - mask-artifact check (`〜 〜`, `〜/〜`, etc.)
  - scope-imbalance check (JA vs ZH/KO information density)
- Then manual adjudication to avoid overcorrection.

## App Context (re-verified)
- Runtime word quiz CSV: `app.py:13` (`..._plajnova.csv`).
- `copy.csv` is audit/edit target unless path is switched.
- Quiz content fields: `Esperanto` + `Japanese_Trans` (`vocab_grouping.py:286-287`, `app.py:1019-1023`).

## Current global status (`copy.csv`)
- Root leakage rows: 0
- Batch-level machine candidates: 55 rows
- Candidate adjudication (`vocab_copy_reaudit_all55_adjudication_20260221.tsv`):
  - keep: 27
  - optional_medium: 16
  - optional_low: 12

## Batch progress
- Batch 1-100: reviewed (1 candidate)
- Batch 101-200: reviewed (2 candidates)
- Batch 201-300: reviewed (2 candidates)
- Batch 301-400: reviewed (1 candidate)
- Batch 401-500: reviewed (2 candidates)
- Hot batches (high machine-candidate density): reviewed
  - 1201-1300
  - 1401-1500
  - 1701-1800
  - 2201-2300
  - 2301-2400

## Notes
- Most remaining candidates are scope expansion opportunities, not hard errors.
- No destructive/global rewrite is recommended.
- Continue with 100-row manual passes for remaining unreviewed blocks.
