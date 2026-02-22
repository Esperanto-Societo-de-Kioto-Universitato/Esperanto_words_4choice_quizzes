import datetime
import random
import uuid
import tempfile
from pathlib import Path

import streamlit as st
import pandas as pd

import vocab_grouping as vg

# パス설정
# 語彙データ（日本語を含む多言語版）
CSV_PATH = Path("2890 Gravaj Esperantaj Vortoj kun Signifoj en la Japana, Ĉina kaj Korea_251129_plajnova.csv")
AUDIO_DIR = Path("audio")
SCORE_FILE = Path("scores.json")

# スコア설정
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
# スパルタモード時の점수係数（通常の約7割）
SPARTAN_SCORE_MULTIPLIER = 0.7
# 殿堂入りライン
HOF_THRESHOLD = 1000000
MOBILE_UA_TOKENS = (
    "iphone",
    "ipad",
    "ipod",
    "android",
    "mobile",
)

POS_JP = {
    "noun": "명사",
    "verb": "동사",
    "adjective": "형용사",
    "adverb": "부사",
    "preposition": "전치사",
    "conjunction": "접속사",
    "prefix": "접두사",
    "suffix": "접미사",
    "correlative": "상관사",
    "numeral": "수사",
    "bare_adverb": "원형 부사",
    "pronoun": "대명사",
    "other": "기타",
}

STAGE_JP = {
    "beginner": "초급",
    "intermediate": "중급",
    "advanced": "상급",
}

# 출제 방향
QUIZ_DIRECTIONS = {
    "eo_to_ja": "에스페란토 → 한국어",
    "ja_to_eo": "한국어 → 에스페란토",
}


@st.cache_data
def load_groups(seed: int):
    df = pd.read_csv(CSV_PATH)
    if "Korean_Trans" in df.columns:
        df["Japanese_Trans"] = df["Korean_Trans"]
    tmp = Path(tempfile.gettempdir()) / "vocab_ko_temp.csv"
    df.to_csv(tmp, index=False)
    return vg.build_groups(tmp, seed=seed, audio_key_fn=vg._default_audio_key)


def is_mobile_client() -> bool:
    """헤더(Client Hints 포함) + URL 파라미터로 모바일 여부를 판정한다."""
    try:
        headers = st.context.headers
    except Exception:
        headers = {}
    normalized = {str(k).lower(): str(v).lower() for k, v in dict(headers).items()}
    ua = normalized.get("user-agent", "")
    ch_mobile = normalized.get("sec-ch-ua-mobile", "")
    ch_platform = normalized.get("sec-ch-ua-platform", "")
    qp_mobile = str(st.query_params.get("mobile", "")).strip().lower()

    if qp_mobile in {"1", "true", "yes", "on"}:
        return True
    if ch_mobile in {"?1", "1", "true"}:
        return True
    if any(token in ch_platform for token in ("android", "ios", "iphone", "ipad")):
        return True
    return any(token in ua for token in MOBILE_UA_TOKENS)


from streamlit_gsheets import GSheetsConnection


# -------- Google Sheets 連携 --------
# ローカルのJSONではなく、Google Sheetsをデータベースとして使用する
# 事前に .streamlit/secrets.toml に認証情報を설정する必要がある

def get_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"Google Sheets 연결 초기화에 실패했습니다: {e}")
        return None

