# Post-Audit Optional 18 Apply Summary (2026-02-22)

- Target file:
  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Backup before apply:
  `fuyou/backup_2890_snapshots/2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_apply_postaudit18_20260222.csv`
- Source proposals:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_postapply_all49_top2_per100_adjudication_20260222.tsv`
  (`optional_medium` + `optional_low` rows only)

## Applied
- Target rows: 18
- Changed cells: 25
- Column split: Chinese_Trans=14, Korean_Trans=11
- Detailed log:
  `fuyou/vocab_copy_audit/vocab_copy_reaudit_postapply18_applied_20260222.tsv`

## Post-check
- shape: 2890 x 9
- Esperanto root leakage (JA/ZH/KO): 0
- empty cells (JA/ZH/KO): 0 / 0 / 0
- mask artifacts (`〜 〜`, `〜/〜`, `=〜 〜`): 0
- `{Ｂ}` in Japanese_Trans: preserved
