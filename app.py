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
    "intermediate": 1.5,
    "advanced": 2.0,
}
# 連続正解ボーナス: 2問目以降の連続正解1回あたり加算
STREAK_BONUS = 2.0
# 最終精度ボーナス: accuracy * 問題数 * この値
ACCURACY_BONUS_PER_Q = 2.0
# 殿堂入りライン
HOF_THRESHOLD = 3000

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
        return []
    try:
        # ワークシート "Scores" からデータを読み込む
        # API制限（1分間に60リクエスト）を回避するため、キャッシュ有効時間を設定
        # ttl=60秒（1分間は再取得せずキャッシュを使う）
        df = conn.read(worksheet="Scores", ttl=60)
        if df.empty:
            return []
        # DataFrameを辞書のリストに変換
        return df.to_dict(orient="records")
    except Exception as e:
        # エラー時はユーザーに通知せず静かに空リストを返す（頻繁なエラー表示を防ぐ）
        # st.error(f"ランキングデータの読み込みに失敗しました: {e}")
        print(f"Ranking load error: {e}")
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
        
        # 保存成功後、キャッシュをクリアして次の読み込みで最新が反映されるようにする
        st.cache_data.clear()
        
        return True
    except Exception as e:
        st.error(f"スコアの保存に失敗しました: {e}")
        return False


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


def rank_dict(d, top_n=None):
    items = sorted(d.items(), key=lambda x: x[1], reverse=True)
    return items[:top_n] if top_n else items


def show_rankings(scores):
    totals, totals_today, totals_month, hof = summarize_scores(scores)
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
        st.dataframe(to_df(totals), width='stretch', hide_index=True)
    with tabs[1]:
        st.dataframe(to_df(totals_today), width='stretch', hide_index=True)
    with tabs[2]:
        st.dataframe(to_df(totals_month), width='stretch', hide_index=True)
    with tabs[3]:
        st.dataframe(to_df(hof), width='stretch', hide_index=True)


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


