# Batch 11 Re-audit Summary (2026-02-22)

- Scope: rows 1001-1100 of `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Full rows:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch11_fullrows_20260222.tsv`
- Candidates:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch11_candidates_rerun_20260222.tsv`
- Adjudication:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch11_adjudication_20260222.tsv`

## Verdict Counts
- optional_medium: 8
- optional_low: 19
- keep: 8

## High-attention Items (optional_medium)
- row 1008 `lukso` (Chinese_Trans)
- row 1015 `magazeno` (Chinese_Trans|Korean_Trans)
- row 1030 `mano` (Chinese_Trans|Korean_Trans)
- row 1033 `mapo` (Chinese_Trans|Korean_Trans)
- row 1041 `maso` (Korean_Trans)
- row 1043 `mastro` (Chinese_Trans|Korean_Trans)
- row 1072 `meti` (Chinese_Trans|Korean_Trans)
- row 1093 `mino` (Korean_Trans)

## Integrity Check (Current CSV, rows 1001-1100)
- root leakage (JA/ZH/KO): 0 / 0 / 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0, 0, 0

## Notes
- This batch is adjudication-only; no write-back to copy.csv was performed in this step.
- Proposals are conservative, focused on scope gaps and KO style normalization.
