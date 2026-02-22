# Re-Audit RoundN Summary (2026-02-22)

## Context re-check
- Runtime word CSV path: `app.py:13` (`..._plajnova.csv`)
- Quiz generation uses `Esperanto` + `Japanese_Trans`: `vocab_grouping.py:286-287`, `vocab_grouping.py:523-564`
- Direction-based display: `app.py:1019-1023`

## Integrity checks (copy.csv)
- root leakage: 0
- empty cells: 0
- mask artifacts: 0
- bracket mismatch: 0
- `{Ｂ}` preserved

## Manual adjudication (top2 per 100 batches)
- keep: 44
- optional_medium: 2
- optional_low: 3
- high-priority issues: 0
