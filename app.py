import base64
import json
import datetime
import random
import uuid
from pathlib import Path
from string import Template

import streamlit as st
import pandas as pd

import vocab_grouping as vg

# パス設定
CSV_PATH = Path("merged_esperanto_vocab_completed.csv")
AUDIO_DIR = Path("audio")
SCORE_FILE = Path("scores.json")

# スコア設定
BASE_POINTS = 10
STAGE_MULTIPLIER = {
    "beginner": 1.0,
    "intermediate": 1.3,  # 格差縮小: 1.5→1.3
    "advanced": 1.6,      # 格差縮小: 2.0→1.6
}
# 連続正解ボーナス: 2問目以降の連続正解1回あたり加算 (さらに半減: 1.0→0.5)
STREAK_BONUS = 0.5
# 最終精度ボーナス: accuracy * 問題数 * この値 (増加: 4.0→5.0)
ACCURACY_BONUS_PER_Q = 5.0
# 殿堂入りライン
HOF_THRESHOLD = 1000000

POS_JP = {
    "noun": "名詞",
    "verb": "動詞",
    "adjective": "形容詞",
    "adverb": "副詞",
    "preposition": "前置詞",
    "conjunction": "接続詞",
    "prefix": "接頭辞",
    "suffix": "接尾辞",
    "correlative": "相関詞",
    "numeral": "数詞",
    "bare_adverb": "原形副詞",
    "pronoun": "代名詞",
    "other": "その他",
}

STAGE_JP = {
    "beginner": "初級",
    "intermediate": "中級",
    "advanced": "上級",
}


@st.cache_data
def load_groups(seed: int):
    return vg.build_groups(CSV_PATH, seed=seed, audio_key_fn=vg._default_audio_key)


from streamlit_gsheets import GSheetsConnection


# -------- Google Sheets 連携 --------
# ローカルのJSONではなく、Google Sheetsをデータベースとして使用する
# 事前に .streamlit/secrets.toml に認証情報を設定する必要がある

def get_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"Google Sheets 接続の初期化に失敗しました: {e}")
        return None

def load_scores():
    """Google Sheetsからスコアを読み込む"""
    conn = get_connection()
    if conn is None:
        st.session_state.score_load_error = "Google Sheets 接続を初期化できませんでした。"
        return []
    try:
        # ワークシート "Scores" からデータを読み込む
        # API制限（1分間に60リクエスト）を回避するため、キャッシュ有効時間を設定
        # ttl=60秒（1分間は再取得せずキャッシュを使う）
        df = conn.read(worksheet="Scores", ttl=60)
        st.session_state.score_load_error = None
        if df.empty:
            return []
        # DataFrameを辞書のリストに変換
        return df.to_dict(orient="records")
    except Exception as e:
        # エラー時はユーザーに通知せず静かに空リストを返す（頻繁なエラー表示を防ぐ）
        # st.error(f"ランキングデータの読み込みに失敗しました: {e}")
        print(f"Ranking load error: {e}")
        st.session_state.score_load_error = f"ランキングの取得に失敗しました: {e}"
        return []

def save_score(record: dict):
    """Google Sheetsにスコアを追記する"""
    conn = get_connection()
    if conn is None:
        return False
    try:
        # 現在のデータを読み込む（書き込み時は最新状態が必要なので ttl=0）
        # ただし、頻繁な書き込みは想定していないため、ここでのAPI消費は許容する
        df = conn.read(worksheet="Scores", ttl=0)
        if df is None or df.empty:
            df = pd.DataFrame()

        # 新しいレコードをDataFrame化して結合
        new_row = pd.DataFrame([record])
        updated_df = pd.concat([df, new_row], ignore_index=True)

        # 更新（追記）
        conn.update(worksheet="Scores", data=updated_df)

        return True
    except Exception as e:
        st.error(f"スコアの保存に失敗しました: {e}")
        return False


def update_user_stats(user: str, points: float, ts: str):
    """UserStatsシート（累積スコア）を更新する"""
    conn = get_connection()
    if conn is None:
        return

    try:
        # UserStatsシート読み込み
        try:
            stats_df = conn.read(worksheet="UserStats", ttl=0)
        except Exception:
            # シートがない場合などは空DF扱い
            stats_df = pd.DataFrame(columns=["user", "total_points", "last_updated"])

        if stats_df is None or stats_df.empty:
             # もしUserStatsが空なら、既存のScoresから再構築（マイグレーション）
             scores_df = conn.read(worksheet="Scores", ttl=0)
             if scores_df is not None and not scores_df.empty:
                 # 集計
                 agg = scores_df.groupby("user")["points"].sum().reset_index()
                 agg.columns = ["user", "total_points"]
                 agg["last_updated"] = datetime.datetime.utcnow().isoformat()
                 stats_df = agg
             else:
                 stats_df = pd.DataFrame(columns=["user", "total_points", "last_updated"])

        # ユーザーの行を探す
        if user in stats_df["user"].values:
            # 更新
            idx = stats_df.index[stats_df["user"] == user][0]
            current_total = float(stats_df.at[idx, "total_points"])
            stats_df.at[idx, "total_points"] = current_total + points
            stats_df.at[idx, "last_updated"] = ts
        else:
            # 新規追加
            new_row = pd.DataFrame([{"user": user, "total_points": points, "last_updated": ts}])
            stats_df = pd.concat([stats_df, new_row], ignore_index=True)

        # 保存
        conn.update(worksheet="UserStats", data=stats_df)
        return True
    except Exception as e:
        print(f"UserStats update error: {e}")
        return False


