# Batch 10 Re-audit Summary (2026-02-22)

- Scope: rows 901-1000 of `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Full rows:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch10_fullrows_20260222.tsv`
- Candidates:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch10_candidates_rerun_20260222.tsv`
- Adjudication:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch10_adjudication_20260222.tsv`

## Verdict Counts
- optional_medium: 7
- optional_low: 22
- keep: 8

## High-attention Items (optional_medium)
- row 901 `krom` (Chinese_Trans|Korean_Trans)
- row 904 `kruco` (Korean_Trans)
- row 931 `kurso` (Korean_Trans)
- row 965 `laŭ` (Korean_Trans)
- row 968 `leciono` (Korean_Trans)
- row 989 `limo` (Korean_Trans)
- row 995 `litero` (Chinese_Trans)

## Integrity Check (Current CSV, rows 901-1000)
- root leakage (JA/ZH/KO): 0 / 0 / 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0, 0, 0

## Notes
- This batch is adjudication-only; no write-back to copy.csv was performed in this step.
- Proposals are conservative and focused on missing senses or Korean style normalization.
