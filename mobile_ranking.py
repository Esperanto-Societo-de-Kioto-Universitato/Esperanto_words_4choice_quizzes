from score_append_utils import load_sheet_records
from ranking_utils import HOF_THRESHOLD, RANKING_TOP_N, ranking_rows, summarize_rankings_from_stats


SCORES_SHEET = "Scores"
USER_STATS_SHEET = "UserStats"


def _ranking_result(payload, *, ok, message, rankings=None, own=None, source="unavailable"):
    return {
        "type": "rankings_result",
        "requestId": str(payload.get("requestId", "")),
        "ok": bool(ok),
        "message": message,
        "source": source,
        "rankings": rankings or {"overall": [], "today": [], "month": [], "hof": []},
        "own": own or {},
        "updatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def load_mobile_rankings_request(payload):
    if not isinstance(payload, dict) or payload.get("type") != "load_rankings":
        return _ranking_result({}, ok=False, message="ランキング取得要求の形式が不正です。")

    user = str(payload.get("user") or "").strip()
    stats_rows = load_sheet_records(USER_STATS_SHEET, refresh=True)
    score_rows = load_sheet_records(SCORES_SHEET, refresh=True)

    if stats_rows is None and score_rows is None:
        return _ranking_result(
            payload,
            ok=False,
            message="ランキングを取得できませんでした。Secrets設定とSheets共有権限を確認してください。",
        )

    overall_totals, today_totals, month_totals, hof_totals = summarize_rankings_from_stats(
        stats_rows or [],
        score_rows=score_rows or [],
        hof_threshold=HOF_THRESHOLD,
    )

    overall_rows, own_overall = ranking_rows(overall_totals, current_user=user, top_n=RANKING_TOP_N)
    today_rows, own_today = ranking_rows(today_totals, current_user=user, top_n=RANKING_TOP_N)
    month_rows, own_month = ranking_rows(month_totals, current_user=user, top_n=RANKING_TOP_N)
    hof_rows, own_hof = ranking_rows(hof_totals, current_user=user, top_n=RANKING_TOP_N)

    source = "live"
    warning = ""
    if stats_rows is None:
        source = "scores_only"
        warning = "累積ランキングはScoresログ集計から表示しています。"
    elif score_rows is None:
        source = "stats_only"
        warning = "本日・今月ランキングはScoresログを取得できないため空表示です。"

    return _ranking_result(
        payload,
        ok=True,
        message=warning or "ランキングを更新しました。",
        source=source,
        rankings={
            "overall": overall_rows,
            "today": today_rows,
            "month": month_rows,
            "hof": hof_rows,
        },
        own={
            "overall": own_overall,
            "today": own_today,
            "month": own_month,
            "hof": own_hof,
        },
    )
