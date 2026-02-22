# Batch 01-05 Optional Apply Summary (2026-02-22)

- Target file:
  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Backup before apply:
  `fuyou/backup_2890_snapshots/2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_apply_batch01_05_optionals_20260222_094713.csv`
- Source proposals:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batches01_05_combined_20260222.tsv`

## Applied
- Proposal rows: 53
- Proposal cells: 60
- Applied rows (newly changed): 30
- Applied cells (newly changed): 35
- Already-at-target cells: 25
- Column split (applied only): Chinese_Trans=13, Korean_Trans=22
- Detailed log:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch01_05_optionals_applied_20260222_094713.tsv`

## Post-check
- shape: 2890 x 9
- root leakage (JA/ZH/KO): 0 / 0 / 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0
- `{Ｂ}` in Japanese_Trans: preserved (2615 -> 2615)