def load_scores(force_refresh: bool = False):
    """Google Sheetsからスコアを読み込む"""
    conn = get_connection()
    if conn is None:
        st.session_state.score_load_error = "Google Sheets 연결을 초기화할 수 없습니다."
        return []
    try:
        # ワークシート "Scores" からデータを読み込む
        # API制限（1分間に60リクエスト）を回避するため、キャッシュ有効時間を설정
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
        st.session_state.score_load_error = f"랭킹을 불러오지 못했습니다: {e}"
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
        st.error(f"점수 저장에 실패했습니다: {e}")
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
    # JSTタイムゾーン설정 (UTC+9)
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
    tabs = st.tabs(["누적", "오늘", "이번 달", f"명예의 전당({HOF_THRESHOLD}점 이상)"])
    import pandas as pd

    def to_df(d):
        if not d:
            return pd.DataFrame(columns=["순위", "사용자", "점수"])
        # 점수順にソート
        items = sorted(d.items(), key=lambda x: x[1], reverse=True)
        # データフレーム化 (順位をつける)
        data = []
        for i, (u, p) in enumerate(items, 1):
            data.append({"순위": i, "사용자": u, "점수": f"{p:.1f}"})
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
    return f"{POS_JP.get(group.pos, group.pos)} / {stage_label} / 그룹{gid_num} ({group.size}어)"


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
        st.info("오디오 파일 없음")
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
        page_title="에스페란토 단어 퀴즈",
        page_icon="💚",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    is_mobile = is_mobile_client()
    if "mobile_compact_ui" not in st.session_state:
        st.session_state.mobile_compact_ui = is_mobile
    if "compact_hide_option_audio" not in st.session_state:
        st.session_state.compact_hide_option_audio = True
    if "compact_hide_prompt_audio" not in st.session_state:
        st.session_state.compact_hide_prompt_audio = True
    if "mobile_ultra_compact" not in st.session_state:
        st.session_state.mobile_ultra_compact = is_mobile
    if "mobile_hide_streamlit_chrome" not in st.session_state:
        st.session_state.mobile_hide_streamlit_chrome = False

    compact_ui = bool(st.session_state.mobile_compact_ui)
    ultra_compact_ui = compact_ui and bool(st.session_state.mobile_ultra_compact)
    direction_for_style = st.session_state.get("quiz_direction", "eo_to_ja")
    base_font = "18px" if direction_for_style == "eo_to_ja" else "24px"
    mobile_font = (
        "34px"
        if (ultra_compact_ui and direction_for_style == "eo_to_ja")
        else (
            "38px"
            if ultra_compact_ui
            else (
                "32px"
                if (compact_ui and direction_for_style == "eo_to_ja")
                else ("36px" if compact_ui else ("24px" if direction_for_style == "eo_to_ja" else "30px"))
            )
        )
    )
    mobile_button_height = "160px" if ultra_compact_ui else ("180px" if compact_ui else "200px")
    mobile_button_padding = "10px" if ultra_compact_ui else ("12px" if compact_ui else "14px")
    mobile_main_title_font = "18px" if ultra_compact_ui else ("20px" if compact_ui else "24px")
    mobile_question_font = (
        "44px"
        if ultra_compact_ui
        else ("50px" if compact_ui else ("56px" if direction_for_style == "ja_to_eo" else "60px"))
    )
    mobile_page_top_padding = "0.15rem" if ultra_compact_ui else ("0.35rem" if compact_ui else "0.9rem")
    mobile_page_bottom_padding = "0.2rem" if ultra_compact_ui else ("0.4rem" if compact_ui else "0.7rem")
    show_main_title = not (compact_ui and bool(st.session_state.get("questions")))
    main_title_html = "<div class='main-title'>에스페란토 단어 4지선다 퀴즈</div>" if show_main_title else ""
    mobile_chrome_css = (
        """
            div[data-testid="stToolbar"] {display: none !important;}
            #MainMenu {visibility: hidden !important;}
            footer {display: none !important;}
        """
        if st.session_state.mobile_hide_streamlit_chrome
        else ""
    )

    # エスペラント・グリーン (#009900) を基調としたテーマ설정
    st.markdown(
        f"""
        <style>
        @media (max-width: 768px) {{
            {mobile_chrome_css}
            .block-container {{
                padding-top: {mobile_page_top_padding} !important;
                padding-bottom: {mobile_page_bottom_padding} !important;
            }}
        }}
        div.stButton > button[kind="primary"] {{
            background-color: #009900 !important;
            border-color: #009900 !important;
            color: white !important;
            font-size: {base_font} !important;
            font-weight: 700 !important;
            line-height: 1.35 !important;
        }}
        div.stButton > button[kind="primary"]:hover {{
            background-color: #007700 !important;
            border-color: #007700 !important;
        }}
        div.stButton > button[kind="primary"]:active {{
            background-color: #005500 !important;
            border-color: #005500 !important;
        }}
        div.stButton > button[kind="secondary"] {{
            border-color: #009900 !important;
        }}
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
        .stButton button p, .stButton button div, .stButton button span {{
            font-size: {base_font} !important;
            font-weight: 700 !important;
            line-height: 1.35 !important;
        }}
        @media (max-width: 768px) {{
            .stButton button {{
                height: {mobile_button_height};
                min-height: {mobile_button_height};
                max-height: {mobile_button_height};
                font-size: {mobile_font} !important;
                font-weight: 700 !important;
                line-height: 1.35 !important;
                padding: {mobile_button_padding};
            }}
            .stButton button p, .stButton button div, .stButton button span {{
                font-size: {mobile_font} !important;
                font-weight: 700 !important;
                line-height: 1.35 !important;
            }}
            .stButton {{
                margin-bottom: 0.2rem !important;
            }}
            p {{
                margin-block-start: 0.2rem;
                margin-block-end: 0.2rem;
            }}
        }}
        .main-title {{
            font-size: 24px;
            font-weight: bold;
            color: #009900;
            margin-bottom: 10px;
            white-space: nowrap;
        }}
        .question-title {{
            font-size: {"20px" if direction_for_style == "ja_to_eo" else "22px"} !important;
            line-height: 1.3 !important;
            margin-top: 0.5rem;
            margin-bottom: 0.75rem;
        }}
        @media (max-width: 768px) {{
            .main-title {{
                font-size: {mobile_main_title_font} !important;
                margin-bottom: 0.3rem !important;
            }}
            .question-title {{
                font-size: {mobile_question_font} !important;
                line-height: 1.25 !important;
                margin-top: 0.2rem !important;
                margin-bottom: 0.45rem !important;
            }}
            .question-box.tight {{
                max-height: none;
                overflow: visible;
                margin-bottom: 0.35rem;
                padding-top: 0.35rem;
                padding-right: 0;
            }}
            .question-box.tight .question-title {{
                margin-top: 0.25rem !important;
                margin-bottom: 0.2rem !important;
            }}
            .compact-progress {{
                font-size: 24px;
                color: #0b6623;
                margin: 0.1rem 0 0.3rem 0;
            }}
            .compact-progress strong {{
                color: #0e8a2c;
            }}
            .question-audio-hint {{
                font-size: 22px;
                color: #0b6623;
                margin-bottom: 0.15rem;
            }}
        }}
        @media (max-width: 420px) {{
            .question-box.tight {{
                max-height: none;
            }}
            .stButton button {{
                height: 132px !important;
                min-height: 132px !important;
                max-height: 132px !important;
                padding: 8px !important;
                font-size: 30px !important;
            }}
            .stButton button p, .stButton button div, .stButton button span, .stButton button * {{
                font-size: 30px !important;
                line-height: 1.3 !important;
            }}
        }}
        </style>
        {main_title_html}
        """,
        unsafe_allow_html=True,
    )

    # モバイル用: 音声自動再生のアンロックスクリプト（グローバルに1回だけ挿入）
    # ユーザーが画面のどこかをタップしたら、サイレント音声を再生して
    # 以降の自動再生を可能にする
    st.markdown(
        """
        <script>
        (function() {
            try {
                const isNarrow = window.innerWidth <= 768;
                const params = new URLSearchParams(window.location.search);
                const already = sessionStorage.getItem("mobile_query_bootstrapped") === "1";
                if (isNarrow && params.get("mobile") !== "1" && !already) {
                    params.set("mobile", "1");
                    sessionStorage.setItem("mobile_query_bootstrapped", "1");
                    const target = window.location.pathname + "?" + params.toString() + window.location.hash;
                    window.location.replace(target);
                    return;
                }
            } catch (_) {}
        })();

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

    show_intro_block = not (compact_ui and bool(st.session_state.get("questions")))
    if show_intro_block:
        st.write("품사×레벨로 그룹화한 단어에서 출제합니다. 시드를 바꾸면 그룹과 순서가 달라집니다.")
        with st.expander("점수 계산 규칙"):
            st.markdown(
                "\n".join(
                    [
                        f"- 기본점: {BASE_POINTS} × 레벨 배율 (초급1.0 / 중급1.3 / 상급1.6)",
                        f"- 연속 정답 보너스: 2문제째부터 연속 정답 1회당 +{STREAK_BONUS}",
                        f"- 정확도 보너스: 최종 정답률 × 문제수 × {ACCURACY_BONUS_PER_Q}",
                        "- 스파르타 정확도 보너스: 없음(복습분은 기본+난이도만 0.7배로 합산)",
                        "- 그룹을 모두 풀면 결과 화면에 보너스 포함 합계를 표시합니다.",
                    ]
                )
            )

    with st.sidebar:
        st.header("설정")
        # keyを指定することでステート管理をStreamlitに任せる
        user_name = st.text_input("사용자명(점수 저장용)", key="user_name")
        seed = st.number_input("랜덤 시드 (1-8192)", min_value=1, max_value=8192, step=1, key="seed")
        # st.session_state.seed = seed # key="seed"にしたので不要
        # st.session_state.shuffle_every_time = st.checkbox("毎回ランダムに並べる（シード無視）", value=st.session_state.shuffle_every_time)
        groups = load_groups(seed)
        pos_list = sorted({g.pos for g in groups})
        pos_label_map = {p: POS_JP.get(p, p) for p in pos_list}
        pos_choice = st.selectbox("품사를 선택", pos_list, format_func=lambda p: pos_label_map.get(p, p), key="pos_select")
        group_options = [g for g in groups if g.pos == pos_choice]
        group_labels = [format_group_label(g) for g in group_options]
        choice = st.selectbox("그룹을 선택", group_labels)
        selected_group = group_options[group_labels.index(choice)] if group_options else None
        st.checkbox(
            "스파르타 모드(모든 문제 후 틀린 것만 정답할 때까지 무작위 출제 · 점수 0.7배)",
            key="spartan_mode",
            disabled=bool(st.session_state.questions),
        )
        st.selectbox(
            "출제 방향",
            options=list(QUIZ_DIRECTIONS.keys()),
            format_func=lambda k: QUIZ_DIRECTIONS[k],
            key="quiz_direction",
            disabled=bool(st.session_state.questions),
        )
        st.checkbox(
            "선택지의 음성을 표시",
            value=st.session_state.show_option_audio,
            key="show_option_audio",
            help="OFF로 하면 선택지별 오디오 플레이어를 숨겨 가볍게 합니다.",
        )
        st.checkbox(
            "모바일 최적화 UI(문항+4지선다를 한 화면 우선)",
            key="mobile_compact_ui",
            help="모바일에서는 ON 권장. 데스크톱 표시에는 영향이 없습니다.",
        )
        if st.session_state.mobile_compact_ui:
            st.checkbox(
                "모바일 최적화 시 선택지 음성을 자동으로 숨기기",
                key="compact_hide_option_audio",
                help="문항 음성은 유지하고, 선택지별 음성만 숨겨 세로 스크롤을 줄입니다.",
            )
            st.checkbox(
                "모바일 최적화 시 문제문 음성 플레이어 숨기기",
                key="compact_hide_prompt_audio",
                help="문항+4지선다를 한 화면에 담기 쉽게 합니다. 필요할 때만 OFF로 바꿔 표시하세요.",
            )
            st.checkbox(
                "초압축 모드(소형 화면용)",
                key="mobile_ultra_compact",
                help="문항 영역과 버튼을 더 압축합니다.",
            )
            st.checkbox(
                "모바일에서 상단 메뉴 숨기기",
                key="mobile_hide_streamlit_chrome",
                help="세로 공간을 늘립니다. 원래대로 돌리려면 OFF로 바꾸세요.",
            )
        st.caption(
            f"기기 판정: {'모바일' if is_mobile else '데스크톱'} / "
            f"최적화 UI: {'ON' if st.session_state.mobile_compact_ui else 'OFF'}"
        )
        if st.button("퀴즈 시작", disabled=not selected_group, use_container_width=True):
            # 出題順は常にランダム（シードはグループ分けのみに使用）
            rng = random.Random()
            start_quiz(selected_group, rng=rng)
            st.session_state.group_id = selected_group.id

        st.markdown("---")
        # ホームに戻るボタンを퀴즈 시작ボタンと同様に横幅可変にし、見た目を揃える
        if st.button("🏠 홈으로 돌아가기", use_container_width=True, type="primary", key="home-btn"):
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
            # ホームに戻る時はスコアを다시 불러오기
            st.session_state.cached_scores = load_scores(force_refresh=True)
            st.session_state.score_load_error = None
            st.rerun()

        st.markdown("---")
        st.markdown(
            "[📘 예문 퀴즈는 여기](https://esperantowords4choicequizzes-korea-version-frazoj.streamlit.app/)"
        )

    # スコア読み込み戦略:
    # 1. クイズ中（questionsがあり、결과画面でない）はAPIを呼ばない（キャッシュ使用）
    # 2. ホーム画面、결과画面、スコア保存直後はAPIを呼ぶ
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
        col_warn.caption("인증·통신 오류일 때만 다시 시도하세요.")
        if col_btn.button("다시 불러오기", key="retry_scores_vocab"):
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
            st.info(f"현재 누적(단어): {user_total_vocab:.1f}")
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
            st.info(f"현재 누적(전체): {user_total_overall:.1f}")
            if user_total_sentence is not None:
                if abs((user_total_vocab + user_total_sentence) - user_total_overall) > 0.5:
                    st.warning("누적(단어+예문)과 전체 합계에 차이가 있습니다. 잠시 후 다시 불러와 주세요.")

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
            st.warning("문제 데이터를 다시 생성합니다. 사이드바에서 다시 '퀴즈 시작'을 눌러주세요.")

    if not st.session_state.questions:
        st.info("왼쪽 사이드바에서 그룹을 선택해 퀴즈를 시작하세요.")
        if scores:
            st.subheader("랭킹(단어 전용 · 로그 집계)")
            vocab_scores = [r for r in scores if r.get("mode") != "sentence"]
            _, vocab_today, vocab_month, vocab_hof = summarize_scores(vocab_scores)
            totals_vocab = {}
            for r in vocab_scores:
                u = r.get("user")
                totals_vocab[u] = totals_vocab.get(u, 0) + float(r.get("points", 0))

            import pandas as pd
            def to_df_log(d):
                if not d:
                    return pd.DataFrame(columns=["순위", "사용자", "점수"])
                items = sorted(d.items(), key=lambda x: x[1], reverse=True)
                data = [{"순위": i, "사용자": u, "점수": f"{p:.1f}"} for i, (u, p) in enumerate(items, 1)]
                return pd.DataFrame(data)

            tabs_log = st.tabs(["누적", "오늘", "이번 달", f"명예의 전당({HOF_THRESHOLD}점 이상)"])
            tabs_log[0].dataframe(to_df_log(totals_vocab), use_container_width=True, hide_index=True)
            tabs_log[1].dataframe(to_df_log(vocab_today), use_container_width=True, hide_index=True)
            tabs_log[2].dataframe(to_df_log(vocab_month), use_container_width=True, hide_index=True)
            tabs_log[3].dataframe(to_df_log(vocab_hof), use_container_width=True, hide_index=True)

            st.subheader("랭킹(전체: 단어+예문)")
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

    # 결과画面（通常モード or スパルタ未発動）
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
        st.subheader("결과")
        st.metric("정답률", f"{accuracy*100:.1f}%")
        st.metric("점수", f"{points:.1f}")
        if st.session_state.spartan_mode and sp_attempts:
            st.caption(f"스파르타 모드: 복습분을 일반의{SPARTAN_SCORE_MULTIPLIER*100:.0f}%로 합산(정확도 보너스 없음)")
            st.caption(f"스파르타 정확도: {sp_accuracy*100:.1f}% ({sp_correct}/{sp_attempts})")
        st.write(f"정답 {correct} / {total}")
        st.write(
            f"내역: 본편 기본+난이도 {raw_points_main:.1f} / 정확도 보너스 {accuracy_bonus:.1f}"
            f" / 스파르타 기본+난이도 {raw_points_spartan:.1f}(정확도 보너스 없음)"
            f" → 합산 {spartan_scaled:.1f}({SPARTAN_SCORE_MULTIPLIER*100:.0f}%)"
        )
        st.caption("음성으로 다시 확인할 수 있습니다.")
        if st.session_state.user_name:
            existing_users = {r.get("user") for r in scores} if scores else set()
            if st.session_state.user_name in existing_users:
                st.info("이 사용자명은 이미 점수가 있습니다. 누적에 합산합니다.")
            if st.session_state.score_saved:
                st.success("점수를 저장했습니다!")
            else:
                st.caption("저장하면 랭킹에도 반영됩니다. 실패하면 다시 시도해주세요.")
                if st.button("점수 저장", key="save_score_btn", use_container_width=True):
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
                        st.error("저장에 실패했습니다. secrets 설정을 확인해주세요.")

        if scores:
            with st.expander("최근 점수", expanded=False):
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
            st.subheader("랭킹(단어 전용 · 로그 집계)")
            vocab_scores = [r for r in scores if r.get("mode") != "sentence"]
            totals_vocab = {}
            for r in vocab_scores:
                u = r.get("user")
                totals_vocab[u] = totals_vocab.get(u, 0) + float(r.get("points", 0))
            import pandas as pd
            def to_df_log(d):
                if not d:
                    return pd.DataFrame(columns=["순위", "사용자", "점수"])
                items = sorted(d.items(), key=lambda x: x[1], reverse=True)
                data = [{"순위": i, "사용자": u, "점수": f"{p:.1f}"} for i, (u, p) in enumerate(items, 1)]
                return pd.DataFrame(data)
            st.dataframe(to_df_log(totals_vocab), use_container_width=True, hide_index=True)
            st.subheader("랭킹(전체: 단어+예문)")
            show_rankings(load_rankings())

        # 복습セクション
        st.subheader("복습")
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
            st.markdown("### 틀린 문제")
            st.caption("음성으로 다시 확인할 수 있습니다.")
            for w in wrong:
                st.write(f"- {w['prompt']}: 정답「{w['answer']} / {w['answer_eo']}」, 당신의 답변「{w['selected']}」 ({w['phase']})")
                if w.get("audio_key"):
                    data, mime = find_audio(w["audio_key"])
                    if data:
                        st.audio(data, format=mime, start_time=0)
        if correct_list:
            st.markdown("### 정답한 문제(확인용)")
            st.caption("음성으로 확인만 가능합니다.")
            for c in correct_list:
                st.write(f"- {c['prompt']}: {c['answer']} / {c['answer_eo']} ({c['phase']})")
                if c.get("audio_key"):
                    data, mime = find_audio(c["audio_key"])
                    if data:
                        st.audio(data, format=mime, start_time=0)
        if st.button("같은 그룹으로 다시 도전", key="retry_btn"):
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
    compact_question_ui = bool(st.session_state.get("mobile_compact_ui", False))

    # 出題単語（一番上に大きく表示）
    if direction == "ja_to_eo":
        prompt_display = question["options"][question["answer_index"]]["japanese"]
        option_labels = [opt["esperanto"] for opt in question["options"]]
    else:
        prompt_display = question["prompt"]
        option_labels = [opt["japanese"] for opt in question["options"]]
        # エス→日では問題文の音声を出題時に自動再生（下部には重複表示しない）
        if audio_key and not st.session_state.showing_result:
            hide_prompt_audio = compact_question_ui and st.session_state.get("compact_hide_prompt_audio", True)
            if not hide_prompt_audio:
                if not compact_question_ui:
                    st.caption(f"🔊 발음 듣기(문제문·자동 재생)【{audio_key}】")
                simple_audio_player(audio_key, question_index=q_index, instance="prompt")
            else:
                st.markdown("<div class='question-audio-hint'>🔇 문제문 음성은 모바일 최적화에서 숨김</div>", unsafe_allow_html=True)

    if in_spartan:
        if not compact_question_ui:
            st.subheader(f"스파르타 복습 남은 {len(st.session_state.spartan_pending)}문제 / 총{len(questions)}문제")
            st.caption("틀린 문제만 무작위로 출제합니다. 정답하면 목록에서 사라집니다.")
        title_prefix = "복습"
    else:
        title_prefix = f"Q{q_index+1}/{len(questions)}"
    question_box_cls = "question-box tight" if ultra_compact_ui else "question-box"
    st.markdown(
        f"<div class='{question_box_cls}'><h3 class='question-title'>{title_prefix}: {prompt_display}</h3></div>",
        unsafe_allow_html=True,
    )
    # 進捗インジケータ（モバイルで邪魔にならないよう小さめ）
    total_questions = len(questions)
    correct_so_far = st.session_state.correct
    remaining = len(st.session_state.spartan_pending) if in_spartan else max(total_questions - st.session_state.q_index, 0)
    if compact_question_ui:
        st.markdown(
            f"<div class='compact-progress'>"
            f"정답 <strong>{correct_so_far}/{total_questions}</strong> ・ "
            f"연속 <strong>{st.session_state.streak}회</strong> ・ "
            f"남은 <strong>{remaining}문제</strong>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            .mini-metrics {font-size: 14px; line-height: 1.2; margin-top: 0; color: #0b6623;}
            .mini-metrics strong {font-size: 16px; color: #0e8a2c;}
            </style>
            """,
            unsafe_allow_html=True,
        )
        col_left, _ = st.columns([2, 5], gap="small")
        with col_left:
            cols_prog = st.columns([1, 1, 1], gap="small")
            cols_prog[0].markdown(f"<div class='mini-metrics'>정답 수<br><strong>{correct_so_far}/{total_questions}</strong></div>", unsafe_allow_html=True)
            cols_prog[1].markdown(f"<div class='mini-metrics'>연속 정답<br><strong>{st.session_state.streak}회</strong></div>", unsafe_allow_html=True)
            cols_prog[2].markdown(f"<div class='mini-metrics'>남은 문제<br><strong>{remaining}문제</strong></div>", unsafe_allow_html=True)

    # 결과表示モードの場合
    showing_result = st.session_state.showing_result
    if showing_result:
        # 결과を表示
        if st.session_state.last_is_correct:
            st.success(st.session_state.last_result_msg)
        else:
            st.error(st.session_state.last_result_msg)

        # 問題文の音声（결과画面でのみ再生）
        if audio_key:
            st.markdown("---")
            st.caption(f"🔊 발음 확인(자동 재생)【{audio_key}】")
            simple_audio_player(audio_key, question_index=q_index, instance="result")

        # 「次へ」ボタン
        if st.button("다음으로", type="primary", use_container_width=True, key=f"next_btn_{st.session_state.q_index}_{'sp' if in_spartan else 'main'}"):
            if in_spartan:
                st.session_state.showing_result = False
                st.session_state.spartan_current_q_idx = None
            else:
                st.session_state.q_index += 1
                st.session_state.showing_result = False
            st.rerun()
        return

    # 回答待ちモード: 4択ボタンを出題直下に配置（출제 방향でラベル切り替え）
    clicked_index = None
    # 4択の各選択肢の音声は常に表示（方向に関わらず）
    show_audio = st.session_state.get("show_option_audio", True)
    if compact_question_ui and st.session_state.get("compact_hide_option_audio", True):
        show_audio = False

    for row_start in range(0, len(option_labels), 2):
        cols = st.columns([1, 1], gap="small" if compact_question_ui else "medium")
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
                # 복습リストから除外して次のランダムへ
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
            msg = f"오답. 정답: {option_labels[question['answer_index']]}"
            st.session_state.streak = 0
            # 初回フェーズでの誤答はスパルタ対象に追加
            if st.session_state.spartan_mode and not in_spartan:
                if current_q_idx not in st.session_state.spartan_pending:
                    st.session_state.spartan_pending.append(current_q_idx)

            # 결과表示モードへ移行
            st.session_state.showing_result = True
            st.session_state.last_result_msg = msg
            st.session_state.last_is_correct = False
            st.session_state.last_correct_answer = option_labels[question['answer_index']]
            st.rerun()


if __name__ == "__main__":
    main()
