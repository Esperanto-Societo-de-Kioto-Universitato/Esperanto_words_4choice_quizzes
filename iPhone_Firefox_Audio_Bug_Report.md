# iPhone Firefox 音声再生バグ - 調査・対策ドキュメント

## 問題の概要

### 症状
- **発生環境**: iPhone + Firefox（Streamlit Cloud上のデプロイ版）
- **現象**: 問題が切り替わった際に、**前の問題の単語の音声が再生される**
- **特徴**:
  - 特に**素早く回答したとき**に顕著
  - 画面上部の出題単語と、音声プレイヤー表示の`audio_key`は**一致している**のに、再生される音声が異なる
  - 手動で再生ボタンを押しても、**前の単語の音声が再生される**
  - iframe内のデバッグ表示「🎵 iframe内音声: XXX」と画面上部の出題単語が**異なっている**

### PC版への影響
- **PC版は全く問題なし** - 対策がPC版のパフォーマンスに影響を与えてはならない

---

## 技術的背景

### アプリの構造
- **フレームワーク**: Streamlit
- **音声プレイヤー**: `st.components.v1.html()`でカスタムHTML/JavaScript を埋め込み
- **音声形式**: Base64エンコードされたWAVファイル（RHVoice TTS）

### Streamlitの制約
- `st.components.v1.html()`は各呼び出しで**個別のiframe**を生成
- iframeは互いに**隔離されたスコープ**を持つ
- **重要**: `st.components.v1.html()`は`key`パラメータを**サポートしていない**
  - 試行時に`TypeError: html() got an unexpected keyword argument 'key'`が発生

### 問題の根本原因（推定）
1. 正解時に`st.rerun()`で画面が再描画される
2. Streamlitが新しいiframeを生成するが、**古いiframeがDOMに残っている時間がある**
3. 古いiframeのJavaScriptが先に実行され、音声を再生してしまう
4. または、古いiframeが画面に表示されたまま、ユーザーがそれを操作してしまう

---

## 試みた対策（時系列順）

### 1. sessionStorageによるオーディオアンロック状態の追跡
- **目的**: モバイルブラウザの自動再生制限を解除
- **実装**: ユーザーの最初のタップでサイレント音声を再生し、`sessionStorage`に記録
- **結果**: 自動再生自体は可能になったが、音声の不一致問題は解決せず

### 2. question_index を使用したトラッキング
- **目的**: 各問題を一意に識別
- **実装**: `audio_id`に`question_index`を含める（例: `audio-q3-abc12345`）
- **結果**: 効果なし

### 3. 親ウィンドウスコープでのグローバル変数管理
- **目的**: iframe間で状態を共有
- **実装**:
  ```javascript
  let parentWin = window.parent || window;
  parentWin._esperantoLatestTimestamp = myTimestamp;
  parentWin._esperantoCurrentAudioId = currentAudioId;
  ```
- **結果**: 部分的に効果あり、しかし完全な解決には至らず

### 4. タイムスタンプベースの排他制御
- **目的**: 古いiframeの音声再生をブロック
- **実装**:
  ```javascript
  parentWin._esperantoBlockOldAudio = myTimestamp;

  function isLatest() {
    if (parentWin._esperantoLatestTimestamp > myTimestamp) return false;
    if (parentWin._esperantoCurrentAudioId !== currentAudioId) return false;
    if (parentWin._esperantoBlockOldAudio > myTimestamp) return false;
    return true;
  }
  ```
- **結果**: 効果なし

### 5. 遅延オーディオ要素生成（Lazy Creation）
- **目的**: audio要素を最初から作らず、再生時に動的生成
- **実装**:
  ```javascript
  function createAudio() {
    if (!isLatest()) return null;
    // ... audio要素を動的に生成
  }
  ```
- **結果**: 効果なし

### 6. `key`パラメータの使用（失敗）
- **目的**: Streamlitにiframeの再利用を防がせる
- **試行**: `st.components.v1.html(html, height=190, key=f"audio_{q_index}")`
- **結果**: **TypeError発生** - `st.components.v1.html()`は`key`をサポートしていない

### 7. モバイル向け遅延時間の増加
- **目的**: 新しいiframeが完全に準備できるまで待機
- **実装**:
  ```javascript
  const delay = isMobile ? 150 : 50;
  setTimeout(() => {
    // 1回目チェック
    if (isMobile) {
      setTimeout(() => {
        // 2回目チェック（追加100ms）
        attemptAutoplay();
      }, 100);
    }
  }, delay);
  ```
- **結果**: 効果なし

### 8. ブロックフラグによる古いaudioの即座ブロック
- **目的**: 古いiframeが`play()`を呼んでも無視
- **実装**: `parentWin._esperantoBlockOldAudio`フラグ
- **結果**: 効果なし

### 9. デバッグ表示の追加
- **目的**: 問題の原因特定
- **実装**:
  1. Python側: `st.caption(f"🔊 発音を聞く（自動再生）【{audio_key}】")`
  2. iframe内: `<div class="audio-debug-label">🎵 iframe内音声: XXX</div>`
