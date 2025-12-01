# 目的
`2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv` を元に、エスペラント→日本語の「最高の4択学習アプリ」を構築する。対象は日本語版のみ。`Unified_Level` を習得レベル管理に使う。

# 成果物の要件
- グループ分けロジック（品詞→レベル→サブレベル→20–30語目標のランダム分割、シード対応）
- 4択（最小2択）出題ロジックと1グループ内を出し切るクイズフロー
- 音声ファイル生成（RHVoice 利用、x表記のファイル名）と再生UI（自動再生＋速度調整）
- Streamlitフロントエンド（設定パネル、クイズ画面、結果画面、スコア保存）
- スコア計算（基礎点×レベル倍率＋連続正解＋精度ボーナス）、ローカル保存
- サンプル実行・検証手順

# データと前提
- CSV: `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv` 列: Esperanto, Japanese_Trans, Unified_Level ほか。
- 品詞判定は語尾＋例外辞書で行う。personal_pronoun と pronoun は統合して1品詞として扱う。それ以外の品詞混在は不可。
- ランダムシードは 1–8192 を推奨し、グループ分けと出題順に再現性を持たせる。

# グループ分け仕様
1. 品詞ごとに分割（名詞/形容詞/副詞/動詞/接続詞/前置詞/接頭辞/接尾辞/代名詞/原形副詞/数詞/人称代名詞/相関詞など）。personal_pronoun と pronoun は「pronoun」に統合する。
2. 各品詞内を `Unified_Level` 昇順で 55/65/120 の比率で 初級/中級/上級 に割り当て。
3. 初級・中級は3等分、上級は6等分してサブレベル化。
4. サブレベルごとに 20–30 語を目標にランダム分割（シード使用）。31–39語は等分2分割。20語未満は隣接サブレベルと結合し、それでも20未満なら単独グループで許容。
5. グループIDは `pos:sublevels:gX` のようにわかる形。

# 出題ロジック
- 1グループ内の全語を一巡させる `build_questions_for_group` を用意。options はグループ語数と4の小さい方、最小2択。
- 単発出題関数も用意してよいが、グループ完走型を優先。

# 音声
- RHVoice で一括生成するスクリプトを用意（例: `generate_audio_batch.py`）。先頭/末尾ハイフンや括弧内注釈は読み上げ前に除去するが、ファイル名は元の単語をエスペラントx表記にした `audio_key` を用いる（ŝipo→`sxipo.wav`）。
- 欠損検査と再生成用スクリプトも用意（例: `check_audio_gaps.py`）。欠損リスト表示と `--regen` で再生成。
- 音声ディレクトリは `audio/` をデフォルトにする。

# フロントエンド（Streamlit）
- サイドバー: ユーザー名、シード、品詞、グループ選択。「クイズ開始」で開始。
- 本画面: 単語提示、音声自動再生＋速度スライダー、2–4択の回答ラジオ。回答で正誤表示→次問。
- グループ完走後: 正答率、得点、内訳（基礎+難易度 / 精度ボーナス）表示。ローカル`scores.json`へ保存可。スコアルールをUIに明示。
- 監視設定: `.streamlit/config.toml` で `fileWatcherType="poll"` を指定（inotify制限回避）。

# スコア計算
- 基礎点: 10 × レベル倍率（初級1.0 / 中級1.5 / 上級2.0）
- 連続正解ボーナス: 2問目以降の連続正解1回につき +2
- 精度ボーナス: 最終正答率 × 問題数 × 2
- 保存するフィールド例: user, group_id, seed, correct, total, accuracy, points, raw_points, accuracy_bonus

# 実装ファイル例
- `vocab_grouping.py`: POS判定、グループ生成、問題生成（グループ一巡用）、audio_key生成。
- `generate_audio_batch.py`: RHVoice で一括生成（`--skip-existing`, `--limit`, `--no-clean` オプション）。
- `check_audio_gaps.py`: 欠損検査と再生成（`--regen`, `--no-clean`）。
- `app.py`: Streamlit アプリ本体。
- `.streamlit/config.toml`: fileWatcherType 設定。

# 推奨手順
1. 依存インストール: `pip install streamlit pandas`、RHVoice を導入（`RHVoice-test`が動くこと）。
2. 音声生成: `python generate_audio_batch.py --voice spomenka --skip-existing`（必要なら`--no-clean`）。
3. 欠損確認: `python check_audio_gaps.py --regen --voice spomenka` で欠損だけ補完。
4. アプリ起動: `streamlit run app.py`。サイドバーでシード・品詞・グループを選んでクイズを開始。

# 品質と検証
- `python -m compileall *.py` で構文チェック。
- グループ分布を確認し、<4語がないことを確認（personal_pronoun統合後はクリア）。
- UIから少なくとも1グループを完走し、音声再生とスコア表示を確認。

# その他の留意点
- 文字コードはUTF-8、非ASCIIはエスペラント文字に限定。
- シードで再現性を確保すること。
- 品詞混在は不可（例外: personal_pronoun+pronounのみ統合）。
