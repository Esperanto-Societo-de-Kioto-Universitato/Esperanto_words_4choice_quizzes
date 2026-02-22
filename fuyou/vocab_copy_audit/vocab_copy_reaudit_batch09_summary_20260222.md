# Batch 09 Re-audit Summary (2026-02-22)

- Scope: rows 801-900 of `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Full rows:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch09_fullrows_20260222.tsv`
- Candidates:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch09_candidates_rerun_20260222.tsv`
- Adjudication:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch09_adjudication_20260222.tsv`

## Verdict Counts
- optional_medium: 10
- optional_low: 21
- keep: 7

## High-attention Items (optional_medium)
- row 802 `kombini` (Chinese_Trans)
- row 815 `kompetenta` (Korean_Trans)
- row 825 `kondamni` (Korean_Trans)
- row 832 `konfidi` (Korean_Trans)
- row 835 `kongreso` (Korean_Trans)
- row 852 `konstitucio` (Korean_Trans)
- row 864 `kordo` (Korean_Trans)
- row 867 `koridoro` (Korean_Trans)
- row 879 `kovri` (Korean_Trans)
- row 887 `kredito` (Korean_Trans)

## Integrity Check (Current CSV, rows 801-900)
- root leakage (JA/ZH/KO): 0 / 0 / 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0, 0, 0

## Notes
- This batch is adjudication-only; no write-back to copy.csv was performed in this step.
- Proposals stay conservative: mostly KO scope restoration and style normalization, plus a few ZH wording corrections.
