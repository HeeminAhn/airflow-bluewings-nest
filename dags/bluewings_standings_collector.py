import logging
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

from bluewings.sql import upsert_standings
from bluewings.teams import short_to_full

log = logging.getLogger(__name__)

KLEAGUE_RANK_URL = "https://www.kleague.com/record/teamRank.do"
LEAGUE_ID = "2"

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
}


def _fetch_standings(**context):
    season = str(datetime.now().year)
    params = {
        "leagueId": LEAGUE_ID,
        "year": season,
        "stadium": "all",
        "recordType": "rank",
    }
    headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.kleague.com/record/team.do",
    }

    log.info(">> 요청: GET %s | params=%s", KLEAGUE_RANK_URL, params)
    resp = requests.get(KLEAGUE_RANK_URL, params=params, headers=headers, timeout=30)
    log.info("<< 응답: status=%d, size=%d bytes", resp.status_code, len(resp.content))
    resp.raise_for_status()
    data = resp.json()

    result_code = data.get("resultCode")
    result_msg = data.get("resultMsg")
    log.info("<< resultCode=%s, resultMsg=%s", result_code, result_msg)
    if result_code != "200":
        raise RuntimeError(f"K리그 API 실패: resultCode={result_code}, msg={result_msg}")

    team_rank = data.get("data", {}).get("teamRank", [])
    if not team_rank:
        log.warning("순위 데이터가 비어 있습니다 (season=%s) — upsert 생략", season)
        context["ti"].xcom_push(key="season", value=season)
        context["ti"].xcom_push(key="standings", value=[])
        return

    standings = []
    for row in team_rank:
        short = row["teamName"]
        full_name = short_to_full(short)
        standing = {
            "season": season,
            "team_name": full_name,
            "position": int(row["rank"]),
            "played": int(row["gameCount"]),
            "won": int(row["winCnt"]),
            "drawn": int(row["tieCnt"]),
            "lost": int(row["lossCnt"]),
            "goals_for": int(row["gainGoal"]),
            "goals_against": int(row["lossGoal"]),
            "goal_difference": int(row["gapCnt"]),
            "points": int(row["gainPoint"]),
        }
        standings.append(standing)
        log.info(
            "  %2d. %-15s | %2dG %2dW %2dD %2dL | %3d:%-3d (%+d) | %2d pts",
            standing["position"], standing["team_name"],
            standing["played"], standing["won"], standing["drawn"], standing["lost"],
            standing["goals_for"], standing["goals_against"], standing["goal_difference"],
            standing["points"],
        )

    log.info("=== 수집 완료: season=%s, %d팀 ===", season, len(standings))
    context["ti"].xcom_push(key="season", value=season)
    context["ti"].xcom_push(key="standings", value=standings)


def _upsert_standings(**context):
    season = context["ti"].xcom_pull(key="season", task_ids="fetch_standings")
    standings = context["ti"].xcom_pull(key="standings", task_ids="fetch_standings")
    log.info("Upsert 시작: season=%s, %d팀", season, len(standings) if standings else 0)
    count = upsert_standings(season, standings)
    log.info("Upsert 완료: %d팀 처리", count)


with DAG(
    dag_id="bluewings_standings_collector",
    default_args=default_args,
    description="K리그2 순위 수집 (K리그 API → Supabase)",
    schedule="0 10 * * 1",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bluewings", "standings"],
) as dag:

    fetch_standings = PythonOperator(
        task_id="fetch_standings",
        python_callable=_fetch_standings,
    )

    upsert_to_supabase = PythonOperator(
        task_id="upsert_to_supabase",
        python_callable=_upsert_standings,
    )

    fetch_standings >> upsert_to_supabase
