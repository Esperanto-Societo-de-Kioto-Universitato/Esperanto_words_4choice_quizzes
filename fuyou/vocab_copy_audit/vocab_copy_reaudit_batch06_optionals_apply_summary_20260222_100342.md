# Batch 06 Optional Apply Summary (2026-02-22)

- Target file:
  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Backup before apply:
  `fuyou/backup_2890_snapshots/2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_apply_batch06_optionals_20260222_100342.csv`
- Source proposals:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch06_adjudication_20260222.tsv`
  (`optional_medium` + `optional_low` rows only)

## Applied
- Proposal rows: 28
- Proposal cells: 38
- Applied rows (newly changed): 28
- Applied cells (newly changed): 38
- Already-at-target cells: 0
- Column split (applied only): Chinese_Trans=11, Korean_Trans=27
- Detailed log:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch06_optionals_applied_20260222_100342.tsv`

## Post-check
- shape: 2890 x 9
- root leakage (JA/ZH/KO): 0 / 0 / 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0
- `{Ｂ}` in Japanese_Trans: preserved (2615 -> 2615)
