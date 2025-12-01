import datetime
import random
import uuid
from pathlib import Path

import streamlit as st
import pandas as pd

import vocab_grouping as vg

# パス設定
# 語彙データ（日本語を含む多言語版）
CSV_PATH = Path("2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv")
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
# スパルタモード時の得点係数（通常の約7割）
SPARTAN_SCORE_MULTIPLIER = 0.7
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

# 出題方向
QUIZ_DIRECTIONS = {
    "eo_to_ja": "エスペラント → 日本語",
    "ja_to_eo": "日本語 → エスペラント",
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

def load_scores(force_refresh: bool = False):
    """Google Sheetsからスコアを読み込む"""
    conn = get_connection()
    if conn is None:
        st.session_state.score_load_error = "Google Sheets 接続を初期化できませんでした。"
        return []
    try:
        # ワークシート "Scores" からデータを読み込む
        # API制限（1分間に60リクエスト）を回避するため、キャッシュ有効時間を設定
        # ttl=60秒（1分間は再取得せずキャッシュを使う）
        df = conn.read(worksheet="Scores", ttl=0 if force_refresh else 60)
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
    # Use the highest stage present; order of labels should not affect scoring.
    if any("advanced" in label for label in stages):
        return STAGE_MULTIPLIER["advanced"]
    if any("intermediate" in label for label in stages):
        return STAGE_MULTIPLIER["intermediate"]
    if any("beginner" in label for label in stages):
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


@st.cache_data(show_spinner=False, max_entries=1024)
def find_audio(akey: str):
    """
    音声ファイルの読み込みをキャッシュして重複I/Oを防ぐ。
    キャッシュはヒット/ミス両方を保持する。
    """
    for ext, mime in [(".wav", "audio/wav"), (".mp3", "audio/mpeg"), (".ogg", "audio/ogg")]:
        fp = AUDIO_DIR / f"{akey}{ext}"
        if fp.exists():
            return fp.read_bytes(), mime
    return None, None


def simple_audio_player(akey: str, question_index: int = 0, instance: str = "default"):
    """
    シンプルな st.audio() ベースのプレイヤー
    - Streamlitがコンポーネントライフサイクルを管理するため、ゴーストiframe問題が発生しない
    - ブラウザ標準の再生速度調整機能を使用可能（Safari/Firefox等）
    """
    data, mime = find_audio(akey)
    if not data:
        st.info("音声ファイルなし")
        return

    format_map = {
        "audio/wav": "audio/wav",
        "audio/mpeg": "audio/mp3",
        "audio/ogg": "audio/ogg",
    }
    audio_format = format_map.get(mime, "audio/wav")
    # start_timeにランダムな微小オフセットを付与してID衝突を防ぐ（key引数は使えないため）
    offset = random.random() / 1000.0 + 1e-6
    with st.container():
        st.audio(data, format=audio_format, autoplay=True, start_time=offset)


def init_state():
    st.session_state.setdefault("user_name", "")
    st.session_state.setdefault("seed", 1)
    st.session_state.setdefault("group_id", None)
    st.session_state.setdefault("questions", [])
    st.session_state.setdefault("q_index", 0)
    st.session_state.setdefault("correct", 0)
    st.session_state.setdefault("main_points", 0.0)
    st.session_state.setdefault("spartan_points", 0.0)
    st.session_state.setdefault("streak", 0)
    st.session_state.setdefault("answers", [])
    st.session_state.setdefault("score_saved", False)
    st.session_state.setdefault("last_saved_key", None)
    st.session_state.setdefault("score_load_error", None)
    st.session_state.setdefault("spartan_mode", False)
    st.session_state.setdefault("spartan_pending", [])
    st.session_state.setdefault("in_spartan_round", False)
    st.session_state.setdefault("spartan_current_q_idx", None)
    st.session_state.setdefault("spartan_attempts", 0)
    st.session_state.setdefault("spartan_correct_count", 0)
    st.session_state.setdefault("quiz_direction", "eo_to_ja")
    # UI State
    st.session_state.setdefault("showing_result", False)
    st.session_state.setdefault("last_result_msg", "")
    st.session_state.setdefault("last_is_correct", False)
    st.session_state.setdefault("last_correct_answer", "")
    st.session_state.setdefault("cached_scores", [])
    st.session_state.setdefault("show_option_audio", True)


def start_quiz(group, rng):
    questions = vg.build_questions_for_group(group, rng=rng, min_options=2, max_options=4)
    st.session_state.questions = questions
    st.session_state.q_index = 0
    st.session_state.correct = 0
    st.session_state.main_points = 0.0
    st.session_state.spartan_points = 0.0
    st.session_state.streak = 0
    st.session_state.answers = []
    st.session_state.score_saved = False
    st.session_state.last_saved_key = None
    st.session_state.showing_result = False
    st.session_state.spartan_pending = []
    st.session_state.in_spartan_round = False
    st.session_state.spartan_current_q_idx = None
    st.session_state.spartan_attempts = 0
    st.session_state.spartan_correct_count = 0


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
        .question-title {
            font-size: 22px !important;
            line-height: 1.3 !important;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
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
            "\n".join(
                [
                    f"- 基礎点: {BASE_POINTS} × レベル倍率 (初級1.0 / 中級1.3 / 上級1.6)",
                    f"- 連続正解ボーナス: 2問目以降の連続正解1回につき +{STREAK_BONUS}",
                    f"- 精度ボーナス: 最終正答率 × 問題数 × {ACCURACY_BONUS_PER_Q}",
                    "- スパルタ精度ボーナス: なし（復習分は基礎+難易度のみを0.7倍で加算）",
                    "- グループを出し切ると結果画面でボーナス込みの合計を表示します。",
                ]
            )
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
        st.checkbox(
            "スパルタモード（全問後に間違えた問題だけ正解するまでランダム出題・得点0.7倍）",
            key="spartan_mode",
            disabled=bool(st.session_state.questions),
        )
        st.selectbox(
            "出題方向",
            options=list(QUIZ_DIRECTIONS.keys()),
            format_func=lambda k: QUIZ_DIRECTIONS[k],
            key="quiz_direction",
            disabled=bool(st.session_state.questions),
        )
        st.checkbox(
            "選択肢の音声を表示",
            value=st.session_state.show_option_audio,
            key="show_option_audio",
            help="オフにすると選択肢ごとの音声プレイヤーを非表示にして軽量化します。",
        )
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
            st.session_state.main_points = 0.0
            st.session_state.spartan_points = 0.0
            st.session_state.streak = 0
            st.session_state.answers = []
            st.session_state.showing_result = False
            st.session_state.score_saved = False
            st.session_state.last_saved_key = None
            st.session_state.spartan_pending = []
            st.session_state.in_spartan_round = False
            st.session_state.spartan_current_q_idx = None
            st.session_state.spartan_attempts = 0
            st.session_state.spartan_correct_count = 0
            # ホームに戻る時はスコアを再読み込み
            st.session_state.cached_scores = load_scores(force_refresh=True)
            st.session_state.score_load_error = None
            st.rerun()

        st.markdown("---")
        st.markdown(
            "[📘 例文クイズはこちら](https://esperantowords4choicequizzes-tiexjo7fx5elylbsywxgxz.streamlit.app/)"
        )

    # スコア読み込み戦略:
    # 1. クイズ中（questionsがあり、結果画面でない）はAPIを呼ばない（キャッシュ使用）
    # 2. ホーム画面、結果画面、スコア保存直後はAPIを呼ぶ
    finished_quiz = (
        bool(st.session_state.questions)
        and st.session_state.q_index >= len(st.session_state.questions)
        and not st.session_state.in_spartan_round
    )
    should_load = (
        not st.session_state.questions
        or finished_quiz
        or st.session_state.score_saved
        or not st.session_state.cached_scores
    )

    if should_load:
        scores = load_scores(force_refresh=True)
        st.session_state.cached_scores = scores
    else:
        scores = st.session_state.cached_scores

    if st.session_state.get("score_load_error"):
        col_warn, col_btn = st.columns([4, 1])
        col_warn.warning(st.session_state.score_load_error)
        col_warn.caption("認証・通信エラー時のみ再試行してください。")
        if col_btn.button("再読み込み", key="retry_scores_vocab"):
            st.cache_data.clear()
            st.session_state.cached_scores = load_scores(force_refresh=True)
            st.session_state.score_load_error = None
            st.rerun()
    # サイドバーでユーザー名が入力されていれば累積を案内（scores読み込み後）
    user_total_vocab = None
    user_total_overall = None
    user_total_sentence = None
    if st.session_state.user_name and scores:
        with st.sidebar:
            st.markdown("---")
            user_total_vocab = sum(
                r.get("points", 0)
                for r in scores
                if r.get("user") == st.session_state.user_name and r.get("mode") != "sentence"
            )
            st.info(f"現在の累積（単語）: {user_total_vocab:.1f}")
            user_total_sentence = sum(
                r.get("points", 0)
                for r in scores
                if r.get("user") == st.session_state.user_name and r.get("mode") == "sentence"
            )
            # 全体累積（UserStats優先、なければログから集計）
            user_total_overall = None
            # クイズ中はネットアクセスを避け、ログ合計を優先
            in_quiz = bool(st.session_state.questions) and not st.session_state.showing_result
            overall_stats = None if in_quiz else load_rankings()
            if overall_stats:
                for row in overall_stats:
                    if row.get("user") == st.session_state.user_name:
                        try:
                            user_total_overall = float(row.get("total_points", 0))
                        except (ValueError, TypeError):
                            user_total_overall = 0.0
                        break
            # ログからの最新合計（語彙+文章）
            log_total = sum(r.get("points", 0) for r in scores if r.get("user") == st.session_state.user_name)
            if user_total_overall is None:
                user_total_overall = log_total
            else:
                # UserStatsが古い場合はログ合計を優先
                user_total_overall = max(user_total_overall, log_total)
            st.info(f"現在の累積（全体）: {user_total_overall:.1f}")
            if user_total_sentence is not None:
                if abs((user_total_vocab + user_total_sentence) - user_total_overall) > 0.5:
                    st.warning("累積（単語＋文章）と全体の合計に差分があります。少し時間をおいて再読み込みしてください。")

    # 古いセッション（フィールド欠落）を検出してリセット
    if st.session_state.questions:
        q0 = st.session_state.questions[0]
        if "prompt" not in q0 or "options" not in q0 or "answer_index" not in q0:
            st.session_state.questions = []
            st.session_state.q_index = 0
            st.session_state.correct = 0
            st.session_state.main_points = 0.0
            st.session_state.spartan_points = 0.0
            st.session_state.streak = 0
            st.session_state.answers = []
            st.session_state.showing_result = False
            st.warning("問題データを再生成します。サイドバーで再度『クイズ開始』を押してください。")

    if not st.session_state.questions:
        st.info("左のサイドバーからグループを選び、クイズを開始してください。")
        if scores:
            st.subheader("ランキング（単語のみ・ログ集計）")
            vocab_scores = [r for r in scores if r.get("mode") != "sentence"]
            _, vocab_today, vocab_month, vocab_hof = summarize_scores(vocab_scores)
            totals_vocab = {}
            for r in vocab_scores:
                u = r.get("user")
                totals_vocab[u] = totals_vocab.get(u, 0) + float(r.get("points", 0))

            import pandas as pd
            def to_df_log(d):
                if not d:
                    return pd.DataFrame(columns=["順位", "ユーザー", "得点"])
                items = sorted(d.items(), key=lambda x: x[1], reverse=True)
                data = [{"順位": i, "ユーザー": u, "得点": f"{p:.1f}"} for i, (u, p) in enumerate(items, 1)]
                return pd.DataFrame(data)

            tabs_log = st.tabs(["累積", "本日", "今月", f"殿堂（{HOF_THRESHOLD}点以上）"])
            tabs_log[0].dataframe(to_df_log(totals_vocab), use_container_width=True, hide_index=True)
            tabs_log[1].dataframe(to_df_log(vocab_today), use_container_width=True, hide_index=True)
            tabs_log[2].dataframe(to_df_log(vocab_month), use_container_width=True, hide_index=True)
            tabs_log[3].dataframe(to_df_log(vocab_hof), use_container_width=True, hide_index=True)

            st.subheader("ランキング（全体: 単語+文章）")
            show_rankings(scores)
        return

    q_index = st.session_state.q_index
    questions = st.session_state.questions
    # スパルタモードへの遷移判定
    if (
        q_index >= len(questions)
        and st.session_state.spartan_mode
        and st.session_state.spartan_pending
    ):
        st.session_state.in_spartan_round = True
    if (
        st.session_state.in_spartan_round
        and not st.session_state.spartan_pending
    ):
        st.session_state.in_spartan_round = False

    # 結果画面（通常モード or スパルタ未発動）
    if q_index >= len(questions) and not st.session_state.in_spartan_round:
        correct = st.session_state.correct
        total = len(questions)
        accuracy = correct / total if total else 0
        # スパルタ部の精度
        sp_attempts = st.session_state.spartan_attempts
        sp_correct = st.session_state.spartan_correct_count
        sp_accuracy = sp_correct / sp_attempts if sp_attempts else 0

        raw_points_main = st.session_state.main_points
        raw_points_spartan = st.session_state.spartan_points
        raw_points_total = raw_points_main + raw_points_spartan
        accuracy_bonus = accuracy * total * ACCURACY_BONUS_PER_Q
        spartan_scaled = raw_points_spartan * SPARTAN_SCORE_MULTIPLIER
        points = raw_points_main + accuracy_bonus + spartan_scaled
        st.subheader("結果")
        st.metric("正答率", f"{accuracy*100:.1f}%")
        st.metric("得点", f"{points:.1f}")
        if st.session_state.spartan_mode and sp_attempts:
            st.caption(f"スパルタモード: 復習分を通常の{SPARTAN_SCORE_MULTIPLIER*100:.0f}%で加算（精度ボーナスなし）")
            st.caption(f"スパルタ精度: {sp_accuracy*100:.1f}% ({sp_correct}/{sp_attempts})")
        st.write(f"正解 {correct} / {total}")
        st.write(
            f"内訳: 本編 基礎+難易度 {raw_points_main:.1f} / 精度ボーナス {accuracy_bonus:.1f}"
            f" / スパルタ 基礎+難易度 {raw_points_spartan:.1f}（精度ボーナスなし）"
            f" → 加算 {spartan_scaled:.1f}（{SPARTAN_SCORE_MULTIPLIER*100:.0f}%）"
        )
        st.caption("音声で再確認できます。")
        if st.session_state.user_name:
            existing_users = {r.get("user") for r in scores} if scores else set()
            if st.session_state.user_name in existing_users:
                st.info("このユーザー名は既にスコアがあります。累積に加算します。")
            if st.session_state.score_saved:
                st.success("スコアを保存しました！")
            else:
                st.caption("保存するとランキングにも反映されます。失敗したらもう一度お試しください。")
                if st.button("スコアを保存", key="save_score_btn", use_container_width=True):
                    now = datetime.datetime.utcnow().isoformat()
                    record = {
                        "user": st.session_state.user_name,
                        "group_id": st.session_state.group_id,
                        "seed": st.session_state.seed,
                        "correct": correct,
                        "total": total,
                        "accuracy": accuracy,
                        "points": points,
                        "raw_points_total": raw_points_total,
                        "raw_points_main": raw_points_main,
                        "raw_points_spartan": raw_points_spartan,
                        "accuracy_bonus_main": accuracy_bonus,
                        "accuracy_bonus_spartan": 0.0,
                        "spartan_scaled_points": spartan_scaled,
                        "spartan_attempts": sp_attempts,
                        "spartan_correct": sp_correct,
                        "spartan_accuracy": sp_accuracy,
                        "accuracy_bonus": accuracy_bonus,
                        "spartan_mode": st.session_state.spartan_mode,
                        "direction": st.session_state.quiz_direction,
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

        if scores:
            with st.expander("最近のスコア", expanded=False):
                # 列順を軽く整える（存在する列のみ）
                import pandas as pd
                preferred_cols = [
                    "ts",
                    "user",
                    "points",
                    "accuracy",
                    "correct",
                    "total",
                    "group_id",
                    "seed",
                    "direction",
                    "spartan_mode",
                    "raw_points_main",
                    "raw_points_spartan",
                    "spartan_scaled_points",
                    "spartan_attempts",
                    "spartan_correct",
                    "spartan_accuracy",
                    "accuracy_bonus_main",
                ]
                df_recent = pd.DataFrame(scores)
                cols = [c for c in preferred_cols if c in df_recent.columns] if not df_recent.empty else []
                if cols:
                    df_recent = df_recent[cols + [c for c in df_recent.columns if c not in cols]]
                st.dataframe(df_recent, hide_index=True, use_container_width=True)
            st.subheader("ランキング（単語のみ・ログ集計）")
            vocab_scores = [r for r in scores if r.get("mode") != "sentence"]
            totals_vocab = {}
            for r in vocab_scores:
                u = r.get("user")
                totals_vocab[u] = totals_vocab.get(u, 0) + float(r.get("points", 0))
            import pandas as pd
            def to_df_log(d):
                if not d:
                    return pd.DataFrame(columns=["順位", "ユーザー", "得点"])
                items = sorted(d.items(), key=lambda x: x[1], reverse=True)
                data = [{"順位": i, "ユーザー": u, "得点": f"{p:.1f}"} for i, (u, p) in enumerate(items, 1)]
                return pd.DataFrame(data)
            st.dataframe(to_df_log(totals_vocab), use_container_width=True, hide_index=True)
            st.subheader("ランキング（全体: 単語+文章）")
            show_rankings(load_rankings())

        # 復習セクション
        st.subheader("復習")
        wrong = []
        correct_list = []
        direction_review = st.session_state.quiz_direction
        for ans in st.session_state.answers:
            q = st.session_state.questions[ans["q_idx"]]
            selected = ans["selected"]
            correct_idx = ans["correct"]
            selected_text = ""
            if selected is not None:
                selected_text = q["options"][selected]["japanese"] if direction_review == "eo_to_ja" else q["options"][selected]["esperanto"]
            answer_text = q["options"][correct_idx]["japanese"]
            answer_eo = q["options"][correct_idx]["esperanto"]
            entry = {
                "prompt": q["prompt"],
                "selected": selected_text,
                "answer": answer_text,
                "answer_eo": answer_eo,
                "phase": ans.get("phase", "main"),
                "audio_key": q["options"][correct_idx]["audio_key"],
            }
            if selected == correct_idx:
                correct_list.append(entry)
            else:
                wrong.append(entry)

        if wrong:
            st.markdown("### 間違えた問題")
            st.caption("音声で再確認できます。")
            for w in wrong:
                st.write(f"- {w['prompt']}: 正解「{w['answer']} / {w['answer_eo']}」、あなたの回答「{w['selected']}」 ({w['phase']})")
                if w.get("audio_key"):
                    data, mime = find_audio(w["audio_key"])
                    if data:
                        st.audio(data, format=mime, start_time=0)
        if correct_list:
            st.markdown("### 正解した問題（確認用）")
            st.caption("音声で確認だけできます。")
            for c in correct_list:
                st.write(f"- {c['prompt']}: {c['answer']} / {c['answer_eo']} ({c['phase']})")
                if c.get("audio_key"):
                    data, mime = find_audio(c["audio_key"])
                    if data:
                        st.audio(data, format=mime, start_time=0)
        if st.button("もう一度同じグループで再挑戦", key="retry_btn"):
            group = next((g for g in load_groups(st.session_state.seed) if g.id == st.session_state.group_id), None)
            if group:
                rng = random.Random()
                start_quiz(group, rng=rng)
                st.rerun()
        return

    # 出題対象の選択（通常/スパルタ）
    in_spartan = st.session_state.in_spartan_round
    if in_spartan:
        pending = st.session_state.spartan_pending
        if not pending:
            st.session_state.in_spartan_round = False
            st.rerun()
        if (
            st.session_state.spartan_current_q_idx is None
            or st.session_state.spartan_current_q_idx not in pending
        ):
            st.session_state.spartan_current_q_idx = random.choice(pending)
        current_q_idx = st.session_state.spartan_current_q_idx
    else:
        current_q_idx = q_index

    question = questions[current_q_idx]
    audio_key = question["options"][question["answer_index"]].get("audio_key")
    direction = st.session_state.quiz_direction

    # スマホ対応: 回答ボタンのスタイル（PCとモバイルで高さを変える）
    # 日本語の意味表示（eo_to_ja）は文字数が多いので少し小さめに
    # 長い日本語が入る eo_to_ja では少しフォントを落とす
    if direction == "eo_to_ja":
        base_font = "18px"
        mobile_font = "16px"
    else:
        base_font = "24px"
        mobile_font = "20px"
    st.markdown(
        f"""
        <style>
        /* PC用: 回答ボタンを固定サイズに統一 */
        .stButton button {{
            height: 120px;
            min-height: 120px;
            max-height: 120px;
            width: 100% !important;
            white-space: normal;
            overflow: hidden;
            text-overflow: ellipsis;
            font-size: {base_font} !important;
            font-weight: 700 !important;
            line-height: 1.35 !important;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 12px;
        }}
        /* ボタン内部のテキストにも適用（Streamlitが入れるラッパー用） */
        .stButton button p, .stButton button div, .stButton button span {{
            font-size: {base_font} !important;
            font-weight: 700 !important;
            line-height: 1.35 !important;
        }}
        /* スマホ用: より小さい高さ */
        @media (max-width: 768px) {{
            .stButton button {{
                height: 80px;
                min-height: 80px;
                max-height: 80px;
                font-size: {mobile_font} !important;
                font-weight: 700 !important;
                line-height: 1.35 !important;
                padding: 8px;
            }}
            .stButton button p, .stButton button div, .stButton button span {{
                font-size: {mobile_font} !important;
                font-weight: 700 !important;
                line-height: 1.35 !important;
            }}
        }}
        .question-title {{
            font-size: { "20px" if direction == "ja_to_eo" else "22px" } !important;
            line-height: 1.3 !important;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 出題単語（一番上に大きく表示）
    if direction == "ja_to_eo":
        prompt_display = question["options"][question["answer_index"]]["japanese"]
        option_labels = [opt["esperanto"] for opt in question["options"]]
    else:
        prompt_display = question["prompt"]
        option_labels = [opt["japanese"] for opt in question["options"]]
        # エス→日では問題文の音声を出題時に自動再生（下部には重複表示しない）
        if audio_key and not st.session_state.showing_result:
            st.caption(f"🔊 発音を聞く（問題文・自動再生）【{audio_key}】")
            simple_audio_player(audio_key, question_index=q_index, instance="prompt")

    if in_spartan:
        st.subheader(f"スパルタ復習 残り{len(st.session_state.spartan_pending)}問 / 全{len(questions)}問")
        st.caption("間違えた問題のみをランダムに出題しています。正解でリストから消えます。")
        title_prefix = "復習"
    else:
        title_prefix = f"Q{q_index+1}/{len(questions)}"
    title_html = f"<h3 class='question-title'>{title_prefix}: {prompt_display}</h3>"
    st.markdown(title_html, unsafe_allow_html=True)
    # 進捗インジケータ（モバイルで邪魔にならないよう小さめ）
    total_questions = len(questions)
    correct_so_far = st.session_state.correct
    remaining = len(st.session_state.spartan_pending) if in_spartan else max(total_questions - st.session_state.q_index, 0)
    st.markdown(
        """
        <style>
        .mini-metrics {font-size: 12px; line-height: 1.2; margin-top: -4px; color: #0b6623;}
        .mini-metrics strong {font-size: 14px; color: #0e8a2c;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    col_left, _ = st.columns([2, 5], gap="small")
    with col_left:
        cols_prog = st.columns([1, 1, 1], gap="small")
        cols_prog[0].markdown(f"<div class='mini-metrics'>正解数<br><strong>{correct_so_far}/{total_questions}</strong></div>", unsafe_allow_html=True)
        cols_prog[1].markdown(f"<div class='mini-metrics'>連続正解<br><strong>{st.session_state.streak}回</strong></div>", unsafe_allow_html=True)
        cols_prog[2].markdown(f"<div class='mini-metrics'>残り<br><strong>{remaining}問</strong></div>", unsafe_allow_html=True)

    # 結果表示モードの場合
    showing_result = st.session_state.showing_result
    if showing_result:
        # 結果を表示
        if st.session_state.last_is_correct:
            st.success(st.session_state.last_result_msg)
        else:
            st.error(st.session_state.last_result_msg)

        # 問題文の音声（結果画面でのみ再生）
        if audio_key:
            st.markdown("---")
            st.caption(f"🔊 発音を確認（自動再生）【{audio_key}】")
            simple_audio_player(audio_key, question_index=q_index, instance="result")

        # 「次へ」ボタン
        if st.button("次へ進む", type="primary", use_container_width=True, key=f"next_btn_{st.session_state.q_index}_{'sp' if in_spartan else 'main'}"):
            if in_spartan:
                st.session_state.showing_result = False
                st.session_state.spartan_current_q_idx = None
            else:
                st.session_state.q_index += 1
                st.session_state.showing_result = False
            st.rerun()
        return

    # 回答待ちモード: 4択ボタンを出題直下に配置（出題方向でラベル切り替え）
    clicked_index = None
    # 4択の各選択肢の音声は常に表示（方向に関わらず）
    show_audio = st.session_state.get("show_option_audio", True)

    for row_start in range(0, len(option_labels), 2):
        cols = st.columns([1, 1], gap="medium")
        for j in range(2):
            idx = row_start + j
            if idx >= len(option_labels):
                continue
            with cols[j]:
                button_key = f"opt-{current_q_idx}-{idx}-{'sp' if in_spartan else 'main'}"
                if st.button(option_labels[idx], key=button_key, use_container_width=True, type="primary"):
                    clicked_index = idx
                if show_audio:
                    opt_audio = question["options"][idx]["audio_key"]
                    if opt_audio:
                        data, mime = find_audio(opt_audio)
                        if data:
                            st.audio(data, format=mime, start_time=0)


    if clicked_index is not None:
        is_correct = clicked_index == question["answer_index"]
        if in_spartan:
            st.session_state.spartan_attempts += 1
        st.session_state.answers.append(
            {
                "q_idx": current_q_idx,
                "q": question["prompt"],
                "selected": clicked_index,
                "correct": question["answer_index"],
                "phase": "spartan" if in_spartan else "main",
            }
        )

        if is_correct:
            # 正解時は即座に次へ（ユーザー要望）
            factor = get_stage_factor(question["stages"])
            st.session_state.streak += 1
            streak_bonus = max(0, st.session_state.streak - 1) * STREAK_BONUS
            earned = BASE_POINTS * factor + streak_bonus

            if not in_spartan:
                st.session_state.main_points += earned
                st.session_state.correct += 1
                st.session_state.q_index += 1
                st.session_state.showing_result = False
            else:
                st.session_state.spartan_points += earned
                st.session_state.spartan_correct_count += 1
                # 復習リストから除外して次のランダムへ
                st.session_state.spartan_pending = [
                    idx for idx in st.session_state.spartan_pending if idx != current_q_idx
                ]
                st.session_state.spartan_current_q_idx = None
                st.session_state.showing_result = False
                if not st.session_state.spartan_pending:
                    st.session_state.in_spartan_round = False
            st.rerun()
        else:
            # 不正解時は正解を表示して一時停止
            msg = f"不正解。正解: {option_labels[question['answer_index']]}"
            st.session_state.streak = 0
            # 初回フェーズでの誤答はスパルタ対象に追加
            if st.session_state.spartan_mode and not in_spartan:
                if current_q_idx not in st.session_state.spartan_pending:
                    st.session_state.spartan_pending.append(current_q_idx)

            # 結果表示モードへ移行
            st.session_state.showing_result = True
            st.session_state.last_result_msg = msg
            st.session_state.last_is_correct = False
            st.session_state.last_correct_answer = option_labels[question['answer_index']]
            st.rerun()


if __name__ == "__main__":
    main()