def load_rankings():
    """ランキング用データをUserStatsから読み込む"""
    conn = get_connection()
    if conn is None:
        return []
    try:
        df = conn.read(worksheet="UserStats", ttl=60)
        if df is None or df.empty:
            # UserStatsが空の場合、Scoresから復旧を試みる（初回移行用）
            scores = load_scores()
            if scores:
                # ここでは簡易的にScoresを返す（次回保存時にUserStatsが作られる）
                # 本来はここでmigrateしてもよいが、読み込み速度優先
                return []
            return []
        return df.to_dict(orient="records")
    except Exception:
        return []


def get_stage_factor(stages):
    for label in stages:
        if "advanced" in label:
            return STAGE_MULTIPLIER["advanced"]
        if "intermediate" in label:
            return STAGE_MULTIPLIER["intermediate"]
        if "beginner" in label:
            return STAGE_MULTIPLIER["beginner"]
    return 1.0


def summarize_scores(scores):
    # JSTタイムゾーン設定 (UTC+9)
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now_jst = datetime.datetime.now(jst)
    today_jst = now_jst.date()
    month_start_jst = today_jst.replace(day=1)

    totals = {}
    totals_today = {}
    totals_month = {}
    hof = {}
    for r in scores:
        user = r.get("user")
        pts = float(r.get("points", 0))
        ts = r.get("ts")
        date_obj = None
        if ts:
            try:
                # ISOフォーマットの文字列をパース
                # tsが "2023-10-27T10:00:00" のような形式の場合、fromisoformatで読み込める
                # タイムゾーン情報がない場合はUTCとみなしてJSTに変換するか、
                # 単純に日付部分だけで比較する。
                # ここでは保存時に isoformat() しているので、そのまま読み込む
                dt = datetime.datetime.fromisoformat(ts)
                # もしナイーブなdatetimeならUTCとみなしてJSTへ変換
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone(jst)
                else:
                    dt = dt.astimezone(jst)
                date_obj = dt.date()
            except Exception:
                date_obj = None

        totals[user] = totals.get(user, 0) + pts
        if date_obj:
            if date_obj == today_jst:
                totals_today[user] = totals_today.get(user, 0) + pts
            if date_obj >= month_start_jst:
                totals_month[user] = totals_month.get(user, 0) + pts

        if totals[user] >= HOF_THRESHOLD:
            hof[user] = totals[user]
    return totals, totals_today, totals_month, hof


def summarize_rankings_from_stats(stats_data):
    """UserStatsデータからランキングを作成"""
    # UserStatsは累積のみ持っているため、本日・今月はScores（ログ）から計算する必要がある
    # しかし、スケーラビリティのため、ランキング表示は「累積（殿堂）」をメインにする
    # 本日・今月は直近ログ（例えば最新1000件）から計算するか、
    # UserStatsに today_points, month_points を持たせる設計変更が必要。
    # 今回は「累積」はUserStatsから、「本日・今月」はScoresから計算するハイブリッド方式とする。

    # 累積（高速）
    totals = {}

    # データ形式の自動判別（Raw Log vs Aggregated Stats）
    is_raw_log = False
    if stats_data and isinstance(stats_data, list) and len(stats_data) > 0:
        first_row = stats_data[0]
        # total_pointsがなく、pointsがある場合はRaw Logとみなす
        if "total_points" not in first_row and "points" in first_row:
            is_raw_log = True
            # st.warning("UserStatsシートにRawデータが含まれています。自動集計します。")

    if is_raw_log:
        # Raw Log形式の場合、ここで集計する（フォールバック）
        for r in stats_data:
            user = r.get("user")
            pts = float(r.get("points", 0))
            totals[user] = totals.get(user, 0) + pts
    else:
        # Aggregated Stats形式の場合（本来の想定）
        for r in stats_data:
            user = r.get("user")
            if not user:
                continue

            val = r.get("total_points")
            if val is None:
                # カラム名の揺らぎ対応
                for k in r.keys():
                    if "total_points" in k:
                        val = r[k]
                        break

            try:
                totals[user] = float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                totals[user] = 0.0

    hof = {u: p for u, p in totals.items() if p >= HOF_THRESHOLD}

    # 本日・今月（Scoresから計算 - ただし全件取得は重いので直近のみ...といきたいが
    # 現状は load_scores() が全件取得しているので、それをそのまま使う。
    # 将来的には load_scores(limit=1000) のように制限する）
    scores = load_scores() # キャッシュされているはず
    _, totals_today, totals_month, _ = summarize_scores(scores)

    return totals, totals_today, totals_month, hof


def rank_dict(d, top_n=None):
    items = sorted(d.items(), key=lambda x: x[1], reverse=True)
    return items[:top_n] if top_n else items