- **発見**: **画面上部の出題単語と、iframe内の音声表示が異なっている**ことを確認

### 10. 古いiframeの自動非表示（hideIfNotLatest）
- **目的**: 古いiframeを見えなくする
- **実装**:
  ```javascript
  function hideIfNotLatest() {
    if (!isLatest()) {
      document.querySelector('.audio-card').style.display = 'none';
    }
  }
  setInterval(hideIfNotLatest, 100);  // 最初の1秒間
  ```
- **結果**: 効果なし（1秒間では不十分）

### 11. 監視頻度と期間の改善
- **目的**: より積極的に古いiframeを検出・非表示
- **実装**:
  ```javascript
  // 最初の500msは30ms間隔、その後は200ms間隔で最大10秒間監視
  const fastCheckInterval = setInterval(() => {
    if (hideIfNotLatest() || checkCount > 16) {
      clearInterval(fastCheckInterval);
      // 低頻度チェックに切り替え
    }
  }, 30);
  ```
- **結果**: 効果なし

### 12. 親ウィンドウにクリーンアップ関数リストを登録
- **目的**: 新しいiframeが古いiframeに直接非表示を指示
- **実装**:
  ```javascript
  if (!parentWin._esperantoCleanupFunctions) {
    parentWin._esperantoCleanupFunctions = [];
  }

  function hideMyself() {
    document.querySelector('.audio-card').style.display = 'none';
    if (a) { a.pause(); a.src = ''; }
  }

  // 古いクリーンアップ関数を全て実行
  oldFunctions.forEach(fn => fn());
  parentWin._esperantoCleanupFunctions = [hideMyself];
  ```
- **結果**: 効果なし

### 13. destroyAllOtherAudio()の強化
- **目的**: 古いiframe内のaudio-cardも非表示にする
- **実装**:
  ```javascript
  iframes.forEach((iframe) => {
    const iframeDoc = iframe.contentDocument;
    // カードを非表示
    iframeDoc.querySelectorAll('.audio-card').forEach(card => {
      if (iframeDoc !== document) card.style.display = 'none';
    });
    // audioを破棄
    iframeDoc.querySelectorAll('audio').forEach(audio => {
      audio.pause(); audio.src = ''; audio.remove();
    });
  });
  ```
- **結果**: 効果なし（おそらくCORS制限で他のiframeにアクセスできない）

### 14. 単語名チェックの追加
- **目的**: タイムスタンプだけでなく、単語名でも一致を確認
- **実装**:
  ```javascript
  parentWin._esperantoCorrectWord = debugAudioKey;

  function isLatest() {
    if (parentWin._esperantoCorrectWord !== debugAudioKey) return false;
    // ...
  }
  ```
- **結果**: 効果なし

### 15. 初期化直後の遅延チェック
- **目的**: 新しいiframeが変数を設定した直後に古いiframeが自分を隠す
- **実装**:
  ```javascript
  setTimeout(() => {
    if (parentWin._esperantoCorrectWord !== debugAudioKey) hideMyself();
  }, 10);
  setTimeout(() => {
    if (parentWin._esperantoCorrectWord !== debugAudioKey) hideMyself();
  }, 50);
  ```
- **結果**: 効果なし

### 16. ボタンクリック時の最新チェック
- **目的**: 古いiframeのボタンを押しても何も起きないようにする
- **実装**:
  ```javascript
  btn.onclick = () => {
    if (!isLatest()) {
      hideMyself();
      return;
    }
    // ...
  };
  ```
- **結果**: 効果なし

### 17. createAudio()に二重チェック追加
- **目的**: audio要素作成前に単語名を再確認
- **実装**:
  ```javascript
  function createAudio() {
    if (!isLatest()) { hideMyself(); return null; }
    if (parentWin._esperantoCorrectWord !== debugAudioKey) {
      hideMyself(); return null;
    }
    // ...
  }
  ```
- **結果**: 効果なし

---

## 現在の状況

### 確認されている事実
1. **画面上部の出題単語**と**Python側の`audio_key`表示**は**一致している**
2. **iframe内のデバッグ表示**が上記と**異なる**ことがある
3. これは**古いiframeが画面に表示されている**ことを意味する
4. JavaScript側の対策は全て**効いていない**

### 考えられる原因
1. **Streamlitの再描画タイミング**: 新しいiframeが作成される前に、古いiframeのJavaScriptが実行されている
2. **CORS制限**: 異なるiframe間でのDOM操作がセキュリティ制限で失敗している可能性
3. **iPhone Firefox特有の挙動**: 他のブラウザ（Chrome、Safari）では自動再生自体がブロックされるため問題が顕在化しない

---

## 未試行のアプローチ案

### 1. Streamlit標準の`st.audio`を使用
- `st.components.v1.html()`を使わず、Streamlit標準の`st.audio()`を使用
- **懸念**: 再生速度調整などカスタム機能が失われる可能性

### 2. iframeを使わないアプローチ
- `st.markdown()`で`<audio>`タグを直接埋め込み
- **懸念**: JavaScriptの制御が難しくなる

