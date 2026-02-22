# Batch 01-03 Optional Apply Summary (2026-02-22)

- Target file:
  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Backup before apply:
  `fuyou/backup_2890_snapshots/2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_apply_batch01_03_optionals_20260222.csv`
- Source proposals:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batches01_03_combined_20260222.tsv`

## Applied
- Target rows: 23
- Changed cells: 25
- Column split: Chinese_Trans=7, Korean_Trans=18
- Log:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch01_03_optionals_applied_20260222.tsv`

## Post-check
- shape: 2890 x 9
- root leakage (JA/ZH/KO): 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0
- `{Ｂ}` in Japanese_Trans: preserved
