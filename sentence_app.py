import datetime
import random
import time
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

from data_sources import PHRASE_CSV
from score_append_utils import append_score_row_fast
from score_row_utils import infer_mode, normalize_score_row, normalize_score_rows
import vocab_grouping as vg

# パス設定（単独アプリとして実行）
BASE_DIR = Path(__file__).resolve().parent
PHRASE_AUDIO_DIR = BASE_DIR / "Esperanto例文5000文_収録音声"

# スコア設定
STREAK_BONUS = 0.5
STREAK_BONUS_SCALE = 1.5
ACCURACY_BONUS_PER_Q = 5.0 * 1.5  # 文章は精度ボーナスも1.5倍
SPARTAN_SCORE_MULTIPLIER = 0.7
SCORES_SHEET = "Scores"
USER_STATS_SHEET = "UserStatsSentence"  # 文章専用の累積
USER_STATS_MAIN = "UserStats"  # 単語と共通累積（全体）
HOF_THRESHOLD = 1000000
MOBILE_UA_TOKENS = (
    "iphone",
    "ipad",
    "ipod",
    "android",
    "mobile",
)
DESKTOP_UA_TOKENS = (
    "windows nt",
    "macintosh",
    "x11",
    "cros",
)
SCORE_READ_RETRIES = 3
SCORE_READ_RETRY_BASE_SEC = 0.35
SCORE_WRITE_RETRIES = 3
SCORE_WRITE_RETRY_BASE_SEC = 0.4
DEBUG_QUERY_VALUES = {"1", "true", "yes", "on"}


@st.cache_data
def load_phrase_df(csv_path: str, mtime_ns: int):
    # mtime_ns をキャッシュキーに含め、CSV更新時に自動で再読込する。
    del mtime_ns
    return pd.read_csv(csv_path)


def is_mobile_client() -> bool:
    """ヘッダ(Client Hints含む) + URLパラメータでモバイル判定する。"""
    try:
        headers = st.context.headers
    except Exception:
        headers = {}
    normalized = {str(k).lower(): str(v).lower() for k, v in dict(headers).items()}
    ua = normalized.get("user-agent", "")
    ch_mobile = normalized.get("sec-ch-ua-mobile", "")
    ch_platform = normalized.get("sec-ch-ua-platform", "")
    qp_mobile = str(st.query_params.get("mobile", "")).strip().lower()

    if ch_mobile in {"?1", "1", "true"}:
        return True
    if any(token in ch_platform for token in ("android", "ios", "iphone", "ipad")):
        return True
    if any(token in ua for token in MOBILE_UA_TOKENS):
        return True

    qp_is_mobile = qp_mobile in {"1", "true", "yes", "on"}
    if not qp_is_mobile:
        return False

    # クエリ強制は「UA/Platformが取れない場合」か「明確なデスクトップでない場合」だけ許可。
    has_signal = bool(ua or ch_platform or ch_mobile)
    looks_desktop = (
        any(token in ch_platform for token in ("windows", "mac", "linux", "chrome os", "cros"))
        or any(token in ua for token in DESKTOP_UA_TOKENS)
    )
    if not has_signal:
        return True
    return not looks_desktop


def is_debug_mode() -> bool:
    raw = str(st.query_params.get("debug", "")).strip().lower()
    return raw in DEBUG_QUERY_VALUES


def get_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"Google Sheets 接続の初期化に失敗しました: {e}")
        return None


def base_points_for_level(level: int) -> float:
    return level + 11.5


def safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        parsed = float(value)
        if parsed != parsed or parsed in (float("inf"), float("-inf")):
            return default
        return parsed
    except (TypeError, ValueError):
        return default


def _phrase_audio_key(phrase_id: int, phrase: str) -> str:
    prefix = f"{int(phrase_id) - 155:04d}"
    suffix = vg._default_audio_key(phrase)
    return f"{prefix}_{suffix}"


@st.cache_data(show_spinner=False, max_entries=1024)
def find_phrase_audio(phrase_id: int, phrase: str):
    key = _phrase_audio_key(phrase_id, phrase)
    audio_formats = [(".wav", "audio/wav"), (".mp3", "audio/mpeg"), (".ogg", "audio/ogg")]
    for ext, mime in audio_formats:
        fp = PHRASE_AUDIO_DIR / f"{key}{ext}"
        if fp.exists():
            return fp.read_bytes(), mime, key
    legacy_key = key.replace("_", "")
    for ext, mime in audio_formats:
        fp = PHRASE_AUDIO_DIR / f"{legacy_key}{ext}"
        if fp.exists():
            return fp.read_bytes(), mime, legacy_key
    # 文章の語順や表記が更新されても、同一 PhraseID の既存音声を拾えるようにする
    prefix = f"{int(phrase_id) - 155:04d}_"
    for ext, mime in audio_formats:
        matches = sorted(PHRASE_AUDIO_DIR.glob(f"{prefix}*{ext}"))
        if matches:
            fp = matches[0]
            return fp.read_bytes(), mime, fp.stem
    return None, None, key


def play_phrase_audio(
    phrase_id: int,
    phrase: str,
    autoplay: bool = False,
    caption: str = "",
    instance: str = "default",
    show_caption: bool = True,
):
    data, mime, key = find_phrase_audio(phrase_id, phrase)
    if not data:
        return
    cap = caption or f"🔊 発音を聞く【{key}】"
    if show_caption:
        st.caption(cap)
    offset = (abs(hash(f"{instance}-{phrase_id}-{key}-{random.random()}")) % 1000000) / 1_000_000 + 1e-6
    st.audio(data, format=mime, start_time=offset, autoplay=autoplay)


