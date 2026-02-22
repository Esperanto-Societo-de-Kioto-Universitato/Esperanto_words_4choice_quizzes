# Re-Audit Rerun Summary (2026-02-22)

- Target: `fuyou/backup_2890_snapshots/... copy.csv`
- App context re-verified (`app.py`, `vocab_grouping.py`, `sentence_app.py`)
- Full strict checks: root leakage 0 / empty cells 0 / mask artifact 0
- Manual adjudication (top2 per 100 batches): keep=17, optional_medium=19, optional_low=14
- Note: proposals are suggestion-only; no CSV content was changed in this rerun.
- Scope-imbalance candidates in rows 2501-2890 (threshold >=8): 0
- High-priority policy violations in full 2890 rows: 0
