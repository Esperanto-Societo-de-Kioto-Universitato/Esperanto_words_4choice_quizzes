# Batch 11 Optional Apply Summary (2026-02-22)

- Target file:
  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Backup before apply:
  `fuyou/backup_2890_snapshots/2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_apply_batch11_optionals_20260222_104117.csv`
- Source proposals:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch11_adjudication_20260222.tsv`
  (`optional_medium` + `optional_low` rows only)

## Applied
- Proposal rows: 27
- Proposal cells: 36
- Applied rows (newly changed): 27
- Applied cells (newly changed): 36
- Already-at-target cells: 0
- Column split (applied only): Chinese_Trans=13, Korean_Trans=23
- Detailed log:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_batch11_optionals_applied_20260222_104117.tsv`

## Post-check
- shape: 2890 x 9
- root leakage (JA/ZH/KO): 0 / 0 / 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0
- `{Ｂ}` in Japanese_Trans: preserved (2615 -> 2615)