def audio_player(akey: str, autoplay: bool = True):
    data, mime = find_audio(akey)
    if not data:
        st.info("音声ファイルなし")
        return
    audio_id = f"audio-{uuid.uuid4().hex}"
    b64 = base64.b64encode(data).decode("utf-8")

    # HTML/JS template
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
        </style>
        <div class="audio-card">
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
        <audio id="$audio_id" src="data:$mime;base64,$b64"></audio>
        <script>
          (function() {
            const a = document.getElementById('$audio_id');
            const btn = document.getElementById('$audio_id-play');
            const bar = document.getElementById('$audio_id-bar');
            const prog = document.getElementById('$audio_id-prog');
            const time = document.getElementById('$audio_id-time');

            const rateBar = document.getElementById('$audio_id-ratebar');
            const rateProg = document.getElementById('$audio_id-rateprog');
            const rateHandle = document.getElementById('$audio_id-ratehandle');
            const rateVal = document.getElementById('$audio_id-rateval');
            const loopCb = document.getElementById('$audio_id-loop');

            const rateMin = 0.5;
            const rateMax = 2.0;

            // --- Persistence Logic ---
            // Load settings from sessionStorage
            let savedRate = parseFloat(sessionStorage.getItem('esperanto_audio_rate'));
            let savedLoop = sessionStorage.getItem('esperanto_audio_loop') === 'true';

            if (isNaN(savedRate)) savedRate = 1.0;

            // Apply settings
            function applyRate(val) {
                const r = Math.min(rateMax, Math.max(rateMin, val));
                a.playbackRate = r;
                a.defaultPlaybackRate = r;

                // Update UI
                const pct = ((r - rateMin) / (rateMax - rateMin)) * 100;
                rateProg.style.width = pct + '%';
                rateHandle.style.left = pct + '%';
                rateVal.textContent = r.toFixed(2) + 'x';

                // Save persistence
                sessionStorage.setItem('esperanto_audio_rate', r);
            }

            applyRate(savedRate);

            a.loop = savedLoop;
            loopCb.checked = savedLoop;

            loopCb.addEventListener('change', () => {
                a.loop = loopCb.checked;
                sessionStorage.setItem('esperanto_audio_loop', loopCb.checked);
            });

            // --- Rate Control UI ---
            rateBar.onclick = (e) => {
              const rect = rateBar.getBoundingClientRect();
              const pct = (e.clientX - rect.left) / rect.width;
              const val = rateMin + pct * (rateMax - rateMin);
              applyRate(val);
            };

            // --- Time Display & Progress ---
            function fmt(t) {
              if (!isFinite(t) || isNaN(t)) return "0:00";
              const m = Math.floor(t/60);
              const s = Math.floor(t%60).toString().padStart(2,'0');
              return m+":"+s;
            }

            function updateBar() {
              const dur = a.duration;
              const cur = a.currentTime;

              // Retry getting duration if not available yet (common with base64)
              if (!isFinite(dur) || isNaN(dur)) {
                  time.textContent = fmt(cur) + " / --:--";
                  prog.style.width = '0%';
                  return;
              }

              const pct = (cur / dur) * 100;
              prog.style.width = pct + '%';
              time.textContent = fmt(cur) + " / " + fmt(dur);
            }

            btn.onclick = () => {
              if (a.paused) {
                a.play();
                btn.textContent = "⏸";
              } else {
                a.pause();
                btn.textContent = "▶︎";
              }
            };

            a.addEventListener('timeupdate', updateBar);
            a.addEventListener('loadedmetadata', updateBar);
            a.addEventListener('durationchange', updateBar); // Extra event for duration availability

            a.addEventListener('ended', () => {
               if (!a.loop) {
                   btn.textContent = "▶︎";
                   a.currentTime = 0;
                   updateBar();
               }
            });

            bar.onclick = (e) => {
              const rect = bar.getBoundingClientRect();
              const pct = (e.clientX - rect.left) / rect.width;
              if (a.duration) {
                a.currentTime = Math.max(0, Math.min(1, pct)) * a.duration;
              }
              updateBar();
            };

            // Initial update
            updateBar();

            if ($autoplay_bool) {
              // Small delay to ensure rate is applied before playing
              setTimeout(() => {
                  a.play().then(() => { btn.textContent = "⏸"; }).catch(() => { btn.textContent = "▶︎"; });
              }, 50);
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
    )
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


def start_quiz(group, rng):
    questions = vg.build_questions_for_group(group, rng=rng, min_options=2, max_options=4)
    st.session_state.questions = questions
    st.session_state.q_index = 0
    st.session_state.correct = 0
    st.session_state.points = 0.0
    st.session_state.streak = 0
    st.session_state.answers = []


def main():
    init_state()

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
            color: #009900 !important;
        }
        div.stButton > button[kind="secondary"]:hover {
            border-color: #007700 !important;
            color: #007700 !important;
            background-color: #f0fff0 !important;
        }
        /* サイドバーのボタンは横幅いっぱいに広げる */
        section[data-testid="stSidebar"] .stButton button {
            width: 100% !important;
        }
        /* ヘッダーの装飾など */
        h1, h2, h3 {
            color: #006600 !important;
        }
        .main-title {
            font-size: 2.0rem; /* Slightly smaller to fit on one line */
            color: #006600; /* Esperanto Green Dark */
            text-align: center;
            font-weight: bold;
            margin-bottom: 20px;
            white-space: nowrap; /* Prevent wrapping */
        }
        </style>
        <div class="main-title">エスペラント単語４択クイズ</div>
        """,
        unsafe_allow_html=True
    )
    st.write("品詞×レベルでグルーピングした単語から出題します。シードを変えるとグループ分けと順番が変わります。")
    with st.expander("スコア計算ルール"):
        st.markdown(
            f"- 基礎点: {BASE_POINTS} × レベル倍率 (初級1.0 / 中級1.5 / 上級2.0)\n"
            f"- 連続正解ボーナス: 2問目以降の連続正解1回につき +{STREAK_BONUS}\n"
            f"- 精度ボーナス: 最終正答率 × 問題数 × {ACCURACY_BONUS_PER_Q}\n"
            "- グループを出し切ると結果画面でボーナス込みの合計を表示します。"
        )

    with st.sidebar:
        st.header("設定")
        st.session_state.user_name = st.text_input("ユーザー名 (スコア保存用)", st.session_state.user_name)
        seed = st.number_input("ランダムシード (1-8192)", min_value=1, max_value=8192, value=st.session_state.get("seed", 1), step=1)
        st.session_state.seed = seed
        # st.session_state.shuffle_every_time = st.checkbox("毎回ランダムに並べる（シード無視）", value=st.session_state.shuffle_every_time)
        groups = load_groups(seed)
        pos_list = sorted({g.pos for g in groups})
        pos_label_map = {p: POS_JP.get(p, p) for p in pos_list}
        pos_choice = st.selectbox("品詞を選択", pos_list, format_func=lambda p: pos_label_map.get(p, p))
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
            st.rerun()

    scores = load_scores()
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
            if st.button("スコアを保存"):
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
                if save_score(record):
                    st.success("保存しました")
                else:
                    st.error("保存に失敗しました。秘密情報（secrets）の設定を確認してください。")

        scores = load_scores()
        if scores:
            st.write("最近のスコア")
            st.dataframe(scores)
            st.subheader("ランキング")
            show_rankings(scores)

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
        if st.button("もう一度同じグループで再挑戦"):
            group = next((g for g in load_groups(st.session_state.seed) if g.id == st.session_state.group_id), None)
            if group:
                rng = random.Random()
                start_quiz(group, rng=rng)
                st.rerun()
        return

    question = questions[q_index]
    st.subheader(f"Q{q_index+1}/{len(questions)}: {question['prompt']}")
    audio_key = question["options"][question["answer_index"]]["audio_key"]
    if audio_key:
        audio_player(audio_key, autoplay=True)

    # 固定サイズボタン（2x2）で見やすく配置
    st.markdown(
        """
        <style>
        /* すべての回答ボタンを固定サイズに統一 */
        .stButton button {
            height: 140px;
            min-height: 140px;
            max-height: 140px;
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
        </style>
        """,
        unsafe_allow_html=True,
    )
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
            st.success("正解！")
            st.session_state.correct += 1
            factor = get_stage_factor(question["stages"])
            st.session_state.streak += 1
            streak_bonus = max(0, st.session_state.streak - 1) * STREAK_BONUS
            st.session_state.points += BASE_POINTS * factor + streak_bonus
        else:
            st.error(f"不正解。正解: {option_labels[question['answer_index']]}")
            st.session_state.streak = 0

        st.session_state.q_index += 1
        st.rerun()


if __name__ == "__main__":
    main()
