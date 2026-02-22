# Root-Mask Validation (2026-02-21, cautious pass)

## Scope
- Target: `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Rule: Esperanto roots must appear in JA/ZH/KO annotations only as masked `〜` form.

## Backups
- `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_rootmask_fix_20260221.csv`
- `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_rootmask_lowprio_all_20260221.csv`

## Applied Changes
- Phase 1 (self-stem direct leak fix): `vocab_copy_rootmask_applied_20260221.tsv`
- Phase 2 (low-priority cross-reference sweep): `vocab_copy_rootmask_lowprio_applied_20260221.tsv`
- Phase 2 count: 210 cells / 262 token replacements
  - Japanese_Trans: 209 cells
  - Chinese_Trans: 1 cell
  - Korean_Trans: 0 cells

## Validation
- Remaining Esperanto root tokens in JA/ZH/KO (any token length): 0
- Consecutive placeholder issue (`〜〜`): 0
- Diff vs original plajnova.csv: 378 cells
  - JA 271, ZH 36, KO 71
- Diff vs before_rootmask_fix backup: 231 cells
- Diff vs before_lowprio backup: 210 cells

## Readability Watch (manual optional)
- Entries with denser masking patterns saved to `vocab_copy_rootmask_readability_watch_20260221.tsv`: 5 rows
- These are not policy violations; they are only candidates for later style polish.

## App Context
- Current vocabulary runtime still points to `..._plajnova.csv` in `app.py`. `copy.csv` is an audit/edit target unless the path is switched.