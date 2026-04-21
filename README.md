# airflow-bluewings-nest

수원 삼성 블루윙즈 경기 일정을 K리그 공식 API에서 수집해 Supabase PostgreSQL에 적재하는 Apache Airflow 프로젝트.

## 구성

- **Airflow 3.1.8** / **Python 3.12**
- **Docker Compose** 기반 CeleryExecutor
- **PostgreSQL 16** (Airflow 메타데이터) / **Redis 7.2** (Celery 브로커)
- **Supabase PostgreSQL** (수집 데이터 저장소)

## 서비스 구성

| 서비스 | 역할 | 포트 |
|---|---|---|
| `airflow-apiserver` | REST API + 웹 UI (Airflow 3.x에서 webserver 대체) | 9090 |
| `airflow-scheduler` | DAG 스케줄링 | 8974 (헬스체크) |
| `airflow-dag-processor` | DAG 파일 파싱 (3.x에서 scheduler로부터 분리) | - |
| `airflow-worker` | Celery 워커, 태스크 실행 | - |
| `airflow-triggerer` | Deferrable 오퍼레이터의 비동기 이벤트 처리 | - |
| `postgres` | Airflow 메타데이터 DB | - |
| `redis` | Celery 브로커 | - |
| `flower` (optional) | Celery 모니터링 | 5555 |

## 디렉토리 구조

```
.
├── dags/                           # DAG 정의 파일
│   ├── bluewings_schedule_collector.py
│   └── example_dag.py
├── plugins/                        # 커스텀 오퍼레이터/훅/재사용 모듈
│   └── bluewings/
│       └── sql.py                  # Supabase upsert 로직
├── config/                         # airflow.cfg 등
├── logs/                           # 태스크 실행 로그 (gitignored)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env                            # 환경변수 (gitignored)
```

## 시작하기

### 1. 최초 실행

```bash
docker compose up airflow-init       # DB 마이그레이션 + 관리자 계정 생성
docker compose up -d                 # 전체 서비스 시작
```

웹 UI: http://localhost:9090 (기본 계정 `airflow` / `airflow`, `.env`에서 변경)

### 2. 종료

```bash
docker compose down                  # 서비스만 종료
docker compose down -v               # 볼륨(DB 데이터)까지 삭제
```

### 3. 커스텀 이미지 빌드

`requirements.txt` 등 의존성을 추가해야 할 경우, `docker-compose.yml`에서 `image:` 줄을 주석처리하고 `build: .`을 활성화:

```bash
docker compose build
docker compose up -d
```

### 4. 모니터링/디버깅

```bash
docker compose --profile flower up -d                # Flower 활성화
docker compose --profile debug run airflow-cli       # Airflow CLI 접근
docker compose logs -f airflow-scheduler             # 특정 서비스 로그
docker compose logs -f airflow-dag-processor         # DAG 파싱 오류 확인
```

## DAG 소개

### `bluewings_schedule_collector`

- **스케줄:** 매주 수요일 09:00 (`0 9 * * 3`)
- **흐름:**
  1. `fetch_schedule` — K리그 API(`getScheduleList.do`)에서 1~12월 전 경기 조회 후, 블루윙즈(K02) 경기만 필터링하여 XCom에 저장
  2. `upsert_to_supabase` — `bluewings_nest.matches` 테이블에 `(match_date, home_team, away_team)` 키 기준 upsert
- **수집 필드:** 날짜/시간, 홈·원정팀, 스코어, 경기장, 라운드, 경기 상태(`SCHEDULED`/`LIVE`/`FINISHED`)
- **상태 판정 로직:** `endYn`, `gameStatus`(`FE`/`1S`/`2S`/`HT`) 조합으로 결정하며, 경기 전인 경우 API가 `0:0`을 반환하더라도 스코어를 `NULL`로 저장

## 외부 연동

- **Supabase PostgreSQL**
  - Connection ID: `supabase_postgres` (환경변수로 자동 등록)
  - 스키마: `bluewings_nest` (public 아님)
  - 대상 테이블: `bluewings_nest.matches`

## DAG 작성 규칙 (Airflow 3.x)

- Import 경로는 Provider 패키지 사용:
  ```python
  from airflow.providers.standard.operators.bash import BashOperator
  from airflow.providers.standard.operators.python import PythonOperator
  ```
  `airflow.operators.*`는 deprecated.
- DAG 파일에는 **DAG 정의와 태스크 오케스트레이션만** 작성. SQL/DB 로직 등 재사용 코드는 `plugins/` 아래 모듈로 분리.

## 로컬 테스트

```bash
# 특정 DAG 수동 트리거
docker compose exec airflow-worker airflow dags test bluewings_schedule_collector 2026-01-01

# DAG 파싱 오류 확인
docker compose logs -f airflow-dag-processor
```

## Python 버전 변경

다른 Python 버전이 필요하면 `.env`의 이미지 태그를 변경:

```
AIRFLOW_IMAGE_NAME=apache/airflow:3.1.8-python3.11
```
