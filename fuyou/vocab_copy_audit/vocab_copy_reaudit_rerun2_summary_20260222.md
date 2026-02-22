# Re-Audit Rerun2 Summary (2026-02-22)

## Context (re-verified)
- Word quiz runtime CSV: `app.py:13` (`..._plajnova.csv`).
- Question generation uses `Esperanto` + `Japanese_Trans`: `vocab_grouping.py:286-287`, `vocab_grouping.py:523-564`.
- Display direction switch: `app.py:1019-1023`.
- Sentence quiz is separate (`sentence_app.py:13`).

## Checks
- Full strict checks on copy.csv: leakage 0 / empty 0 / mask artifact 0.
- 2501-2890 range: no candidates at threshold>=10.

## Manual findings (top3 per 100)
- keep: 25
- optional_medium: 26
- optional_low: 23
- No high-priority rule violation found in this rerun.
