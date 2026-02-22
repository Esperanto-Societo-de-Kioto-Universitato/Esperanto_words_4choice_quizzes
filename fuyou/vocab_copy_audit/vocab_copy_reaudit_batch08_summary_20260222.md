# Batch 08 Re-audit Summary (2026-02-22)

- Scope: rows 701-800 of `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Full rows:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch08_fullrows_20260222.tsv`
- Candidates:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch08_candidates_rerun_20260222.tsv`
- Adjudication:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch08_adjudication_20260222.tsv`

## Verdict Counts
- optional_medium: 13
- optional_low: 20
- keep: 5

## High-attention Items (optional_medium)
- row 704 `justa` (Chinese_Trans|Korean_Trans)
- row 708 `kabineto` (Korean_Trans)
- row 710 `kaduka` (Korean_Trans)
- row 714 `kajo` (Korean_Trans)
- row 724 `kampo` (Korean_Trans)
- row 726 `kandelo` (Chinese_Trans|Korean_Trans)
- row 732 `kapo` (Chinese_Trans)
- row 741 `karto` (Korean_Trans)
- row 744 `kaso` (Korean_Trans)
- row 764 `kerno` (Korean_Trans)
- row 778 `klara` (Korean_Trans)
- row 780 `klaso` (Korean_Trans)
- row 800 `komandi` (Korean_Trans)

## Integrity Check (Current CSV, rows 701-800)
- root leakage (JA/ZH/KO): 0 / 0 / 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0, 0, 0

## Notes
- This batch is adjudication-only; no write-back to copy.csv was executed in this step.
- Proposals are conservative: mainly scope restoration and wording naturalness corrections.