def show_rankings(stats_data):
    # --- DEBUG START ---
    with st.expander("Debug: Raw UserStats Data"):
        st.write("Raw Data:", stats_data)
        if st.button("Clear Cache & Rerun"):
            st.cache_data.clear()
            st.rerun()
    # --- DEBUG END ---

    totals, totals_today, totals_month, hof = summarize_rankings_from_stats(stats_data)
    tabs = st.tabs(["累積", "本日", "今月", f"殿堂（{HOF_THRESHOLD}点以上）"])
    import pandas as pd

    def to_df(d):
        if not d:
            return pd.DataFrame(columns=["順位", "ユーザー", "得点"])
        # 得点順にソート
        items = sorted(d.items(), key=lambda x: x[1], reverse=True)
        # データフレーム化 (順位をつける)
        data = []
        for i, (u, p) in enumerate(items, 1):
            data.append({"順位": i, "ユーザー": u, "得点": f"{p:.1f}"})
        return pd.DataFrame(data)

    with tabs[0]:
        st.dataframe(to_df(totals), use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(to_df(totals_today), use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(to_df(totals_month), use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(to_df(hof), use_container_width=True, hide_index=True)


def format_stage_label(stages):
    def map_stage(s):
        if s.startswith("beginner"):
            n = s.split("_")[1] if "_" in s else ""
            return f"{STAGE_JP['beginner']}{n}"
        if s.startswith("intermediate"):
            n = s.split("_")[1] if "_" in s else ""
            return f"{STAGE_JP['intermediate']}{n}"
        if s.startswith("advanced"):
            n = s.split("_")[1] if "_" in s else ""
            return f"{STAGE_JP['advanced']}{n}"
        return s

    return "+".join(map_stage(s) for s in stages)


def format_group_label(group):
    stage_label = format_stage_label(group.stages)
    gid = group.id.split(":")[-1]  # g1
    gid_num = gid[1:] if gid.startswith("g") else gid
    return f"{POS_JP.get(group.pos, group.pos)} / {stage_label} / グループ{gid_num} ({group.size}語)"


def find_audio(akey: str):
    for ext, mime in [(".wav", "audio/wav"), (".mp3", "audio/mpeg"), (".ogg", "audio/ogg")]:
        fp = AUDIO_DIR / f"{akey}{ext}"
        if fp.exists():
            return fp.read_bytes(), mime
    return None, None


def inject_audio_signal(session_id: str, target_audio_key: str):
    """
    Signal Iframe:
    Writes the target audio key to LocalStorage immediately.
    This runs in a separate, lightweight iframe that loads faster than the heavy audio player.
    Old iframes (ghosts) will see this change in LocalStorage and kill themselves.
    """
    signal_script = f"""
    <script>
        (function() {{
            try {{
                const sessionId = '{session_id}';
                const targetKey = '{target_audio_key}';
                const storageKey = 'esperanto_audio_target_' + sessionId;
                localStorage.setItem(storageKey, targetKey);
                localStorage.setItem(storageKey, targetKey);
            }} catch(e) {{
                console.error('[Signal] Error:', e);
            }}
        }})();
    </script>
    """
    # height=0 で不可視のiframeを注入
    st.components.v1.html(signal_script, height=0)


def audio_player(akey: str, autoplay: bool = True, question_index: int = 0):
    data, mime = find_audio(akey)
    if not data:
        st.info("音声ファイルなし")
        return

    # セッションIDを取得
    session_id = st.session_state.get("session_id", "default")

    # 問題ごとにユニークなIDを生成（question_indexを含めて確実に区別）
    unique_suffix = uuid.uuid4().hex[:8]
    audio_id = f"audio-q{question_index}-{unique_suffix}"
    b64 = base64.b64encode(data).decode("utf-8")

    # デバッグ用: audio_keyを埋め込む（コンソールログで確認可能）
    debug_audio_key = akey

    # HTML/JS template
    # モバイル対応: Web Audio API + ユーザージェスチャー追跡
    # iPhone Firefox対策: LocalStorageによる同期 + Signal Iframe
    tmpl = Template(
        """
        <style>
        .audio-card {
          width: 100%;
          padding: 12px 14px;
          background: #f7f7f7;
          border-radius: 10px;
          border: 1px solid #e0e0e0;
          box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);
        }
        .audio-top {
          display: flex;
          align-items: center;
          gap: 12px;
          width: 100%;
        }
        .audio-btn {
          width: 60px;
          min-width: 60px;
          height: 40px;
          font-size: 16px;
          cursor: pointer;
          border: 1px solid #ccc;
          border-radius: 5px;
          background: #fff;
        }
        .audio-bar {
          position: relative;
          flex: 1 1 60%;
          max-width: 60%;
          min-width: 200px;
          height: 10px;
          background: #ddd;
          border-radius: 6px;
          overflow: hidden;
          cursor: pointer;
        }
        .audio-progress {
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: 0%;
          background: #009900; /* Esperanto Green */
          border-radius: 6px;
        }
        .audio-time {
          width: 110px;
          min-width: 110px;
          text-align: right;
          font-variant-numeric: tabular-nums;
          font-size: 14px;
          white-space: nowrap;
          padding-left: 8px;
          padding-right: 8px;
        }
        .audio-controls {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-top: 10px;
          font-size: 14px;
          width: 100%;
          flex-wrap: wrap;
        }
        .rate-bar {
          position: relative;
          flex: 1 1 60%;
          min-width: 200px;
          max-width: 400px;
          height: 10px;
          background: #ddd;
          border-radius: 6px;
          cursor: pointer;
        }
        .rate-progress {
          position: absolute;
          left: 0;
          top: 0;
          bottom: 0;
          width: 0%;
          background: #009900;
          border-radius: 6px;
        }
        .rate-handle {
          position: absolute;
          top: -4px;
          width: 18px;
          height: 18px;
          background: #009900;
          border-radius: 50%;
          transform: translateX(-50%);
        }
        .rate-val {
          width: 60px;
          text-align: center;
        }
        .audio-debug-label {
          font-size: 11px;
          color: #666;
          margin-bottom: 4px;
          font-family: monospace;
        }
        </style>
        <div class="audio-card">
          <!-- デバッグ: このiframe内の音声が何かを表示 -->
          <div class="audio-debug-label">🎵 iframe内音声: <strong>$debug_audio_key</strong> (Q$question_index)</div>
          <div class="audio-top">
            <button class="audio-btn" id="$audio_id-play">▶︎</button>
            <div class="audio-bar" id="$audio_id-bar">
              <div class="audio-progress" id="$audio_id-prog"></div>
            </div>
            <span class="audio-time" id="$audio_id-time">0:00 / 0:00</span>
          </div>
          <div class="audio-controls">
            <div>再生速度</div>
            <div class="rate-bar" id="$audio_id-ratebar">
              <div class="rate-progress" id="$audio_id-rateprog"></div>
              <div class="rate-handle" id="$audio_id-ratehandle"></div>
            </div>
            <span class="rate-val" id="$audio_id-rateval">1.00x</span>
            <label><input type="checkbox" id="$audio_id-loop"> ループ</label>
          </div>
        </div>
        <!-- audio要素は遅延生成するため、ここでは作成しない -->
        <div id="$audio_id-container"></div>
        <script>
          (function() {
            // iPhone Firefox対策: LocalStorage同期 + Signal Iframe
            // 1. LocalStorageを監視し、ターゲット単語が自分でない場合は即停止
            // 2. isConnected チェックも併用
            // 3. Blob URL使用

            const currentQuestionIndex = $question_index;
            const currentAudioId = '$audio_id';
            const debugAudioKey = '$debug_audio_key';
            const mimeType = '$mime';
            const b64Data = '$b64';
            const sessionId = '$session_id';
            const storageKey = 'esperanto_audio_target_' + sessionId;
            const myTimestamp = Date.now();

            // Blob URLの生成
            function b64ToBlob(b64Data, contentType='', sliceSize=512) {
              const byteCharacters = atob(b64Data);
              const byteArrays = [];
              for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
                const slice = byteCharacters.slice(offset, offset + sliceSize);
                const byteNumbers = new Array(slice.length);
                for (let i = 0; i < slice.length; i++) {
                  byteNumbers[i] = slice.charCodeAt(i);
                }
                const byteArray = new Uint8Array(byteNumbers);
                byteArrays.push(byteArray);
              }
              return new Blob(byteArrays, {type: contentType});
            }

            const audioBlob = b64ToBlob(b64Data, mimeType);
            const audioUrl = URL.createObjectURL(audioBlob);

            // 自分自身を非表示にする関数
            function hideMyself() {
              const card = document.querySelector('.audio-card');
              if (card) {
                card.style.display = 'none';
              }
              if (a) {
                a.pause();
                a.src = '';
                a.load();
              }
              if (audioUrl) {
                URL.revokeObjectURL(audioUrl);
              }
            }

            // 最新チェック（LocalStorageベース）
            function isLatest() {
              // 1. DOM接続チェック
              if (!document.documentElement.isConnected) {
                  return false;
              }

              // 2. LocalStorageチェック (最強の同期手段)
              try {
                  const target = localStorage.getItem(storageKey);
                  // targetが存在し、かつ自分と異なる場合は古いとみなす
                  // (targetがまだセットされていない場合は、Signal Iframeが遅れている可能性があるので許容するか、
                  //  あるいは安全側に倒して停止するか。ここでは安全側に倒すが、初期ロード時の競合に注意)
                  if (target && target !== debugAudioKey) {
                      return false;
                  }
              } catch(e) {
                  console.error(e);
              }

              return true;
            }

            function checkAndStop() {
                if (!isLatest()) {
                    hideMyself();
                    return true;
                }
                return false;
            }

            // 監視ループ (100ms間隔)
            const checkInterval = setInterval(() => {
              if (checkAndStop()) {
                clearInterval(checkInterval);
              }
            }, 100);

            // ページ遷移/アンロード時のクリーンアップ
            window.addEventListener('unload', hideMyself);
            window.addEventListener('pagehide', hideMyself);

            const btn = document.getElementById('$audio_id-play');
            const bar = document.getElementById('$audio_id-bar');
            const prog = document.getElementById('$audio_id-prog');
            const time = document.getElementById('$audio_id-time');
            const rateBar = document.getElementById('$audio_id-ratebar');
            const rateProg = document.getElementById('$audio_id-rateprog');
            const rateHandle = document.getElementById('$audio_id-ratehandle');
            const rateVal = document.getElementById('$audio_id-rateval');
            const loopCb = document.getElementById('$audio_id-loop');
            const container = document.getElementById('$audio_id-container');

            const rateMin = 0.5;
            const rateMax = 2.0;

            let a = null;
            let audioCreated = false;

            let savedRate = parseFloat(sessionStorage.getItem('esperanto_audio_rate'));
            let savedLoop = sessionStorage.getItem('esperanto_audio_loop') === 'true';
            if (isNaN(savedRate)) savedRate = 1.0;

            function updateRateUI(r) {
              const pct = ((r - rateMin) / (rateMax - rateMin)) * 100;
              rateProg.style.width = pct + '%';
              rateHandle.style.left = pct + '%';
              rateVal.textContent = r.toFixed(2) + 'x';
            }
            updateRateUI(savedRate);
            loopCb.checked = savedLoop;

            function fmt(t) {
              if (!isFinite(t) || isNaN(t)) return "0:00";
              const m = Math.floor(t/60);
              const s = Math.floor(t%60).toString().padStart(2,'0');
              return m+":"+s;
            }

            function updateBar() {
              if (!a) return;
              const dur = a.duration;
              const cur = a.currentTime;
              if (!isFinite(dur) || isNaN(dur)) {
                time.textContent = fmt(cur) + " / --:--";
                prog.style.width = '0%';
                return;
              }
              const pct = (cur / dur) * 100;
              prog.style.width = pct + '%';
              time.textContent = fmt(cur) + " / " + fmt(dur);
            }

            function resetBtnStyle() {
              btn.style.background = '';
              btn.style.color = '';
              btn.style.animation = '';
              btn.style.width = '';
              btn.style.minWidth = '';
              btn.style.fontSize = '';
              btn.style.fontWeight = '';
            }

            function createAudio() {
              if (audioCreated) return a;
              if (!isLatest()) {
                hideMyself();
                return null;
              }

              a = document.createElement('audio');
              a.id = currentAudioId;
              a.preload = 'auto';
              a.setAttribute('playsinline', '');
              a.src = audioUrl; // Blob URLを使用
              container.appendChild(a);
              audioCreated = true;

              a.playbackRate = savedRate;
              a.defaultPlaybackRate = savedRate;
              a.loop = savedLoop;

              a.addEventListener('timeupdate', updateBar);
              a.addEventListener('loadedmetadata', updateBar);
              a.addEventListener('durationchange', updateBar);
              a.addEventListener('ended', () => {
                if (!a.loop) {
                  btn.textContent = "▶︎";
                  a.currentTime = 0;
                  updateBar();
                }
              });

              return a;
            }

            rateBar.onclick = (e) => {
              const rect = rateBar.getBoundingClientRect();
              const pct = (e.clientX - rect.left) / rect.width;
              const val = rateMin + pct * (rateMax - rateMin);
              const r = Math.min(rateMax, Math.max(rateMin, val));
              savedRate = r;
              sessionStorage.setItem('esperanto_audio_rate', r);
              updateRateUI(r);
              if (a) {
                a.playbackRate = r;
                a.defaultPlaybackRate = r;
              }
            };

            loopCb.addEventListener('change', () => {
              savedLoop = loopCb.checked;
              sessionStorage.setItem('esperanto_audio_loop', loopCb.checked);
              if (a) a.loop = loopCb.checked;
            });

            bar.onclick = (e) => {
              if (!a || !a.duration) return;
              const rect = bar.getBoundingClientRect();
              const pct = (e.clientX - rect.left) / rect.width;
              a.currentTime = Math.max(0, Math.min(1, pct)) * a.duration;
              updateBar();
            };

            btn.onclick = () => {
              if (!isLatest()) {
                hideMyself();
                return;
              }
              const audio = createAudio();
              if (!audio) return;

              if (audio.paused) {
                audio.play().then(() => {
                  if (!isLatest()) {
                    audio.pause();
                    hideMyself();
                    return;
                  }
                  resetBtnStyle();
                  btn.textContent = "⏸";
                }).catch((err) => {
                  console.warn("Play failed:", err);
                });
              } else {
                audio.pause();
                btn.textContent = "▶︎";
              }
            };

            function attemptAutoplay() {
              if (!isLatest()) return;

              const audio = createAudio();
              if (!audio) return;

              audio.play().then(() => {
                if (!isLatest()) {
                  audio.pause();
                  return;
                }
                resetBtnStyle();
                btn.textContent = "⏸";
              }).catch((err) => {
                console.warn("[Esperanto Audio] Autoplay blocked:", debugAudioKey, err);
                btn.textContent = "▶︎";

                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                if (isMobile) {
                  btn.style.background = '#009900';
                  btn.style.color = '#fff';
                  btn.style.width = '100%';
                  btn.style.minWidth = '100%';
                  btn.style.fontSize = '18px';
                  btn.style.fontWeight = 'bold';
                  btn.textContent = "🔊 タップして再生";
                  btn.style.animation = 'pulse 1s infinite';

                  if (!document.getElementById('pulse-style')) {
                    const style = document.createElement('style');
                    style.id = 'pulse-style';
                    style.textContent = '@keyframes pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.02); opacity: 0.9; } }';
                    document.head.appendChild(style);
                  }
                }
              });
            }

            if ($autoplay_bool) {
              const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
              // Signal IframeがLocalStorageを更新するのを待つため、少し遅延を増やす
              const delay = isMobile ? 300 : 50;
              setTimeout(() => {
                if (isLatest()) {
                   attemptAutoplay();
                }
              }, delay);
            }
          })();
        </script>
        """
    )
    html = tmpl.safe_substitute(
        audio_id=audio_id,
        mime=mime,
        b64=b64,
        autoplay_bool=str(autoplay).lower(),
        question_index=question_index,
        debug_audio_key=debug_audio_key,
        session_id=session_id,
    )
    # st.components.v1.html()はkeyパラメータをサポートしていない
    st.components.v1.html(html, height=190)




def init_state():
    st.session_state.setdefault("user_name", "")
    st.session_state.setdefault("seed", 1)
    st.session_state.setdefault("group_id", None)
    st.session_state.setdefault("questions", [])
    st.session_state.setdefault("q_index", 0)
    st.session_state.setdefault("correct", 0)
    st.session_state.setdefault("points", 0.0)
    st.session_state.setdefault("streak", 0)
    st.session_state.setdefault("answers", [])
    st.session_state.setdefault("playback_rate", 1.0)
    st.session_state.setdefault("loop_enabled", False)
    st.session_state.setdefault("score_saved", False)
    st.session_state.setdefault("last_saved_key", None)
    st.session_state.setdefault("score_load_error", None)
    # UI State
    st.session_state.setdefault("showing_result", False)
    st.session_state.setdefault("last_result_msg", "")
    st.session_state.setdefault("last_is_correct", False)
    st.session_state.setdefault("last_correct_answer", "")
    st.session_state.setdefault("last_correct_answer", "")
    st.session_state.setdefault("score_saved", False)
    st.session_state.setdefault("cached_scores", [])
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())


def start_quiz(group, rng):
    questions = vg.build_questions_for_group(group, rng=rng, min_options=2, max_options=4)
    st.session_state.questions = questions
    st.session_state.q_index = 0
    st.session_state.correct = 0
    st.session_state.points = 0.0
    st.session_state.streak = 0
    st.session_state.answers = []
    st.session_state.score_saved = False
    st.session_state.last_saved_key = None
    st.session_state.showing_result = False


def main():
    init_state()

    st.set_page_config(
        page_title="エスペラント単語クイズ",
        page_icon="💚",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    # エスペラント・グリーン (#009900) を基調としたテーマ設定
    st.markdown(
        """
        <style>
        /* プライマリボタン（st.button type="primary"）の色変更 */
        div.stButton > button[kind="primary"] {
            background-color: #009900 !important;
            border-color: #009900 !important;
            color: white !important;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #007700 !important;
            border-color: #007700 !important;
        }
        div.stButton > button[kind="primary"]:active {
            background-color: #005500 !important;
            border-color: #005500 !important;
        }
        /* 通常ボタンのボーダーなども緑系に */
        div.stButton > button[kind="secondary"] {
            border-color: #009900 !important;
        }
        /* タイトルスタイル */
        .main-title {
            font-size: 24px;
            font-weight: bold;
            color: #009900;
            margin-bottom: 10px;
            white-space: nowrap; /* Prevent wrapping */
        }
        </style>
        <div class="main-title">エスペラント単語４択クイズ</div>
        """,
        unsafe_allow_html=True
    )

    # モバイル用: 音声自動再生のアンロックスクリプト（グローバルに1回だけ挿入）
    # ユーザーが画面のどこかをタップしたら、サイレント音声を再生して
    # 以降の自動再生を可能にする
    st.markdown(
        """
        <script>
        (function() {
            // 既にアンロック済みならスキップ
            if (window._esperantoAudioUnlocked) return;

            const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
            if (!isMobile) {
                window._esperantoAudioUnlocked = true;
                return;
            }

            // sessionStorageでページ間のアンロック状態を維持
            if (sessionStorage.getItem('esperanto_audio_unlocked') === 'true') {
                window._esperantoAudioUnlocked = true;
                return;
            }

            function unlockAudio() {
                // サイレントな短いオーディオを再生してブラウザの制限を解除
                const silentAudio = new Audio('data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=');
                silentAudio.volume = 0.01;
                silentAudio.play().then(() => {
                    console.log('Audio unlocked for mobile');
                    window._esperantoAudioUnlocked = true;
                    sessionStorage.setItem('esperanto_audio_unlocked', 'true');
                }).catch((e) => {
                    console.log('Silent audio play failed:', e);
                });
            }

            // 最初のユーザー操作でアンロック
            document.addEventListener('touchstart', unlockAudio, { once: true });
            document.addEventListener('click', unlockAudio, { once: true });
        })();
        </script>
        """,
        unsafe_allow_html=True
    )

    st.write("品詞×レベルでグルーピングした単語から出題します。シードを変えるとグループ分けと順番が変わります。")
    with st.expander("スコア計算ルール"):
        st.markdown(
            f"- 基礎点: {BASE_POINTS} × レベル倍率 (初級1.0 / 中級1.3 / 上級1.6)\\n"
            f"- 連続正解ボーナス: 2問目以降の連続正解1回につき +{STREAK_BONUS}\\n"
            f"- 精度ボーナス: 最終正答率 × 問題数 × {ACCURACY_BONUS_PER_Q}\\n"
            "- グループを出し切ると結果画面でボーナス込みの合計を表示します。"
        )

    with st.sidebar:
        st.header("設定")
        # keyを指定することでステート管理をStreamlitに任せる
        user_name = st.text_input("ユーザー名 (スコア保存用)", key="user_name")
        seed = st.number_input("ランダムシード (1-8192)", min_value=1, max_value=8192, step=1, key="seed")
        # st.session_state.seed = seed # key="seed"にしたので不要
        # st.session_state.shuffle_every_time = st.checkbox("毎回ランダムに並べる（シード無視）", value=st.session_state.shuffle_every_time)
        groups = load_groups(seed)
        pos_list = sorted({g.pos for g in groups})
        pos_label_map = {p: POS_JP.get(p, p) for p in pos_list}
        pos_choice = st.selectbox("品詞を選択", pos_list, format_func=lambda p: pos_label_map.get(p, p), key="pos_select")
        group_options = [g for g in groups if g.pos == pos_choice]
        group_labels = [format_group_label(g) for g in group_options]
        choice = st.selectbox("グループを選択", group_labels)
        selected_group = group_options[group_labels.index(choice)] if group_options else None
        if st.button("クイズ開始", disabled=not selected_group, use_container_width=True):
            # 出題順は常にランダム（シードはグループ分けのみに使用）
            rng = random.Random()
            start_quiz(selected_group, rng=rng)
            st.session_state.group_id = selected_group.id

        st.markdown("---")
        # ホームに戻るボタンをクイズ開始ボタンと同様に横幅可変にし、見た目を揃える
        if st.button("🏠 ホームに戻る", use_container_width=True, type="primary", key="home-btn"):
            st.session_state.questions = []
            st.session_state.group_id = None
            st.session_state.q_index = 0
            st.session_state.correct = 0
            st.session_state.points = 0.0
            st.session_state.streak = 0
            st.session_state.answers = []
            st.session_state.showing_result = False
            st.session_state.score_saved = False
            st.session_state.last_saved_key = None
            st.rerun()

            st.session_state.score_saved = False
            st.session_state.last_saved_key = None
            # ホームに戻る時はスコアを再読み込み
            st.session_state.cached_scores = load_scores()
            st.rerun()

    # スコア読み込み戦略:
    # 1. クイズ中（questionsがあり、結果画面でない）はAPIを呼ばない（キャッシュ使用）
    # 2. ホーム画面、結果画面、スコア保存直後はAPIを呼ぶ
    should_load = (
        not st.session_state.questions or
        st.session_state.showing_result or
        st.session_state.score_saved or
        not st.session_state.cached_scores
    )

    if should_load:
        scores = load_scores()
        st.session_state.cached_scores = scores
    else:
        scores = st.session_state.cached_scores

    if st.session_state.get("score_load_error"):
        st.warning(st.session_state.score_load_error)
    if st.session_state.user_name and scores:
        user_total = sum(r.get("points", 0) for r in scores if r.get("user") == st.session_state.user_name)
        st.info(f"現在の累積得点（{st.session_state.user_name}）: {user_total:.1f}")

    if not st.session_state.questions:
        st.info("左のサイドバーからグループを選び、クイズを開始してください。")
        if scores:
            st.subheader("ランキング")
            show_rankings(scores)
        return

    q_index = st.session_state.q_index
    questions = st.session_state.questions
    if q_index >= len(questions):
        # 終了画面
        correct = st.session_state.correct
        total = len(questions)
        accuracy = correct / total if total else 0
        raw_points = st.session_state.points
        accuracy_bonus = accuracy * total * ACCURACY_BONUS_PER_Q
        points = raw_points + accuracy_bonus
        st.subheader("結果")
        st.metric("正答率", f"{accuracy*100:.1f}%")
        st.metric("得点", f"{points:.1f}")
        if st.session_state.user_name:
            user_total = sum(r.get("points", 0) for r in scores if r.get("user") == st.session_state.user_name)
            st.metric("累積得点", f"{user_total + points:.1f}（今回{points:.1f}加算前 {user_total:.1f}）")
        st.write(f"正解 {correct} / {total}")
        st.write(f"内訳: 基礎+難易度 {raw_points:.1f} / 精度ボーナス {accuracy_bonus:.1f}")
        if st.session_state.user_name:
            existing_users = {r.get("user") for r in load_scores()}
            if st.session_state.user_name in existing_users:
                st.info("このユーザー名は既にスコアがあります。累積に加算します。")
            if st.session_state.score_saved:
                st.success("スコアを保存しました！")
            else:
                if st.button("スコアを保存", key="save_score_btn"):
                    now = datetime.datetime.utcnow().isoformat()
                    record = {
                        "user": st.session_state.user_name,
                        "group_id": st.session_state.group_id,
                        "seed": st.session_state.seed,
                        "correct": correct,
                        "total": total,
                        "accuracy": accuracy,
                        "points": points,
                        "raw_points": raw_points,
                        "accuracy_bonus": accuracy_bonus,
                        "ts": now,
                    }
                    # UserStats更新（累積）
                    update_user_stats(st.session_state.user_name, points, now)

                    # Scores更新（ログ）
                    if save_score(record):
                        st.session_state.score_saved = True
                        st.rerun()
                    else:
                        st.error("保存に失敗しました。秘密情報（secrets）の設定を確認してください。")

        scores = load_scores()
        if scores:
            st.write("最近のスコア")
            st.dataframe(scores)
            st.subheader("ランキング")
            show_rankings(load_rankings())

        # 復習セクション
        st.subheader("復習")
        wrong = []
        correct_list = []
        for ans in st.session_state.answers:
            q = st.session_state.questions[ans["q_idx"]]
            selected = ans["selected"]
            correct_idx = ans["correct"]
            entry = {
                "prompt": q["prompt"],
                "selected": q["options"][selected]["japanese"] if selected is not None else "",
                "answer": q["options"][correct_idx]["japanese"],
                "answer_eo": q["options"][correct_idx]["esperanto"],
            }
            if selected == correct_idx:
                correct_list.append(entry)
            else:
                wrong.append(entry)

        if wrong:
            st.markdown("### 間違えた問題")
            for w in wrong:
                st.write(f"- {w['prompt']}: 正解「{w['answer']} / {w['answer_eo']}」、あなたの回答「{w['selected']}」")
        if correct_list:
            st.markdown("### 正解した問題（確認用）")
            for c in correct_list:
                st.write(f"- {c['prompt']}: {c['answer']} / {c['answer_eo']}")
        if st.button("もう一度同じグループで再挑戦", key="retry_btn"):
            group = next((g for g in load_groups(st.session_state.seed) if g.id == st.session_state.group_id), None)
            if group:
                rng = random.Random()
                start_quiz(group, rng=rng)
                st.rerun()
        return

    question = questions[q_index]
    audio_key = question["options"][question["answer_index"]]["audio_key"]

    # Signal Iframeを注入して、LocalStorageを即座に更新
    # これにより、古いiframe（ゴースト）が自分が古いことを検知して停止する
    if audio_key:
        inject_audio_signal(st.session_state.session_id, audio_key)

    # スマホ対応: 回答ボタンのスタイル（PCとモバイルで高さを変える）
    st.markdown(
        """
        <style>
        /* PC用: 回答ボタンを固定サイズに統一 */
        .stButton button {
            height: 120px;
            min-height: 120px;
            max-height: 120px;
            width: 100% !important;
            white-space: normal;
            overflow: hidden;
            text-overflow: ellipsis;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 8px;
        }
        /* スマホ用: より小さい高さ */
        @media (max-width: 768px) {
            .stButton button {
                height: 80px;
                min-height: 80px;
                max-height: 80px;
                font-size: 14px;
                padding: 4px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 出題単語（一番上に大きく表示）
    st.subheader(f"Q{q_index+1}/{len(questions)}: {question['prompt']}")

    # 結果表示モードの場合
    if st.session_state.showing_result:
        # 結果を表示
        if st.session_state.last_is_correct:
            st.success(st.session_state.last_result_msg)
        else:
            st.error(st.session_state.last_result_msg)

        # 「次へ」ボタン
        if st.button("次へ進む", type="primary", use_container_width=True, key=f"next_btn_{st.session_state.q_index}"):
            st.session_state.q_index += 1
            st.session_state.showing_result = False
            st.rerun()

        # 音声プレイヤーは下に配置（不正解時の復習用）
        if audio_key:
            st.markdown("---")
            st.caption(f"🔊 発音を確認【{audio_key}】")
            audio_player(audio_key, autoplay=True, question_index=q_index)
        return

    # 回答待ちモード: 4択ボタンを出題単語の直下に配置
    option_labels = [f"{opt['japanese']}" for opt in question["options"]]
    clicked_index = None
    for row_start in range(0, len(option_labels), 2):
        cols = st.columns([1, 1], gap="medium")
        for j in range(2):
            idx = row_start + j
            if idx >= len(option_labels):
                continue
            with cols[j]:
                if st.button(option_labels[idx], key=f"opt-{q_index}-{idx}", use_container_width=True, type="primary"):
                    clicked_index = idx

    # 音声プレイヤーは4択ボタンの下に配置
    if audio_key:
        st.markdown("---")
        # デバッグ: 現在の音声キーを表示（問題特定後に削除可能）
        st.caption(f"🔊 発音を聞く（自動再生）【{audio_key}】")
        audio_player(audio_key, autoplay=True, question_index=q_index)

    if clicked_index is not None:
        is_correct = clicked_index == question["answer_index"]
        st.session_state.answers.append(
            {
                "q_idx": q_index,
                "q": question["prompt"],
                "selected": clicked_index,
                "correct": question["answer_index"],
            }
        )

        if is_correct:
            # 正解時は即座に次へ（ユーザー要望）
            st.session_state.correct += 1
            factor = get_stage_factor(question["stages"])
            st.session_state.streak += 1
            streak_bonus = max(0, st.session_state.streak - 1) * STREAK_BONUS
            st.session_state.points += BASE_POINTS * factor + streak_bonus

            st.session_state.q_index += 1
            st.session_state.showing_result = False
            st.rerun()
        else:
            # 不正解時は正解を表示して一時停止
            msg = f"不正解。正解: {option_labels[question['answer_index']]}"
            st.session_state.streak = 0

            # 結果表示モードへ移行
            st.session_state.showing_result = True
            st.session_state.last_result_msg = msg
            st.session_state.last_is_correct = False
            st.session_state.last_correct_answer = option_labels[question['answer_index']]
            st.rerun()


if __name__ == "__main__":
    main()
