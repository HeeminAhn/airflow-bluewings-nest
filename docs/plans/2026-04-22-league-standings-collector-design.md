# K리그2 순위 수집 DAG 설계

- 작성일: 2026-04-22
- 대상: `bluewings_nest.league_standings` 테이블
- 데이터 소스: `https://www.kleague.com/record/teamRank.do`

## 배경

기존 `bluewings_schedule_collector` DAG가 수원삼성블루윙즈(K리그2) 경기 일정을 K리그 API로부터 수집해 `bluewings_nest.matches` 테이블에 저장한다. 같은 패턴으로 K리그2 전체 팀 순위를 수집해 `bluewings_nest.league_standings` 테이블에 주기적으로 반영한다.

## 데이터 소스

- **Method/URL**: `GET https://www.kleague.com/record/teamRank.do`
- **Query**: `leagueId=2`, `year=<현재연도>`, `stadium=all`, `recordType=rank`
- **응답**:
  ```json
  {
    "resultCode": "200",
    "resultMsg": "성공",
    "data": {
      "year": 2026,
      "teamRank": [
        {
          "rank": 1, "teamName": "부산",
          "gainPoint": 22, "winCnt": 7, "tieCnt": 1, "lossCnt": 0,
          "gameCount": 8, "gainGoal": 18, "lossGoal": 8, "gapCnt": 10
        }
      ]
    }
  }
  ```

## DB 필드 매핑

| `league_standings` 컬럼 | `teamRank[]` 필드 |
|---|---|
| season | 쿼리 파라미터 `year` (varchar) |
| team_name | `teamName` (약칭 → 전체명 매핑 후 저장) |
| position | `rank` |
| played | `gameCount` |
| won | `winCnt` |
| drawn | `tieCnt` |
| lost | `lossCnt` |
| goals_for | `gainGoal` |
| goals_against | `lossGoal` |
| goal_difference | `gapCnt` |
| points | `gainPoint` |
| updated_at | `NOW()` |

## 아키텍처

### 파일 구성

- `plugins/bluewings/teams.py` (신규) — K리그2 약칭 → 전체명 매핑 dict
- `plugins/bluewings/sql.py` — `UPSERT_STANDINGS_SQL`, `upsert_standings()` 추가
- `dags/bluewings_standings_collector.py` (신규) — DAG 정의

### 태스크 흐름

```
fetch_standings  →  upsert_standings
```

- `fetch_standings`: API 호출 → `resultCode == "200"` 검증 → `teamRank[]` 순회 → 약칭을 전체명으로 매핑 → XCom push
- `upsert_standings`: XCom pull → `upsert_standings()` 호출

### Upsert 전략

`(season, team_name)` UNIQUE 제약이 현재 테이블에 없고, `flyway_schema_history` 테이블이 존재해 스키마는 백엔드 Flyway에서 관리되는 것으로 보인다. 스키마 변경을 피하기 위해 **한 트랜잭션 내 DELETE + INSERT** 로 구현한다.

```sql
BEGIN;
DELETE FROM bluewings_nest.league_standings WHERE season = %s;
INSERT INTO bluewings_nest.league_standings (
    season, team_name, position, played, won, drawn, lost,
    goals_for, goals_against, goal_difference, points, updated_at
) VALUES (..., NOW());
COMMIT;
```

- 실패 시 `rollback()` → 빈 상태로 남지 않음
- 시즌 단위로 전체 갈아끼우는 구조 (순위 이력은 별도 요건 아님)
- 12팀 미만이라 성능 무관

### 팀명 매핑 정책

- API는 약칭 ("수원", "부산")만 반환 → `matches` 테이블은 전체명("수원삼성블루윙즈") 저장
- `teams.py`의 `K_LEAGUE_2_SHORT_TO_FULL` dict에서 전체명으로 변환 후 저장
- 매핑에 없는 약칭이 들어오면 **예외 raise** (조용히 넘기지 않음) — 시즌별 팀 구성 변경을 빨리 감지
- 전체명은 K리그 API가 일정 조회 시 돌려주는 `homeTeamName` 값과 일치시킴

## DAG 설정

```python
DAG(
    dag_id="bluewings_standings_collector",
    schedule="0 10 * * 1",       # 매주 월요일 10시 (주말 경기 후)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["bluewings", "standings"],
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=3),
    },
)
```

- `season = str(datetime.now().year)` — 현재 시즌 자동 추출 (기존 schedule_collector 패턴 재사용)

## 에러 처리

- HTTP 오류 → `resp.raise_for_status()`
- `resultCode != "200"` → 예외 raise (태스크 실패 → Airflow 재시도)
- 매핑에 없는 팀명 → 예외 raise
- `teamRank[]`가 비어 있으면 → 경고 로그 후 upsert 호출 자체를 skip (DELETE도 하지 않음)

## 검증

```bash
# DAG 파싱 오류 확인
docker compose logs -f airflow-dag-processor

# 수동 트리거
docker compose exec airflow-worker airflow dags test bluewings_standings_collector 2026-04-22

# DB 확인
SELECT position, team_name, played, won, drawn, lost, points
FROM bluewings_nest.league_standings
WHERE season = '2026'
ORDER BY position;
```

## YAGNI

- K리그1 확장, 순위 이력 저장, 웹훅 알림 등은 요건이 명확해지기 전에는 구현하지 않음
- 팀명 매핑은 하드코딩으로 시작 (별도 `teams` DB 테이블 도입하지 않음)
