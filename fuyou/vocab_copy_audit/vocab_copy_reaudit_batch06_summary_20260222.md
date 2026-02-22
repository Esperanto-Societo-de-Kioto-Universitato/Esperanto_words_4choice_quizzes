# Batch 06 Re-audit Summary (2026-02-22)

- Scope: rows 501-600 of `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Full rows:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch06_fullrows_20260222.tsv`
- Candidates:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch06_candidates_rerun_20260222.tsv`
- Adjudication:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch06_adjudication_20260222.tsv`

## Verdict Counts
- optional_medium: 8
- optional_low: 20
- keep: 6

## Integrity Check (Current CSV, rows 501-600)
- root leakage (JA/ZH/KO): 0 / 0 / 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0, 0, 0

## Key Notes
- Most proposals are conservative scope-expansions in ZH/KO to match existing JA breadth without over-editing.
- One notable wording risk: `harmonio` Chinese currently uses `谐音`, proposed as `和声，和谐；融洽` to avoid semantic confusion.
- This batch was adjudicated only; no direct write-back to `copy.csv` was performed in this step.
