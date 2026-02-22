# Batch 07 Re-audit Summary (2026-02-22)

- Scope: rows 601-700 of `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Full rows:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch07_fullrows_20260222.tsv`
- Candidates:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch07_candidates_rerun_20260222.tsv`
- Adjudication:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch07_adjudication_20260222.tsv`

## Verdict Counts
- optional_medium: 13
- optional_low: 15
- keep: 7

## High-attention Items (optional_medium)
- row 613 `horizonto` (Korean_Trans)
- row 618 `humana` (Chinese_Trans)
- row 620 `humila` (Chinese_Trans)
- row 634 `ilustri` (Chinese_Trans)
- row 642 `imuna` (Korean_Trans)
- row 656 `injekti` (Chinese_Trans|Korean_Trans)
- row 660 `insigno` (Chinese_Trans|Korean_Trans)
- row 663 `instali` (Chinese_Trans|Korean_Trans)
- row 667 `instrumento` (Chinese_Trans|Korean_Trans)
- row 674 `interesi` (Chinese_Trans|Korean_Trans)
- row 676 `interpreti` (Chinese_Trans|Korean_Trans)
- row 688 `izoli` (Korean_Trans)
- row 695 `jen` (Chinese_Trans)

## Integrity Check (Current CSV, rows 601-700)
- root leakage (JA/ZH/KO): 0 / 0 / 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0, 0, 0

## Notes
- This step is adjudication only. No write-back to copy.csv was executed.
- Proposals are conservative and focused on scope gaps or wording naturalness.
