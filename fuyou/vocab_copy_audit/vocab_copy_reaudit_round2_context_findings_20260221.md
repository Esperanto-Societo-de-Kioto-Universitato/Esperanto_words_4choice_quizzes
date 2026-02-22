# Re-Audit (Context + Findings) 2026-02-21

## 1) Streamlit app context (re-verified)
- 単語4択アプリの実運用CSVは `app.py:13` の
  `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv`。
- 語彙グループ化・出題データ生成は `vocab_grouping.py:280-301`, `vocab_grouping.py:523-564`。
  読み込んでいる主列は `Esperanto` と `Japanese_Trans`。
- 単語クイズ画面の出題表示は `app.py:1017-1023`。
  `ja_to_eo` では日本語注釈が問題文、`eo_to_ja` ではエスペラント語根が問題文。
- 例文クイズは別アプリ `sentence_app.py` で、別CSV `sentence_app.py:13` を使用。

## 2) 再審査対象
- 監査対象: `fuyou/backup_2890_snapshots/2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova copy.csv`
- 100件単位の再走査を継続し、未完了だった `2501-2890` を完了。

## 3) 完了した追加チェック
- 語根露出チェック（全2890件、JA/ZH/KO）
  - 新規検出: 1件（row 1832 `vazo`、JA注釈内 `sangovazo`）
- `2501-2890` の候補抽出
  - `vocab_copy_reaudit_batch26_29_candidates_20260221.tsv`: 3件
  - 2624 `kankro`, 2628 `karpo`, 2810 `skorpio`

## 4) 今回の追加所見（詳細）
- `fuyou/vocab_copy_audit/vocab_copy_reaudit_additional_findings_20260221.tsv`
  - high: 1件（語根露出ルール抵触）
  - optional_medium: 1件
  - optional_low: 2件

## 5) 方針
- high 1件は、クイズの答え漏れ防止ポリシーに直接関わるため優先修正推奨。
- optional 3件は、日中韓の語義バランス改善目的で、過修正を避ける最小追記案のみ提示。