### 3. 音声URLをサーバーから提供
- Base64ではなく、静的ファイルURLを使用
- **懸念**: Streamlit Cloudでの静的ファイル配信の制限

### 4. Web Audio APIの使用
- HTML Audio要素ではなく、Web Audio APIで再生
- **懸念**: 実装が複雑になる

### 5. iPhone Firefox専用のフォールバック
- 自動再生を諦め、常に手動再生ボタンを表示
- **懸念**: ユーザー体験の低下

---

## 関連コード箇所

### `audio_player()` 関数
- ファイル: `app.py`
- 行番号: 約 375〜950行

### 主要なJavaScript変数（親ウィンドウに保存）
```javascript
parentWin._esperantoLatestTimestamp    // 最新iframeのタイムスタンプ
parentWin._esperantoCurrentAudioId     // 最新iframeのaudio ID
parentWin._esperantoBlockOldAudio      // ブロックフラグ
parentWin._esperantoCorrectWord        // 正しい単語名
parentWin._esperantoCorrectAudioSrc    // 正しい音声データ
parentWin._esperantoCleanupFunctions   // クリーンアップ関数リスト
```

### 主要なJavaScript関数
```javascript
isLatest()           // 自分が最新かチェック
hideMyself()         // 自分を非表示にする
hideIfNotLatest()    // 最新でなければ非表示
destroyAllOtherAudio() // 他のaudioを破棄
createAudio()        // audio要素を動的生成
attemptAutoplay()    // 自動再生を試みる
```

---

## 制約条件

1. **PC版への影響禁止**: 「角を矯めて牛を殺すようなことは絶対避けてほしい」
2. **出題速度の維持**: 「出題速度遅くなったりしたら絶対に嫌」
3. `st.components.v1.html()`の`key`パラメータは使用不可

---

## 参考情報

### リポジトリ
- **名前**: Esperanto_words_4choice_quizzes
- **オーナー**: Takatakatake
- **ブランチ**: main

### デプロイ環境
- Streamlit Cloud

### 作成日
- 2024年11月26日

---

## 解決策（最終的に成功した方法）

### 18. Signal Iframe + LocalStorage 連携（成功）

これまでの失敗から、**「iframe間の直接通信（`window.parent`経由）は、iPhone Firefoxの厳格なiframe分離ポリシーやキャッシュ挙動によって信頼できない」** という結論に至りました。
そこで、ブラウザの永続ストレージである `localStorage` を「通信バス」として利用するアーキテクチャに変更しました。

#### 仕組みの概要
1. **Signal Iframe（司令塔）**:
   - 音声プレイヤーとは別に、軽量な「Signal Iframe」を `height=0` で注入します。
   - このiframeはHTML/CSSのレンダリング負荷がほぼゼロで、メインの音声プレイヤーよりも**圧倒的に早くロードされます**。
   - 役割はただ一つ、**「今再生すべき正しい音声キー」を `localStorage` に書き込むこと**です。

2. **LocalStorage（通信バス）**:
   - `localStorage` は同一オリジン（ドメイン）内の全てのiframeで共有されます。
   - ここに `esperanto_audio_target_{session_id}` というキーで、正しい音声キーが保存されます。

3. **Audio Player（監視者）**:
   - メインの音声プレイヤー（重いiframe）は、起動時および定期的に `localStorage` を監視します。
   - **自爆ロジック**: もし `localStorage` に書かれているキーが、自分の持っているキーと**異なる**場合、即座に：
     - 音声を停止 (`pause()`)
     - 音声ソースを空にする (`src = ""`)
     - 自分自身を非表示にする (`display: none`)
     - 処理を終了する
   - これにより、画面上に残ってしまった「ゴーストiframe」は、新しい問題（Signal Iframe）がロードされた瞬間に、自分が用済みであることを悟り、即座に自決します。

#### なぜこれで直ったのか？
- **通信の確実性**: `window.parent` 変数はiframeのライフサイクルやメモリ管理の影響を受けやすく、特にモバイルブラウザでは不安定でした。一方、`localStorage` はブラウザレベルで管理されるため、iframeの状態に関わらず確実に値を共有できます。
- **速度差の利用**: Signal Iframeは極めて軽量なため、重い音声プレイヤーがロードされて再生準備が整うよりも**前に**、確実に `localStorage` を更新できます。これにより、ゴーストiframeが「再生開始」する前に「停止命令」を受け取ることが可能になりました。
- **ゾンビプロセスの排除**: 以前のアプローチでは「新しいプレイヤーが古いプレイヤーを消す」ことを試みていましたが、アクセス権の問題で失敗していました。今回は「古いプレイヤーが自分で自分を消す（自律的な自爆）」方式にしたため、外部からの干渉が不要になり、確実に動作するようになりました。

#### 副次的効果
- **PC版への影響なし**: LocalStorageの読み書きは極めて高速なため、PC版のパフォーマンスには一切影響を与えませんでした。
- **セッション分離**: `session_id` を導入したため、ユーザーが複数のタブでアプリを開いても、それぞれのタブで独立して正しく動作するようになりました。
