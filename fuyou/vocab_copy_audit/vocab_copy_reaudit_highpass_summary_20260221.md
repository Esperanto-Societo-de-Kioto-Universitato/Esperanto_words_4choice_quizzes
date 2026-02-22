# Re-Audit High-Priority Cautious Pass (2026-02-21)

## Scope
- Target: `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- Policy kept: Esperanto roots should not appear literally in JA/ZH/KO annotations.

## Backup
- `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.before_high14_readability_fix_20260221.csv`

## Applied
- Main high-priority fixes: `vocab_copy_reaudit_high14_applied_20260221.tsv` (14 JA cells)
- Tail cleanup fixes: `vocab_copy_reaudit_high14_tail_applied_20260221.tsv` (2 JA cells)
- Total in this pass: 16 JA cells

## Verification
- Root leakage (any token length): 0
- Mask artifact counts in JA:
  - `〜 〜`: 0
  - `〜/〜`: 0
  - `=〜 〜`: 0
- Remaining parenthesized tilde patterns: 2 (intentional/acceptable)

## Optional Remaining
- Medium items left unchanged to avoid overcorrection: 5
- Status file: `vocab_copy_reaudit_findings_roundX_status_20260221.tsv`

## Diff size
- vs pre-pass backup: JA 16 / ZH 0 / KO 0 (total 16)
