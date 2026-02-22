# Optional-Low12 Recheck (2026-02-21)

## Rule Gate
- Mandatory rule: Esperanto roots must appear only as `〜` in JA/ZH/KO annotations.
- Proposal leak check file: `vocab_copy_reaudit_optional_low_leakcheck_20260221.tsv`
- Result: 0 proposal strings contain literal Esperanto roots.

## Decision policy
- Low-priority set was reviewed one-by-one.
- To avoid overcorrection, this pass applies no low-priority edits directly.
- Kept items remain unchanged; proposal-only items are suggestions for future optional refinement.

## Decision file
- `vocab_copy_reaudit_optional_low12_adjudication_20260221.tsv`
  - `keep`: 5
  - `proposal_only`: 7
  - `applied_now`: all `no`

## Current dataset safety
- Root leakage in current `copy.csv`: 0
- No change was applied in this low-priority pass.
