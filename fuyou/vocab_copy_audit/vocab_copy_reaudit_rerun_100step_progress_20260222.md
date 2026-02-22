# Re-Audit Rerun 100-Step Progress (2026-02-22)

- Strict checks over full 2890 rows: root leakage 0, empty cells 0, mask artifacts 0.
- Candidate extraction used scope-imbalance heuristics; this is advisory, not automatic error detection.
- Manual adjudication was done on top-2 candidates per active 100-row batch.

| Batch | Heuristic Candidates | Keep | Optional Medium | Optional Low |
|---|---:|---:|---:|---:|
| 1-100 | 5 | 1 | 0 | 1 |
| 101-200 | 6 | 1 | 1 | 0 |
| 201-300 | 7 | 1 | 1 | 0 |
| 301-400 | 16 | 0 | 1 | 1 |
| 401-500 | 12 | 0 | 1 | 1 |
| 501-600 | 14 | 0 | 0 | 2 |
| 601-700 | 10 | 1 | 1 | 0 |
| 701-800 | 14 | 0 | 1 | 1 |
| 801-900 | 9 | 0 | 1 | 1 |
| 901-1000 | 15 | 1 | 0 | 1 |
| 1001-1100 | 13 | 0 | 2 | 0 |
| 1101-1200 | 14 | 1 | 1 | 0 |
| 1201-1300 | 17 | 1 | 0 | 1 |
| 1301-1400 | 12 | 1 | 1 | 0 |
| 1401-1500 | 20 | 1 | 1 | 0 |
| 1501-1600 | 20 | 0 | 1 | 1 |
| 1601-1700 | 16 | 2 | 0 | 0 |
| 1701-1800 | 17 | 1 | 0 | 1 |
| 1801-1900 | 18 | 2 | 0 | 0 |
| 1901-2000 | 12 | 0 | 1 | 1 |
| 2001-2100 | 4 | 1 | 1 | 0 |
| 2101-2200 | 8 | 1 | 0 | 1 |
| 2201-2300 | 18 | 0 | 2 | 0 |
| 2301-2400 | 18 | 0 | 1 | 1 |
| 2401-2500 | 2 | 1 | 1 | 0 |
| 2501-2600 | 0 | 0 | 0 | 0 |
| 2601-2700 | 0 | 0 | 0 | 0 |
| 2701-2800 | 0 | 0 | 0 | 0 |
| 2801-2900 | 0 | 0 | 0 | 0 |
