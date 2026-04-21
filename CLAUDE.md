# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Apache Airflow 3.1.8 / Python 3.12 개발 환경. Docker Compose 기반 CeleryExecutor 구성으로 PostgreSQL(메타데이터) + Redis(브로커)를 사용한다. 다른 Python 버전이 필요하면 `.env`의 이미지 태그를 변경한다 (예: `apache/airflow:3.1.8-python3.11`).

## Commands

### 환경 시작/종료
```bash
docker compose up airflow-init       # 최초 1회: DB 마이그레이션 + 관리자 계정 생성
docker compose up -d                 # 전체 서비스 시작
docker compose down                  # 서비스 종료
docker compose down -v               # 서비스 종료 + 볼륨(DB 데이터) 삭제
```

### 커스텀 이미지 빌드
docker-compose.yml에서 `image:` 줄을 주석처리하고 `build: .`을 활성화한 뒤:
```bash
docker compose build                 # requirements.txt 변경 시 재빌드
docker compose up -d
```

### 모니터링/디버깅
```bash
docker compose --profile flower up -d   # Flower(Celery 모니터링) 활성화 → localhost:5555
docker compose --profile debug run airflow-cli   # Airflow CLI 접근
docker compose logs -f airflow-scheduler         # 특정 서비스 로그
```

## Architecture

**서비스 구성 (docker-compose.yml):**
- `airflow-apiserver` — REST API + 웹 UI (포트 9090). Airflow 3.x에서 webserver를 대체
- `airflow-scheduler` — DAG 스케줄링 (헬스체크 포트 8974)
- `airflow-dag-processor` — DAG 파일 파싱 (3.x에서 scheduler로부터 분리된 별도 프로세스)
- `airflow-worker` — Celery 워커, 실제 태스크 실행. apiserver healthy 후 시작
- `airflow-triggerer` — Deferrable 오퍼레이터의 비동기 이벤트 처리
- `postgres:16` / `redis:7.2-bookworm` — 메타데이터 DB / Celery 브로커

**디렉토리 → 컨테이너 마운트:**
- `dags/` → `/opt/airflow/dags` — DAG 정의 파일
- `plugins/` → `/opt/airflow/plugins` — 커스텀 오퍼레이터/훅/센서
- `config/` → `/opt/airflow/config` — airflow.cfg 등 설정 파일
- `logs/` → `/opt/airflow/logs` — 태스크 실행 로그

**인증:** FabAuthManager + JWT (기본 계정 airflow/airflow, `.env`에서 변경)

## DAG 작성 규칙

DAG 파일은 `dags/` 디렉토리에 배치하면 dag-processor가 자동 감지한다. `dags/example_dag.py`를 참고 템플릿으로 활용할 것.

**Import 규칙 (Airflow 3.x):**
- `from airflow.providers.standard.operators.bash import BashOperator`
- `from airflow.providers.standard.operators.python import PythonOperator`
- `airflow.operators.*` 경로는 deprecated이므로 사용하지 않는다.

**코드 분리 규칙:**
- DAG 파일(`dags/`)에는 DAG 정의와 태스크 오케스트레이션만 작성한다.
- SQL 쿼리, DB 접속 로직 등 재사용 가능한 코드는 `plugins/` 아래 모듈로 분리한다.
- 현재 구조:
  - `plugins/bluewings/sql.py` — Supabase DB 연결 + SQL 쿼리 (upsert 등)
  - `dags/bluewings_schedule_collector.py` — K리그 API 수집 + 태스크 정의

**외부 연동:**
- Supabase PostgreSQL — Connection ID: `supabase_postgres` (환경변수로 자동 등록)
- 대상 스키마: `bluewings_nest` (public 아님)

## 로컬 테스트

코드 변경 시 반드시 로컬 환경에서 테스트 가능하도록 해야 한다. DAG 파일 작성·수정 후에는 `docker compose` 환경에서 실제 동작을 확인한다.

```bash
# DAG 파싱 오류 확인
docker compose logs -f airflow-dag-processor

# 특정 DAG 수동 트리거
docker compose exec airflow-worker airflow dags test <dag_id> 2026-01-01
```
