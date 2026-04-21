import json
import logging
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

from bluewings.sql import upsert_matches

log = logging.getLogger(__name__)

KLEAGUE_API_URL = "https://www.kleague.com/getScheduleList.do"
TEAM_ID = "K02"
LEAGUE_ID = "2"

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
}


def _fetch_schedule(**context):
    year = str(datetime.now().year)
    all_matches = []

    for month in range(1, 13):
        payload = {
            "leagueId": LEAGUE_ID,
            "teamId": TEAM_ID,
            "year": year,
            "month": f"{month:02d}",
        }
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.kleague.com/club/club.do?teamId={TEAM_ID}",
        }

        log.info(">> 요청: POST %s | payload=%s", KLEAGUE_API_URL, json.dumps(payload, ensure_ascii=False))

        resp = requests.post(KLEAGUE_API_URL, json=payload, headers=headers, timeout=30)
        log.info("<< 응답: status=%d, size=%d bytes", resp.status_code, len(resp.content))
        resp.raise_for_status()
        data = resp.json()

        result_code = data.get("resultCode")
        result_msg = data.get("resultMsg")
        log.info("<< resultCode=%s, resultMsg=%s", result_code, result_msg)

        if result_code != "200":
            log.warning("Month %02d: API 실패 - %s", month, result_msg)
            continue

        schedule_list = data.get("data", {}).get("scheduleList", [])
        matched = 0
        for match in schedule_list:
            home_id = match.get("homeTeam", "")
            away_id = match.get("awayTeam", "")
            if TEAM_ID not in (home_id, away_id):
                continue

            match_date = match.get("gameDate", "")
            if not match_date:
                continue

            formatted_date = match_date.replace(".", "-")
            game_time = match.get("gameTime")

            # gameStatus: FE=종료, 1S=전반, 2S=후반, HT=하프타임, 그 외=경기전
            game_status = match.get("gameStatus", "")
            end_yn = match.get("endYn", "")
            if end_yn == "Y" or game_status == "FE":
                status = "FINISHED"
            elif game_status in ("1S", "2S", "HT"):
                status = "LIVE"
            else:
                status = "SCHEDULED"

            # 경기 전이면 스코어를 null로 처리 (API가 0:0을 반환하는 케이스 방어)
            if status == "SCHEDULED":
                home_score = None
                away_score = None
            else:
                home_score = match.get("homeGoal")
                away_score = match.get("awayGoal")

            round_id = match.get("roundId")
            match_day = int(round_id) if round_id is not None else None

            match_data = {
                "match_date": formatted_date,
                "match_time": game_time,
                "home_team": match.get("homeTeamName", ""),
                "away_team": match.get("awayTeamName", ""),
                "home_score": int(home_score) if home_score is not None else None,
                "away_score": int(away_score) if away_score is not None else None,
                "stadium": match.get("fieldName", ""),
                "competition": "K리그2",
                "season": year,
                "match_day": match_day,
                "status": status,
            }
            all_matches.append(match_data)
            matched += 1

            log.info(
                "  R%s %s | %s vs %s | %s | %s %s",
                match_day,
                formatted_date,
                match_data["home_team"],
                match_data["away_team"],
                game_time or "TBD",
                f"{home_score}:{away_score}" if status == "FINISHED" else "",
                status,
            )

        log.info("Month %02d: 전체 %d경기 중 블루윙즈 %d경기", month, len(schedule_list), matched)

    log.info("=== 수집 완료: 총 %d경기 ===", len(all_matches))
    context["ti"].xcom_push(key="matches", value=all_matches)


def _upsert_matches(**context):
    matches = context["ti"].xcom_pull(key="matches", task_ids="fetch_schedule")
    log.info("Upsert 시작: %d건", len(matches) if matches else 0)
    count = upsert_matches(matches)
    log.info("Upsert 완료: %d건 처리", count)


with DAG(
    dag_id="bluewings_schedule_collector",
    default_args=default_args,
    description="수원 삼성 블루윙즈 경기 일정 수집 (K리그 API → Supabase)",
    schedule="0 9 * * 3",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bluewings", "schedule"],
) as dag:

    fetch_schedule = PythonOperator(
        task_id="fetch_schedule",
        python_callable=_fetch_schedule,
    )

    upsert_to_supabase = PythonOperator(
        task_id="upsert_to_supabase",
        python_callable=_upsert_matches,
    )

    fetch_schedule >> upsert_to_supabase