def _get_col(df: pd.DataFrame, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of the columns found: {candidates}")


def build_groups(df: pd.DataFrame):
    col_eo = _get_col(df, ["Esperanto", "Phrase"])
    col_ja = _get_col(df, ["日本語", "Japanese"])
    col_level = _get_col(df, ["LevelID", "Level"])
    col_topic = _get_col(df, ["TopicName_EN", "Topic"])
    col_subtopic = _get_col(df, ["SubtopicName_EN", "Subtopic"])
    col_id = _get_col(df, ["PhraseID", "ID"])

    groups = {}
    for _, row in df.iterrows():
        topic = str(row[col_topic]).strip()
        subtopic = str(row[col_subtopic]).strip()
        key = (topic, subtopic)
        groups.setdefault(key, []).append(
            {
                "phrase_id": int(row[col_id]),
                "phrase": str(row[col_eo]).strip(),
                "japanese": str(row[col_ja]).strip(),
                "level": int(row[col_level]),
            }
        )
    return groups


def filter_by_levels(entries, levels):
    return [e for e in entries if e["level"] in levels]


def build_questions(entries, levels, rng: random.Random):
    eligible = filter_by_levels(entries, levels)
    if len(eligible) < 4:
        return []
    rng.shuffle(eligible)
    questions = []
    for correct in eligible:
        others = [e for e in eligible if e is not correct]
        if len(others) < 3:
            continue
        options = rng.sample(others, 3) + [correct]
        rng.shuffle(options)
        answer_idx = options.index(correct)
        questions.append(
            {
                "prompt_eo": correct["phrase"],
                "prompt_ja": correct["japanese"],
                "answer_index": answer_idx,
                "options": [
                    {
                        "phrase": opt["phrase"],
                        "japanese": opt["japanese"],
                        "level": opt["level"],
                        "phrase_id": opt["phrase_id"],
                    }
                    for opt in options
                ],
            }
        )
    return questions


def _read_sheet_with_retry(conn, worksheet: str, force_refresh: bool):
    ttl = 0 if force_refresh else 60
    last_error = None
    for attempt in range(SCORE_READ_RETRIES):
        try:
            return conn.read(worksheet=worksheet, ttl=ttl)
        except Exception as e:
            last_error = e
            if attempt + 1 < SCORE_READ_RETRIES:
                time.sleep(SCORE_READ_RETRY_BASE_SEC * (attempt + 1))
    if last_error is not None:
        raise last_error
    return pd.DataFrame()


def load_scores(force_refresh: bool = False):
    conn = get_connection()
    cached_scores = st.session_state.get("cached_scores", [])
    if conn is None:
        if cached_scores:
            st.session_state.score_load_error = None
            st.session_state.score_refresh_needed = False
            return normalize_score_rows(cached_scores, fallback_mode="vocab")
        st.session_state.score_load_error = "Google Sheets 接続を初期化できませんでした。"
        return []
    try:
        df = _read_sheet_with_retry(conn, worksheet=SCORES_SHEET, force_refresh=force_refresh)
        st.session_state.score_load_error = None
        st.session_state.score_refresh_needed = False
        if df is None or df.empty:
            return []
        records = normalize_score_rows(df.to_dict(orient="records"), fallback_mode="vocab")
        return [r for r in records if r.get("mode") == "sentence"] or []
    except Exception as e:
        if cached_scores:
            st.session_state.score_load_error = None
            st.session_state.score_refresh_needed = False
            normalized_cached = normalize_score_rows(cached_scores, fallback_mode="vocab")
            return [r for r in normalized_cached if r.get("mode") == "sentence"] or []
        st.session_state.score_load_error = f"ランキングの取得に失敗しました: {e}"
        return []


def load_scores_all(force_refresh: bool = False):
    """モードに関係なくScoresを取得（全体累積のフォールバック用）"""
    conn = get_connection()
    cached_scores_all = st.session_state.get("cached_scores_all", [])
    if conn is None:
        return normalize_score_rows(cached_scores_all, fallback_mode="vocab") if cached_scores_all else []
    try:
        df = _read_sheet_with_retry(conn, worksheet=SCORES_SHEET, force_refresh=force_refresh)
        if df is None or df.empty:
            return []
        return normalize_score_rows(df.to_dict(orient="records"), fallback_mode="vocab")
    except Exception:
        return normalize_score_rows(cached_scores_all, fallback_mode="vocab") if cached_scores_all else []


def _score_record_exists(df: pd.DataFrame, record: dict) -> bool:
    if df is None or df.empty:
        return False
    save_id = str(record.get("save_id", "")).strip()
    if save_id and "save_id" in df.columns:
        return df["save_id"].fillna("").astype(str).str.strip().eq(save_id).any()

    user = str(record.get("user", "")).strip()
    ts = str(record.get("ts", "")).strip()
    if not user or not ts:
        return False
    if "user" not in df.columns or "ts" not in df.columns:
        return False
    mask = df["user"].fillna("").astype(str).str.strip().eq(user)
    mask &= df["ts"].fillna("").astype(str).str.strip().eq(ts)
    if "points" in df.columns:
        mask &= pd.to_numeric(df["points"], errors="coerce").fillna(0.0).eq(
            safe_float(record.get("points", 0.0), 0.0)
        )
    return bool(mask.any())


def _append_score_record(df: pd.DataFrame, record: dict) -> pd.DataFrame:
    new_row = pd.DataFrame([record])
    if df is None or df.empty:
        return new_row
    return pd.concat([df, new_row], ignore_index=True, sort=False)


def _build_stats_from_scores(scores_df: pd.DataFrame, ts: str, sentence_only: bool) -> pd.DataFrame:
    columns = ["user", "total_points", "last_updated"]
    if scores_df is None or scores_df.empty or "user" not in scores_df.columns:
        return pd.DataFrame(columns=columns)

    normalized = scores_df.copy()
    normalized["user"] = normalized["user"].fillna("").astype(str).str.strip()
    normalized = normalized[normalized["user"] != ""]
    if normalized.empty:
        return pd.DataFrame(columns=columns)

    normalized["mode"] = normalized.apply(
        lambda row: infer_mode(row.to_dict(), fallback="vocab"),
        axis=1,
    )
    if sentence_only:
        normalized = normalized[normalized["mode"] == "sentence"]
    if normalized.empty:
        return pd.DataFrame(columns=columns)

    if "points" not in normalized.columns:
        normalized["points"] = 0.0
    normalized["points"] = pd.to_numeric(normalized["points"], errors="coerce").fillna(0.0)

    agg = normalized.groupby("user", as_index=False)["points"].sum()
    agg = agg.rename(columns={"points": "total_points"})
    agg["last_updated"] = ts
    return agg[columns]


def save_score(record: dict):
    record_to_save = normalize_score_row(record, fallback_mode="sentence")
    save_id = str(record_to_save.get("save_id", "")).strip()
    record_to_save["save_id"] = save_id or str(uuid.uuid4())
    fast_saved = append_score_row_fast(record_to_save, worksheet_name=SCORES_SHEET)
    if fast_saved is True:
        return True

    conn = get_connection()
    if conn is None:
        return False

    last_error = None

    for attempt in range(SCORE_WRITE_RETRIES):
        try:
            df = _read_sheet_with_retry(conn, worksheet=SCORES_SHEET, force_refresh=True)
            if df is None or df.empty:
                df = pd.DataFrame()
            if _score_record_exists(df, record_to_save):
                return True

            updated = _append_score_record(df, record_to_save)
            conn.update(worksheet=SCORES_SHEET, data=updated)

            verify_df = _read_sheet_with_retry(conn, worksheet=SCORES_SHEET, force_refresh=True)
            if _score_record_exists(verify_df, record_to_save):
                return True
            last_error = RuntimeError("保存後の検証で反映を確認できませんでした。")
        except Exception as e:
            last_error = e

        if attempt + 1 < SCORE_WRITE_RETRIES:
            time.sleep(SCORE_WRITE_RETRY_BASE_SEC * (attempt + 1))

    st.error(f"スコアの保存に失敗しました: {last_error}")
    return False


def _update_stats(sheet_name: str, user: str, points: float, ts: str):
    del points
    conn = get_connection()
    if conn is None:
        return False

    normalized_user = str(user).strip()
    sentence_only = sheet_name == USER_STATS_SHEET
    last_error = None

    for attempt in range(SCORE_WRITE_RETRIES):
        try:
            scores_df = _read_sheet_with_retry(conn, worksheet=SCORES_SHEET, force_refresh=True)
            stats_df = _build_stats_from_scores(scores_df, ts=ts, sentence_only=sentence_only)

            expected_total = None
            if normalized_user and not stats_df.empty:
                target_row = stats_df[stats_df["user"] == normalized_user]
                if not target_row.empty:
                    expected_total = safe_float(target_row.iloc[0]["total_points"], 0.0)
            if normalized_user and expected_total is None:
                raise RuntimeError("Scores 再集計で対象ユーザーの累積を特定できませんでした。")

            conn.update(worksheet=sheet_name, data=stats_df)

            if not normalized_user:
                return True
            verify_df = _read_sheet_with_retry(conn, worksheet=sheet_name, force_refresh=True)
            if verify_df is not None and not verify_df.empty and "user" in verify_df.columns:
                mask = verify_df["user"].fillna("").astype(str).str.strip().eq(normalized_user)
                if mask.any():
                    actual_total = safe_float(verify_df.loc[mask].iloc[0].get("total_points"), 0.0)
                    if abs(actual_total - expected_total) <= 0.001 or actual_total > expected_total:
                        return True
            last_error = RuntimeError(f"{sheet_name} の検証で期待値を確認できませんでした。")
        except Exception as e:
            last_error = e

        if attempt + 1 < SCORE_WRITE_RETRIES:
            time.sleep(SCORE_WRITE_RETRY_BASE_SEC * (attempt + 1))

    st.error(f"累積スコアの保存に失敗しました ({sheet_name}): {last_error}")
    return False


def update_user_stats(user: str, points: float, ts: str):
    return _update_stats(USER_STATS_SHEET, user, points, ts)


def update_user_stats_main(user: str, points: float, ts: str):
    return _update_stats(USER_STATS_MAIN, user, points, ts)


def load_rankings(force_refresh: bool = False):
    conn = get_connection()
    if conn is None:
        return []
    try:
        df = _read_sheet_with_retry(conn, worksheet=USER_STATS_SHEET, force_refresh=force_refresh)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception:
        return []


def load_main_rankings(force_refresh: bool = False):
    conn = get_connection()
    if conn is None:
        return []
    try:
        df = _read_sheet_with_retry(conn, worksheet=USER_STATS_MAIN, force_refresh=force_refresh)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception:
        return []


def summarize_scores(scores):
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now_jst = datetime.datetime.now(jst)
    today_jst = now_jst.date()
    month_start_jst = today_jst.replace(day=1)

    totals = {}
    totals_today = {}
    totals_month = {}
    hof = {}
    for r in scores:
        user = str(r.get("user", "")).strip()
        if not user:
            continue
        pts = safe_float(r.get("points", 0), 0.0)
        ts = str(r.get("ts", "")).strip()
        date_obj = None
        if ts:
            parsed_ts = pd.to_datetime(ts, errors="coerce", utc=True)
            if pd.notna(parsed_ts):
                date_obj = parsed_ts.tz_convert(jst).date()

        totals[user] = totals.get(user, 0) + pts
        if date_obj:
            if date_obj == today_jst:
                totals_today[user] = totals_today.get(user, 0) + pts
            if date_obj >= month_start_jst:
                totals_month[user] = totals_month.get(user, 0) + pts

        if totals[user] >= HOF_THRESHOLD:
            hof[user] = totals[user]
    return totals, totals_today, totals_month, hof


def summarize_rankings_from_stats(stats_data, score_rows=None):
    totals = {}
    if stats_data and isinstance(stats_data, list):
        first_row = stats_data[0] if stats_data else {}
        is_raw_log = "total_points" not in first_row and "points" in first_row
    else:
        is_raw_log = False

    if is_raw_log:
        for r in stats_data or []:
            user = str(r.get("user", "")).strip()
            if not user:
                continue
            totals[user] = totals.get(user, 0.0) + safe_float(r.get("points", 0), 0.0)
    else:
        for r in stats_data or []:
            user = str(r.get("user", "")).strip()
            if not user:
                continue
            val = r.get("total_points")
            if val is None:
                for k in r.keys():
                    if "total_points" in k:
                        val = r[k]
                        break
            totals[user] = safe_float(val, 0.0)

    scores = score_rows if score_rows is not None else load_scores()
    score_totals, totals_today, totals_month, _ = summarize_scores(scores)
    if totals:
        for user, log_total in score_totals.items():
            totals[user] = max(safe_float(totals.get(user, 0.0), 0.0), safe_float(log_total, 0.0))
    else:
        totals = score_totals
    hof = {u: p for u, p in totals.items() if p >= HOF_THRESHOLD}
    return totals, totals_today, totals_month, hof


def rank_dict(d, top_n=None):
    items = sorted(d.items(), key=lambda x: x[1], reverse=True)
    return items[:top_n] if top_n else items


def show_rankings(stats_data, key_suffix: str = "", score_rows=None):
    if is_debug_mode():
        with st.expander("Debug: Raw UserStats Data"):
            st.write("Raw Data:", stats_data)
            if st.button("Clear Cache & Rerun", key=f"clear_cache_sentence{key_suffix}"):
                st.cache_data.clear()
                st.rerun()

    totals, totals_today, totals_month, hof = summarize_rankings_from_stats(stats_data, score_rows=score_rows)
    tabs = st.tabs(["累積", "本日", "今月", f"殿堂（{HOF_THRESHOLD}点以上）"])

    def to_df(d):
        if not d:
            return pd.DataFrame(columns=["順位", "ユーザー", "得点"])
        items = sorted(d.items(), key=lambda x: x[1], reverse=True)
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


def render_cross_language_footer(current_key: str):
    links = [
        ("vocab_zh", "語彙版（中文）", "https://esperantowords4choicequizzes-cxina-versio.streamlit.app"),
        ("sentence_zh", "文章版（中文）", "https://esperantowords4choicequizzes-fwvq3dnm2jq85gbaztjlyy.streamlit.app"),
        ("vocab_ko", "어휘 버전(한국어)", "https://esperantowords4choicequizzes-korea-versio.streamlit.app"),
        ("sentence_ko", "문장 버전(한국어)", "https://esperantowords4choicequizzes-korea-version-frazoj.streamlit.app"),
        ("vocab_ja", "語彙版（日本語）", "https://esperantowords4choicequizzes-bzgev2astlasx4app3futb.streamlit.app"),
        ("sentence_ja", "文章版（日本語）", "https://esperantowords4choicequizzes-tiexjo7fx5elylbsywxgxz.streamlit.app"),
    ]
    foreign_links = [item for item in links if item[0] != current_key]
    link_html = " ・ ".join(
        f"<a href='{url}' target='_blank' rel='noopener noreferrer'>{label}</a>" for _, label, url in foreign_links
    )
    st.markdown(
        f"""
        <div style="margin-top: 1.4rem; padding-top: 0.55rem; border-top: 1px solid #e5e7eb; font-size: 0.80rem; color: #6b7280;">
            他言語版: {link_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(
        page_title="エスペラント例文クイズ",
        page_icon="📘",
        layout="centered",
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

    requested_compact_ui = bool(st.session_state.mobile_compact_ui)
    compact_ui = is_mobile and requested_compact_ui
    ultra_compact_ui = compact_ui and bool(st.session_state.mobile_ultra_compact)
    direction = st.session_state.get("direction", "ja_to_eo")
    base_font = "18px" if direction == "eo_to_ja" else "24px"
    mobile_font = (
        "34px"
        if (ultra_compact_ui and direction == "eo_to_ja")
        else (
            "38px"
            if ultra_compact_ui
            else (
                "32px"
                if (compact_ui and direction == "eo_to_ja")
                else ("36px" if compact_ui else ("24px" if direction == "eo_to_ja" else "30px"))
            )
        )
    )
    mobile_button_height = "148px" if ultra_compact_ui else ("168px" if compact_ui else "188px")
    mobile_button_padding = "8px" if ultra_compact_ui else ("10px" if compact_ui else "12px")
    mobile_main_title_font = "18px" if ultra_compact_ui else ("20px" if compact_ui else "24px")
    mobile_question_font = (
        "38px" if ultra_compact_ui else ("44px" if compact_ui else ("50px" if direction == "ja_to_eo" else "54px"))
    )
    mobile_option_font = (
        "51px"
        if (ultra_compact_ui and direction == "eo_to_ja")
        else (
            "57px"
            if ultra_compact_ui
            else (
                "48px"
                if (compact_ui and direction == "eo_to_ja")
                else ("54px" if compact_ui else ("36px" if direction == "eo_to_ja" else "45px"))
            )
        )
    )
    mobile_page_top_padding = "0.15rem" if ultra_compact_ui else ("0.35rem" if compact_ui else "0.9rem")
    mobile_page_bottom_padding = "0.2rem" if ultra_compact_ui else ("0.4rem" if compact_ui else "0.7rem")
    show_main_title = not (compact_ui and bool(st.session_state.get("questions")))
    main_title_html = "<div class='main-title'>エスペラント例文４択クイズ</div>" if show_main_title else ""
    mobile_chrome_css = (
        """
            div[data-testid="stToolbar"] {display: none !important;}
            #MainMenu {visibility: hidden !important;}
            footer {display: none !important;}
        """
        if st.session_state.mobile_hide_streamlit_chrome
        else ""
    )
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
        /* 通常ボタンのボーダーなども緑系に */
        div.stButton > button[kind="secondary"] {{
            border-color: #009900 !important;
        }}
        [data-testid="stMain"] .stButton button {{
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
        /* ボタン内部のdiv/spanにも同じフォントサイズを強制 */
        [data-testid="stMain"] .stButton button * {{
            font-size: {base_font} !important;
            font-weight: 700 !important;
            line-height: 1.35 !important;
        }}
        @media (max-width: 768px) {{
            [data-testid="stMain"] .stButton button {{
                height: auto;
                min-height: {mobile_button_height};
                max-height: none;
                overflow: visible;
                text-overflow: clip;
                white-space: normal;
                overflow-wrap: anywhere;
                word-break: break-word;
                font-size: {mobile_option_font} !important;
                font-weight: 700 !important;
                padding: {mobile_button_padding};
            }}
            [data-testid="stMain"] .stButton button * {{
                font-size: {mobile_option_font} !important;
                font-weight: 700 !important;
                line-height: 1.35 !important;
            }}
            [data-testid="stMain"] .stButton {{
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
            font-size: {"20px" if direction == "ja_to_eo" else "22px"} !important;
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
            [data-testid="stMain"] .stButton button p, [data-testid="stMain"] .stButton button span, [data-testid="stMain"] .stButton button div {{
                line-height: 1.25 !important;
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
            [data-testid="stMain"] .stButton button {{
                height: auto !important;
                min-height: 124px !important;
                max-height: none !important;
                overflow: visible !important;
                text-overflow: clip !important;
                white-space: normal !important;
                overflow-wrap: anywhere !important;
                word-break: break-word !important;
                padding: 8px !important;
                font-size: 45px !important;
            }}
            [data-testid="stMain"] .stButton button p, [data-testid="stMain"] .stButton button div, [data-testid="stMain"] .stButton button span, [data-testid="stMain"] .stButton button * {{
                font-size: 45px !important;
                line-height: 1.3 !important;
            }}
        }}
        </style>
        {main_title_html}
        """,
        unsafe_allow_html=True,
    )

    # モバイル用: 音声自動再生のアンロックスクリプト
    st.markdown(
        """
        <script>
        (function() {
            try {
                const isNarrow = window.innerWidth <= 768;
                const params = new URLSearchParams(window.location.search);
                const hasMobileParam = params.get("mobile") === "1";
                if (isNarrow && !hasMobileParam) {
                    params.set("mobile", "1");
                    const target = window.location.pathname + "?" + params.toString() + window.location.hash;
                    window.location.replace(target);
                    return;
                }
                if (!isNarrow && hasMobileParam) {
                    params.delete("mobile");
                    const query = params.toString();
                    const target = window.location.pathname + (query ? "?" + query : "") + window.location.hash;
                    window.location.replace(target);
                    return;
                }
            } catch (_) {}
        })();

        (function() {
            if (window._esperantoAudioUnlocked) return;
            const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
            if (!isMobile) {
                window._esperantoAudioUnlocked = true;
                return;
            }
            if (sessionStorage.getItem('esperanto_audio_unlocked') === 'true') {
                window._esperantoAudioUnlocked = true;
                return;
            }
            function unlockAudio() {
                const silentAudio = new Audio('data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=');
                silentAudio.volume = 0.01;
                silentAudio.play().then(() => {
                    window._esperantoAudioUnlocked = true;
                    sessionStorage.setItem('esperanto_audio_unlocked', 'true');
                }).catch(() => {});
            }
            document.addEventListener('touchstart', unlockAudio, { once: true });
            document.addEventListener('click', unlockAudio, { once: true });
        })();

        (function() {
            if (window.__esperantoOptionAutoFitInstalled) {
                if (typeof window.__esperantoOptionAutoFitSchedule === "function") {
                    window.__esperantoOptionAutoFitSchedule();
                }
                return;
            }
            window.__esperantoOptionAutoFitInstalled = true;

            const MOBILE_BP = 768;
            const MIN_FONT_PX = 16;
            const MIN_RATIO = 0.62;
            const HEIGHT_TOLERANCE = 6;
            const MAX_STEPS = 22;

            function applySize(btn, nodes, px) {
                const size = `${px}px`;
                btn.style.fontSize = size;
                nodes.forEach((n) => {
                    n.style.fontSize = size;
                });
            }

            function fitOne(btn) {
                if (window.innerWidth > MOBILE_BP) return;
                const base = parseFloat(btn.dataset.baseFontPx || getComputedStyle(btn).fontSize || "0");
                if (!base || Number.isNaN(base)) return;
                if (!btn.dataset.baseFontPx) {
                    btn.dataset.baseFontPx = String(base);
                }

                const minHeight = parseFloat(getComputedStyle(btn).minHeight || "0");
                const targetHeight = (Number.isFinite(minHeight) && minHeight > 0) ? (minHeight + HEIGHT_TOLERANCE) : 180;
                const minFont = Math.max(MIN_FONT_PX, base * MIN_RATIO);
                const nodes = btn.querySelectorAll("p, div, span");

                applySize(btn, nodes, base);
                if (btn.offsetHeight <= targetHeight) return;

                let size = base;
                let step = 0;
                while (btn.offsetHeight > targetHeight && size > minFont && step < MAX_STEPS) {
                    size -= 1;
                    applySize(btn, nodes, size);
                    step += 1;
                }
            }

            function fitOptionButtons() {
                if (window.innerWidth > MOBILE_BP) return;
                const buttons = document.querySelectorAll('[data-testid="stMain"] div.stButton > button[kind="primary"]');
                buttons.forEach(fitOne);
            }

            let rafId = null;
            function scheduleFit() {
                if (rafId !== null) return;
                rafId = window.requestAnimationFrame(() => {
                    rafId = null;
                    fitOptionButtons();
                });
            }

            window.__esperantoOptionAutoFitSchedule = scheduleFit;

            const observer = new MutationObserver(scheduleFit);
            observer.observe(document.body, { childList: true, subtree: true });
            window.addEventListener("resize", scheduleFit, { passive: true });
            scheduleFit();
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    show_intro_block = not (compact_ui and bool(st.session_state.get("questions")))
    if show_intro_block:
        st.write("トピック別の例文から4択で出題します。単語版よりも得点係数を約1.5倍に調整しています。")
        with st.expander("スコア計算ルール"):
            st.markdown(
                "\n".join(
                    [
                        f"- 基礎点: レベル + 11.5（例: Lv5→16.5点）",
                        f"- 連続正解ボーナス: 2問目以降の連続正解1回につき +{STREAK_BONUS * STREAK_BONUS_SCALE}",
                        f"- 精度ボーナス: 最終正答率 × 問題数 × {ACCURACY_BONUS_PER_Q}",
                        "- スパルタモード: 復習分は0.7倍で加算（精度ボーナスなし）",
                        "- 同じ問題数なら単語版よりおおむね1.5倍スコアが伸びる想定です。",
                    ]
                )
            )

    # 状態初期化
    st.session_state.setdefault("questions", [])
    st.session_state.setdefault("q_index", 0)
    st.session_state.setdefault("correct", 0)
    st.session_state.setdefault("points_raw", 0.0)
    st.session_state.setdefault("points_main", 0.0)
    st.session_state.setdefault("points_spartan_raw", 0.0)
    st.session_state.setdefault("points_spartan_scaled", 0.0)
    st.session_state.setdefault("streak", 0)
    st.session_state.setdefault("answers", [])
    st.session_state.setdefault("showing_result", False)
    st.session_state.setdefault("direction", "ja_to_eo")
    st.session_state.setdefault("score_saved", False)
    st.session_state.setdefault("pending_save_id", None)
    st.session_state.setdefault("score_refresh_needed", False)
    st.session_state.setdefault("score_load_error", None)
    st.session_state.setdefault("score_sync_warning", None)
    st.session_state.setdefault("cached_scores", [])
    st.session_state.setdefault("cached_scores_all", [])
    st.session_state.setdefault("cached_main_rank", [])
    st.session_state.setdefault("spartan_mode", False)
    st.session_state.setdefault("spartan_pending", [])
    st.session_state.setdefault("in_spartan_round", False)
    st.session_state.setdefault("spartan_current_q_idx", None)
    st.session_state.setdefault("spartan_attempts", 0)
    st.session_state.setdefault("spartan_correct_count", 0)
    st.session_state.setdefault("show_option_audio", True)
    st.session_state.setdefault("quiz_topic", None)
    st.session_state.setdefault("quiz_subtopic", None)
    st.session_state.setdefault("quiz_levels", [])
    st.session_state.setdefault("mobile_compact_ui", is_mobile)
    st.session_state.setdefault("compact_hide_option_audio", True)
    st.session_state.setdefault("compact_hide_prompt_audio", True)

    df = load_phrase_df(str(PHRASE_CSV), PHRASE_CSV.stat().st_mtime_ns)
    groups = build_groups(df)

    with st.sidebar:
        st.header("設定")
        st.text_input("ユーザー名（表示用）", key="sentence_user_name")
        topic_options = sorted(set(k[0] for k in groups.keys()))
        topic = st.selectbox("Topic", topic_options)
        subtopics = sorted([k[1] for k in groups.keys() if k[0] == topic])
        subtopic = st.selectbox("Subtopic", subtopics)

        levels = list(range(1, 11))
        default_levels = [1, 2, 3, 4, 5]
        selected_levels = st.multiselect(
            "出題レベル (1-10, 複数選択可)",
            levels,
            default=default_levels,
        )
        direction = st.radio(
            "出題方向",
            options=[("ja_to_eo", "日本語 → エスペラント"), ("eo_to_ja", "エスペラント → 日本語")],
            format_func=lambda x: x[1],
            index=0 if st.session_state.direction == "ja_to_eo" else 1,
        )[0]
        st.session_state.direction = direction
        st.checkbox(
            "スパルタモード（全問後に間違えた問題だけ正解するまでランダム出題・得点0.7倍）",
            key="spartan_mode",
            disabled=bool(st.session_state.questions),
        )
        st.checkbox(
            "選択肢の音声を表示",
            value=st.session_state.show_option_audio,
            key="show_option_audio",
            help="オフにすると選択肢ごとの音声プレイヤーを非表示にして軽量化します。",
        )
        st.checkbox(
            "スマホ最適化UI（設問+4択を1画面優先）",
            key="mobile_compact_ui",
            help="モバイルではON推奨。デスクトップ表示には影響しません。",
        )
        if compact_ui:
            st.checkbox(
                "スマホ最適化時は選択肢の音声を自動で隠す",
                key="compact_hide_option_audio",
                help="問題文の音声は維持しつつ、選択肢ごとの音声表示だけ抑制して縦スクロールを減らします。",
            )
            st.checkbox(
                "スマホ最適化時は問題文音声プレイヤーを隠す",
                key="compact_hide_prompt_audio",
                help="設問+4択を1画面に収めやすくします。必要時のみOFFにして表示してください。",
            )
            st.checkbox(
                "超圧縮モード（小画面向け）",
                key="mobile_ultra_compact",
                help="設問エリア・ボタンをさらに圧縮します。",
            )
            st.checkbox(
                "スマホ時に上部メニュー類を隠す",
                key="mobile_hide_streamlit_chrome",
                help="縦領域を増やします。通常操作に戻したい場合はOFFにしてください。",
            )
        st.caption("出題方向にかかわらず、音声はトグルONで選択肢に表示されます。モバイルで重い場合はOFF推奨。")
        st.caption(
            f"端末判定: {'モバイル' if is_mobile else 'デスクトップ'} / "
            f"最適化UI: {'ON' if compact_ui else 'OFF'}"
        )

        if st.button("クイズ開始", use_container_width=True):
            rng = random.Random()
            entries = groups.get((topic, subtopic), [])
            qs = build_questions(entries, selected_levels, rng)
            if len(qs) < 4:
                st.warning("4問以上になるようにレベルを増やしてください。")
            else:
                st.session_state.questions = qs
                st.session_state.q_index = 0
                st.session_state.correct = 0
                st.session_state.points_raw = 0.0
                st.session_state.points_main = 0.0
                st.session_state.points_spartan_raw = 0.0
                st.session_state.points_spartan_scaled = 0.0
                st.session_state.streak = 0
                st.session_state.answers = []
                st.session_state.showing_result = False
                st.session_state.last_is_correct = False
                st.session_state.last_result_msg = ""
                st.session_state.score_saved = False
                st.session_state.pending_save_id = None
                st.session_state.score_refresh_needed = False
                st.session_state.score_sync_warning = None
                st.session_state.spartan_pending = []
                st.session_state.in_spartan_round = False
                st.session_state.spartan_current_q_idx = None
                st.session_state.spartan_attempts = 0
                st.session_state.spartan_correct_count = 0
                st.session_state.quiz_topic = topic
                st.session_state.quiz_subtopic = subtopic
                st.session_state.quiz_levels = list(selected_levels)
                st.rerun()

        st.markdown("---")
        if st.button("🏠 ホームに戻る", use_container_width=True, type="primary"):
            st.session_state.questions = []
            st.session_state.q_index = 0
            st.session_state.correct = 0
            st.session_state.points_raw = 0.0
            st.session_state.points_main = 0.0
            st.session_state.points_spartan_raw = 0.0
            st.session_state.points_spartan_scaled = 0.0
            st.session_state.streak = 0
            st.session_state.answers = []
            st.session_state.showing_result = False
            st.session_state.score_saved = False
            st.session_state.pending_save_id = None
            st.session_state.score_refresh_needed = False
            st.session_state.score_sync_warning = None
            st.session_state.spartan_pending = []
            st.session_state.in_spartan_round = False
            st.session_state.spartan_current_q_idx = None
            st.session_state.spartan_attempts = 0
            st.session_state.spartan_correct_count = 0
            st.session_state.quiz_topic = None
            st.session_state.quiz_subtopic = None
            st.session_state.quiz_levels = []
            st.session_state.cached_scores = load_scores()
            st.rerun()

        st.markdown("---")
        st.markdown(
            "[💚 単語クイズはこちら](https://esperantowords4choicequizzes-bzgev2astlasx4app3futb.streamlit.app/)"
        )

    # スコア読み込み
    should_load = (
        not st.session_state.questions
        or st.session_state.showing_result
        or st.session_state.score_saved
        or not st.session_state.cached_scores
    )
    finished_quiz = (
        bool(st.session_state.questions)
        and st.session_state.q_index >= len(st.session_state.questions)
        and not st.session_state.in_spartan_round
    )
    force_refresh_rankings = st.session_state.get("score_refresh_needed", False)
    if (
        not st.session_state.questions
        or finished_quiz
        or st.session_state.score_saved
        or not st.session_state.cached_scores
    ):
        scores = load_scores(force_refresh=force_refresh_rankings)
        st.session_state.cached_scores = scores
    else:
        scores = st.session_state.cached_scores
    if st.session_state.get("score_load_error"):
        col_warn, col_btn = st.columns([4, 1])
        col_warn.warning(st.session_state.score_load_error)
        col_warn.caption("認証・通信エラー時のみ再試行してください。")
        if col_btn.button("再読み込み", key="retry_scores_sentence"):
            st.cache_data.clear()
            st.session_state.cached_scores = load_scores(force_refresh=True)
            st.session_state.score_load_error = None
            st.rerun()

    # サイドバーでユーザー名が入力されていれば累積を案内（scores読み込み後）
    if st.session_state.sentence_user_name and scores:
        with st.sidebar:
            st.markdown("---")
            user_total_sentence = sum(
                safe_float(r.get("points", 0), 0.0)
                for r in scores
                if r.get("user") == st.session_state.sentence_user_name
            )
            st.info(f"現在の累積（文章）: {user_total_sentence:.1f}")
            # 全体累積（UserStats優先、なければ全モードのログから集計）
            overall_points = None
            # クイズ中はネットアクセスを避け、キャッシュまたは空にする
            in_quiz = bool(st.session_state.questions) and not st.session_state.showing_result
            if not in_quiz:
                main_rank = load_main_rankings(force_refresh=force_refresh_rankings)
                st.session_state.cached_main_rank = main_rank
            else:
                main_rank = st.session_state.get("cached_main_rank", [])
            if main_rank:
                for row in main_rank:
                    if row.get("user") == st.session_state.sentence_user_name:
                        try:
                            overall_points = float(row.get("total_points", 0))
                        except (ValueError, TypeError):
                            overall_points = 0.0
                        break
            if not in_quiz:
                all_scores = load_scores_all(force_refresh=force_refresh_rankings)
                st.session_state.cached_scores_all = all_scores
            else:
                all_scores = st.session_state.get("cached_scores_all", [])
            log_total_all = sum(
                safe_float(r.get("points", 0), 0.0)
                for r in all_scores
                if r.get("user") == st.session_state.sentence_user_name
            )
            log_total_sentence = sum(
                safe_float(r.get("points", 0), 0.0)
                for r in scores
                if r.get("user") == st.session_state.sentence_user_name
            )
            log_total_vocab = log_total_all - log_total_sentence
            if overall_points is None:
                overall_points = log_total_all
            else:
                overall_points = max(overall_points, log_total_all)
            st.info(f"現在の累積（全体）: {overall_points:.1f}")
            if abs((log_total_sentence + log_total_vocab) - overall_points) > 0.5:
                st.warning("累積（単語＋文章）と全体の合計に差分があります。少し時間をおいて再読み込みしてください。")

    questions = st.session_state.questions
    if questions:
        q0 = questions[0]
        if "prompt_eo" not in q0 or "prompt_ja" not in q0:
            st.session_state.questions = []
            st.session_state.q_index = 0
            st.session_state.correct = 0
            st.session_state.points_raw = 0.0
            st.session_state.points_main = 0.0
            st.session_state.points_spartan_raw = 0.0
            st.session_state.points_spartan_scaled = 0.0
            st.session_state.streak = 0
            st.session_state.answers = []
            st.session_state.showing_result = False
            st.session_state.spartan_pending = []
            st.session_state.in_spartan_round = False
            st.session_state.spartan_current_q_idx = None
            st.session_state.spartan_attempts = 0
            st.session_state.spartan_correct_count = 0
            st.warning("問題データを再生成します。サイドバーで再度『クイズ開始』を押してください。")
            return

    if not questions:
        st.info("サイドバーでトピック/サブトピックとレベルを選んで開始してください。")
        st.caption("単語版に近い操作感で、例文の4択クイズを遊べます。")
        sentence_rank = load_rankings(force_refresh=force_refresh_rankings)
        if sentence_rank:
            st.subheader("ランキング")
            show_rankings(sentence_rank, key_suffix="_sentence", score_rows=scores)
        main_rank = load_main_rankings(force_refresh=force_refresh_rankings)
        if main_rank:
            all_scores = load_scores_all(force_refresh=force_refresh_rankings)
            st.session_state.cached_scores_all = all_scores
            st.subheader("ランキング（全体）")
            show_rankings(main_rank, key_suffix="_main", score_rows=all_scores)
        render_cross_language_footer("sentence_ja")
        return

    direction = st.session_state.direction
    q_idx = st.session_state.q_index

    # スパルタ判定
    if (
        q_idx >= len(questions)
        and st.session_state.spartan_mode
        and st.session_state.spartan_pending
    ):
        st.session_state.in_spartan_round = True
    if st.session_state.in_spartan_round and not st.session_state.spartan_pending:
        st.session_state.in_spartan_round = False

    if q_idx >= len(questions) and not st.session_state.in_spartan_round:
        total = len(questions)
        accuracy = st.session_state.correct / total if total else 0
        acc_bonus = accuracy * total * ACCURACY_BONUS_PER_Q
        raw_main = st.session_state.points_main
        raw_spartan_raw = st.session_state.points_spartan_raw
        raw_spartan_scaled = st.session_state.points_spartan_scaled
        sp_attempts = st.session_state.spartan_attempts
        sp_correct = st.session_state.spartan_correct_count
        sp_accuracy = sp_correct / sp_attempts if sp_attempts else 0
        base_points = raw_main + raw_spartan_scaled
        points = base_points + acc_bonus
        st.subheader("結果")
        st.metric("正答率", f"{accuracy*100:.1f}%")
        st.metric("得点", f"{points:.1f}")
        if st.session_state.sentence_user_name:
            # 全体累積はUserStats優先、ログ合計を優先度2で使用
            overall_points = None
            main_rank = load_main_rankings(force_refresh=force_refresh_rankings)
            if main_rank:
                for row in main_rank:
                    if row.get("user") == st.session_state.sentence_user_name:
                        try:
                            overall_points = float(row.get("total_points", 0))
                        except (ValueError, TypeError):
                            overall_points = 0.0
                        break
            all_scores_for_total = st.session_state.get("cached_scores_all", [])
            if not all_scores_for_total:
                all_scores_for_total = load_scores_all(force_refresh=force_refresh_rankings)
                st.session_state.cached_scores_all = all_scores_for_total
            log_total_all = sum(
                safe_float(r.get("points", 0), 0.0)
                for r in all_scores_for_total
                if r.get("user") == st.session_state.sentence_user_name
            )
            if overall_points is None:
                overall_points = log_total_all
            else:
                overall_points = max(overall_points, log_total_all)
            st.metric("累積（今回加算後）", f"{overall_points + points:.1f}")
        st.caption("音声で再確認できます。")
        st.write(f"正解 {st.session_state.correct}/{total}")
        st.write(
            f"内訳: 本編 基礎+ストリーク {raw_main:.1f} / スパルタ {raw_spartan_scaled:.1f}（精度ボーナスなし・0.7倍込） / 精度ボーナス {acc_bonus:.1f}"
        )
        if st.session_state.spartan_mode and sp_attempts:
            st.caption(f"スパルタモード: 復習分を通常の{SPARTAN_SCORE_MULTIPLIER*100:.0f}%で加算（精度ボーナスなし）")
            st.caption(f"スパルタ精度: {sp_accuracy*100:.1f}% ({sp_correct}/{sp_attempts})")
        if st.session_state.sentence_user_name:
            st.caption("同じユーザー名のスコアがある場合は累積に加算します。")
            if st.session_state.score_saved:
                st.success("スコアを保存しました！")
                if st.session_state.get("score_sync_warning"):
                    st.warning(st.session_state.score_sync_warning)
            else:
                st.caption("保存するとランキングに反映されます。失敗したらもう一度お試しください。")
                if st.button("スコアを保存", use_container_width=True):
                    now = datetime.datetime.utcnow().isoformat()
                    save_id = st.session_state.get("pending_save_id")
                    if not save_id:
                        save_id = str(uuid.uuid4())
                        st.session_state.pending_save_id = save_id
                    saved_topic = st.session_state.get("quiz_topic") or topic
                    saved_subtopic = st.session_state.get("quiz_subtopic") or subtopic
                    saved_levels = st.session_state.get("quiz_levels") or selected_levels
                    record = {
                        "user": st.session_state.sentence_user_name,
                        "mode": "sentence",
                        "topic": saved_topic,
                        "subtopic": saved_subtopic,
                        "levels": ",".join(map(str, saved_levels)),
                        "correct": st.session_state.correct,
                        "total": total,
                        "accuracy": accuracy,
                        "points": points,
                        "raw_points": base_points,
                        "points_main": raw_main,
                        "points_spartan_raw": raw_spartan_raw,
                        "points_spartan_scaled": raw_spartan_scaled,
                        "spartan_attempts": sp_attempts,
                        "spartan_correct": sp_correct,
                        "spartan_accuracy": sp_accuracy,
                        "spartan_mode": st.session_state.spartan_mode,
                        "direction": direction,
                        "accuracy_bonus_spartan": 0.0,
                        "accuracy_bonus": acc_bonus,
                        "ts": now,
                        "save_id": save_id,
                    }
                    log_saved = save_score(record)
                    if not log_saved:
                        st.error("保存に失敗しました。secrets を確認してください。")
                    else:
                        ok_sentence = update_user_stats(st.session_state.sentence_user_name, points, now)
                        ok_main = update_user_stats_main(st.session_state.sentence_user_name, points, now)
                        st.session_state.score_saved = True
                        st.session_state.pending_save_id = None
                        st.session_state.score_refresh_needed = True
                        st.session_state.cached_scores_all = []
                        st.session_state.cached_main_rank = []
                        st.session_state.score_sync_warning = None if (ok_sentence and ok_main) else "スコアログは保存しましたが、累積スコアの反映に一時失敗しました。少し時間をおいて再試行してください。"
                        st.rerun()
        recent = scores  # 既に読み込んだデータを再利用
        if recent:
            with st.expander("最近のスコア（文章）", expanded=False):
                # 列順を軽く整える（存在する列のみ）
                preferred_cols = [
                    "ts",
                    "user",
                    "points",
                    "accuracy",
                    "correct",
                    "total",
                    "topic",
                    "subtopic",
                    "levels",
                    "direction",
                    "spartan_mode",
                    "points_main",
                    "points_spartan_raw",
                    "points_spartan_scaled",
                    "spartan_attempts",
                    "spartan_correct",
                    "spartan_accuracy",
                    "accuracy_bonus",
                    "mode",
                ]
                df_recent = pd.DataFrame(recent)
                cols = [c for c in preferred_cols if c in df_recent.columns] if not df_recent.empty else []
                if cols:
                    df_recent = df_recent[cols + [c for c in df_recent.columns if c not in cols]]
                st.dataframe(df_recent, hide_index=True, use_container_width=True)
        ranking = load_rankings(force_refresh=force_refresh_rankings)
        if ranking:
            st.subheader("ランキング")
            show_rankings(ranking, key_suffix="_sentence", score_rows=scores)
        main_rank = load_main_rankings(force_refresh=force_refresh_rankings)
        if main_rank:
            all_scores = load_scores_all(force_refresh=force_refresh_rankings)
            st.session_state.cached_scores_all = all_scores
            st.subheader("ランキング（全体）")
            show_rankings(main_rank, key_suffix="_main", score_rows=all_scores)
        st.subheader("復習")
        wrong = []
        correct_list = []
        for ans in st.session_state.answers:
            idx = ans.get("q_idx", -1)
            if idx < 0 or idx >= len(st.session_state.questions):
                continue
            q = st.session_state.questions[idx]
            selected = ans["selected"]
            correct_idx = ans["correct"]
            opt_sel = q["options"][selected] if selected is not None else None
            opt_cor = q["options"][correct_idx]
            entry = {
                "prompt_eo": q["prompt_eo"],
                "prompt_ja": q["prompt_ja"],
                "selected": opt_sel["phrase"] if opt_sel else "",
                "selected_ja": opt_sel["japanese"] if opt_sel else "",
                "answer": opt_cor["phrase"],
                "answer_ja": opt_cor["japanese"],
                "phrase_id": opt_cor["phrase_id"],
            }
            if selected == correct_idx:
                correct_list.append(entry)
            else:
                wrong.append(entry)

        if wrong:
            st.markdown("### 間違えた問題")
            st.caption("音声で再確認できます。")
            for w in wrong:
                st.write(f"- {w['prompt_ja']} / {w['prompt_eo']}")
                st.write(f"　正解「{w['answer_ja']} / {w['answer']}」、あなたの回答「{w['selected_ja']} / {w['selected']}」")
                play_phrase_audio(w["phrase_id"], w["answer"], autoplay=False, caption="🔊 発音を確認")
        if correct_list:
            st.markdown("### 正解した問題（確認用）")
            st.caption("音声で確認だけできます。")
            for c in correct_list:
                st.write(f"- {c['prompt_ja']} / {c['prompt_eo']}: {c['answer_ja']} / {c['answer']}")
                play_phrase_audio(c["phrase_id"], c["answer"], autoplay=False, caption="🔊 発音を確認")

        if st.button("同じ設定で再挑戦"):
            st.session_state.q_index = 0
            st.session_state.correct = 0
            st.session_state.points_raw = 0.0
            st.session_state.points_main = 0.0
            st.session_state.points_spartan_raw = 0.0
            st.session_state.points_spartan_scaled = 0.0
            st.session_state.streak = 0
            st.session_state.answers = []
            st.session_state.showing_result = False
            st.session_state.score_saved = False
            st.session_state.pending_save_id = None
            st.session_state.score_refresh_needed = False
            st.session_state.score_sync_warning = None
            st.session_state.spartan_pending = []
            st.session_state.in_spartan_round = False
            st.session_state.spartan_current_q_idx = None
            st.session_state.spartan_attempts = 0
            st.session_state.spartan_correct_count = 0
            st.rerun()
        render_cross_language_footer("sentence_ja")
        return

    # 出題対象（通常 or スパルタ）
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
        current_q_idx = q_idx

    question = questions[current_q_idx]
    if direction == "eo_to_ja":
        prompt_text = question["prompt_eo"]
    else:
        prompt_text = question["prompt_ja"]
    compact_question_ui = compact_ui
    title_prefix = "復習" if in_spartan else f"Q{q_idx+1}/{len(questions)}"
    if in_spartan and not compact_question_ui:
        st.caption(f"スパルタ復習 残り{len(st.session_state.spartan_pending)}問 / 全{len(questions)}問")
        st.caption("間違えた問題のみをランダムに出題しています。正解でリストから消えます。")
    question_box_cls = "question-box tight" if ultra_compact_ui else "question-box"
    st.markdown(
        f"<div class='{question_box_cls}'><h3 class='question-title'>{title_prefix}: {prompt_text}</h3></div>",
        unsafe_allow_html=True,
    )
    # 進捗インジケータ（モバイルで邪魔にならない小サイズ）
    total_questions = len(questions)
    correct_so_far = st.session_state.correct
    remaining = len(st.session_state.spartan_pending) if in_spartan else max(total_questions - st.session_state.q_index, 0)
    if compact_question_ui:
        st.markdown(
            f"<div class='compact-progress'>"
            f"正解 <strong>{correct_so_far}/{total_questions}</strong> ・ "
            f"連続 <strong>{st.session_state.streak}回</strong> ・ "
            f"残り <strong>{remaining}問</strong>"
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
            cols_prog[0].markdown(f"<div class='mini-metrics'>正解数<br><strong>{correct_so_far}/{total_questions}</strong></div>", unsafe_allow_html=True)
            cols_prog[1].markdown(f"<div class='mini-metrics'>連続正解 <strong>{st.session_state.streak}回</strong></div>", unsafe_allow_html=True)
            cols_prog[2].markdown(f"<div class='mini-metrics'>残り<br><strong>{remaining}問</strong></div>", unsafe_allow_html=True)
    if direction == "eo_to_ja" and not st.session_state.showing_result:
        hide_prompt_audio = compact_question_ui and st.session_state.get("compact_hide_prompt_audio", True)
        if not hide_prompt_audio:
            play_phrase_audio(
                question["options"][question["answer_index"]]["phrase_id"],
                question["options"][question["answer_index"]]["phrase"],
                autoplay=True,
                caption="🔊 発音を聞く（問題文・自動再生）",
                instance=f"prompt-{q_idx}",
                show_caption=not compact_question_ui,
            )
        elif compact_question_ui:
            st.markdown("<div class='question-audio-hint'>🔇 問題文音声はスマホ最適化で非表示</div>", unsafe_allow_html=True)

    if st.session_state.showing_result:
        if st.session_state.last_is_correct:
            st.success(st.session_state.last_result_msg)
        else:
            st.error(st.session_state.last_result_msg)
        correct_opt = question["options"][question["answer_index"]]
        play_phrase_audio(
            correct_opt["phrase_id"],
            correct_opt["phrase"],
            autoplay=True,
            caption="🔊 正解の発音（自動再生）",
            instance=f"result-{q_idx}",
        )
        if st.button("次へ", type="primary", use_container_width=True):
            if in_spartan:
                st.session_state.showing_result = False
                st.session_state.spartan_current_q_idx = None
            else:
                st.session_state.q_index += 1
                st.session_state.showing_result = False
            st.rerun()
        render_cross_language_footer("sentence_ja")
        return

    option_labels = [opt["phrase"] if direction == "ja_to_eo" else opt["japanese"] for opt in question["options"]]
    show_option_audio = st.session_state.get("show_option_audio", True)
    if compact_question_ui and st.session_state.get("compact_hide_option_audio", True):
        show_option_audio = False
    clicked = None
    opt_gap = "small" if compact_question_ui else "medium"
    for row_start in range(0, len(option_labels), 2):
        cols = st.columns(2, gap=opt_gap)
        for j in range(2):
            idx = row_start + j
            if idx >= len(option_labels):
                continue
            with cols[j]:
                if st.button(option_labels[idx], key=f"opt-{current_q_idx}-{idx}", use_container_width=True, type="primary"):
                    clicked = idx
                opt = question["options"][idx]
                if show_option_audio:
                    play_phrase_audio(
                        opt["phrase_id"],
                        opt["phrase"],
                        autoplay=False,
                        caption="🔊",
                        instance=f"option-{current_q_idx}-{idx}",
                        show_caption=not compact_question_ui,
                    )

    if clicked is not None:
        is_correct = clicked == question["answer_index"]
        if in_spartan:
            st.session_state.spartan_attempts += 1
        st.session_state.answers.append(
            {
                "q_idx": current_q_idx,
                "selected": clicked,
                "correct": question["answer_index"],
            }
        )
        if is_correct:
            if not in_spartan:
                st.session_state.correct += 1
            else:
                st.session_state.spartan_correct_count += 1
            st.session_state.streak += 1
            opt = question["options"][clicked]
            streak_bonus = max(0, st.session_state.streak - 1) * STREAK_BONUS * STREAK_BONUS_SCALE
            earned = base_points_for_level(opt["level"]) + streak_bonus
            if in_spartan:
                st.session_state.points_spartan_raw += earned
                scaled = earned * SPARTAN_SCORE_MULTIPLIER
                st.session_state.points_spartan_scaled += scaled
                st.session_state.points_raw += scaled
                st.session_state.spartan_pending = [
                    idx for idx in st.session_state.spartan_pending if idx != current_q_idx
                ]
                st.session_state.spartan_current_q_idx = None
                if not st.session_state.spartan_pending:
                    st.session_state.in_spartan_round = False
            else:
                st.session_state.points_main += earned
                st.session_state.points_raw += earned
            if not in_spartan:
                st.session_state.q_index += 1
            st.session_state.showing_result = False
            st.rerun()
        else:
            st.session_state.streak = 0
            correct_opt = question["options"][question["answer_index"]]
            correct_text = correct_opt["japanese"] if direction == "eo_to_ja" else correct_opt["phrase"]
            st.session_state.last_result_msg = f"不正解。正解: {correct_text}"
            st.session_state.last_is_correct = False
            if st.session_state.spartan_mode and not in_spartan:
                if current_q_idx not in st.session_state.spartan_pending:
                    st.session_state.spartan_pending.append(current_q_idx)
            st.session_state.showing_result = True
            st.rerun()

    render_cross_language_footer("sentence_ja")


if __name__ == "__main__":
    main()
