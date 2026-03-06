# 音声整合確認レポート

作成日: 2026-03-06

## 対象

- 例文CSV: `phrases_eo_en_ja_zh_ko_ru_fulfilled_251130.csv`
- 例文音声: `Esperanto例文5000文_収録音声/`
- 単語CSV: `2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv`
- 単語音声: `audio/`

## 結論

- 例文音声: **5000 / 5000 exact**
- 単語音声: **2890 / 2890 exact**

現時点で、アプリ内で使われるエスペラント例文・エスペラント単語と音声ファイルの整合性は取れている。

追加検証も実施した。

- 例文音声: **5000 / 5000 が exact で存在**
- 例文音声: **5000 / 5000 が可読**
- 単語音声: **2890 / 2890 が exact で存在**
- 単語音声: **2890 / 2890 が可読**
- 日本語版・中国語版・韓国語版の文章アプリは、すべて同じ音声キー生成規則と同じ音声ディレクトリ設定を使っている

## 例文音声

### 実施前

- exact: 4876
- prefix fallback: 124
- missing: 0

`PhraseID` 接頭辞フォールバックで旧音声を再利用していた 124 件について、表示文と読み上げ内容が一致しない可能性があった。

### 実施内容

- 差し替え候補一覧を作成:
  - `phrases_audio_replacement_candidates_20260306.csv`
- 置換音声生成スクリプトを追加:
  - `tools/generate_phrase_audio_replacements.py`
- 124件の新規音声を生成:
  - `phrases_audio_replacement_generation_20260306.csv`
- 旧音声124件を退避:
  - `Esperanto例文5000文_収録音声/archived_replaced_audio_20260306/`
  - `Esperanto例文5000文_収録音声/archived_replaced_audio_20260306/moved_files.csv`

### 実施後

- exact: 5000
- legacy: 0
- prefix: 0
- missing: 0

### 可読性検証

例文音声は全件についてファイルの存在だけでなく、実際に読み込めるかも確認した。

- `.wav` は Python `wave` でフレーム数 > 0 を確認
- `.mp3` / `.ogg` は `ffprobe` でストリーム存在を確認

結果:

- bad audio: 0
- format: `.wav` 5000件

## 単語音声

単語側は `vocab_grouping._default_audio_key()` によるキー生成と `audio/` 内の音声ファイル名が全件一致していた。

### 実施結果

- exact: 2890
- missing: 0

### 可読性検証

単語音声も同じ基準で全件確認した。

結果:

- bad audio: 0
- format: `.wav` 2890件

### 単語側のキー重複について

単語音声は 2890 件すべて exact 一致しているが、音声キーの一意数は 2884 だった。

これは不整合ではなく、次のような**表記違いが同じ音声キーに正規化される**ため。

- `fi` / `fi!`
- `ha` / `ha!`
- `he` / `he!`
- `ho` / `ho!`
- `ve` / `ve!`
- `-i` / `-i-`

いずれも発音上は同一扱いで問題ないと判断した。

## アプリ実装の一致確認

次の3ファイルについて、文章音声まわりの実装が揃っていることを確認した。

- `sentence_app.py`
- `sentence_app_Cxina_versio.py`
- `sentence_app_Korea_versio.py`

確認項目:

- `PHRASE_AUDIO_DIR = BASE_DIR / "Esperanto例文5000文_収録音声"`
- `vg._default_audio_key(phrase)` を使う
- `PhraseID` 接頭辞ベースの prefix fallback を持つ

現状は全件 exact のため、fallback は残っていても実運用では使われない。

## 補足

- 例文アプリ側の `find_phrase_audio()` には `PhraseID` ベースの互換フォールバックが残っている。
- ただし現在は全件 exact に揃っているため、実運用で旧音声へ落ちることはない。
- 旧音声は削除せず、退避フォルダへ移動済み。
- 今回の検証は**ファイル名・キー・可読性・アプリ検索ロジック**の観点では十分厳密に確認している。
- ただし、**音声の発話内容そのものをASRで文字起こしして照合**する検証までは行っていない。そこまでやるなら別途音声認識系の検証工程が必要。
