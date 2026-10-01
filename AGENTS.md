# Repository Guidelines

## 프로젝트 구조와 모듈 구성

이 저장소는 Python 3.14.6 및 Apache Airflow 3.3.2 기반의 Docker Compose 프로젝트입니다. `dags/`에는 스케줄 수집 및 순위 수집 DAG와 예제 DAG를 둡니다. `plugins/bluewings/`는 SQL 및 Supabase 저장 로직처럼 DAG에서 재사용하는 코드를 담당합니다. Airflow 설정은 `config/airflow.cfg`, 이미지 설정은 `Dockerfile`, 서비스 구성은 `docker-compose.yml`에서 관리합니다. 설계 문서는 `docs/plans/`에 있습니다. 실행 로그와 `.env`는 저장소에 추가하지 마세요.

## 빌드, 실행 및 개발 명령

- `cp .env.example .env`: 로컬 환경 설정 파일을 준비합니다. Supabase 접속 정보와 Fernet 키를 채우세요.
- `docker compose up airflow-init`: 최초 데이터베이스 마이그레이션 및 관리자 계정 생성을 수행합니다.
- `docker compose up -d`: Airflow 서비스 전체를 백그라운드로 시작합니다. UI는 `http://localhost:9090`에서 확인합니다.
- `docker compose down`: 서비스를 종료합니다. `-v` 옵션은 데이터베이스 볼륨까지 삭제하므로 주의하세요.
- `docker compose exec airflow-worker airflow dags test <dag_id> 2026-01-01`: 지정한 실행 날짜로 DAG를 수동 검증합니다.
- `docker compose logs -f airflow-dag-processor`: DAG 파싱 및 로딩 오류를 확인합니다.

## 코딩 스타일 및 명명 규칙

Python은 PEP 8 스타일을 따르고 들여쓰기는 공백 4칸을 사용합니다. 파일과 모듈은 `snake_case`, DAG ID는 설명이 분명한 `snake_case`로 작성합니다. Airflow 3.x Provider import 경로를 사용하세요. 예: `airflow.providers.standard.operators.python`. DAG 파일에는 DAG 정의와 작업 흐름을 두고, SQL·DB 접근 코드는 `plugins/` 아래 모듈로 분리합니다.

## 테스트 지침

별도 테스트 프레임워크나 커버리지 기준은 현재 설정되어 있지 않습니다. DAG 변경 후에는 위 `airflow dags test` 명령으로 실제 실행을 확인하고, DAG Processor 로그에서 import 오류가 없는지 살펴보세요. 외부 API나 Supabase가 필요한 작업은 `.env`와 연결 설정을 준비한 뒤 검증합니다.

## 커밋 및 풀 리퀘스트

최근 커밋은 `feat(standings): ...`, `docs: ...`처럼 Conventional Commits 형식을 사용합니다. 변경 범위를 나타내는 짧은 제목을 작성하세요. PR에는 목적, 주요 변경점, 실행 또는 검증 방법과 결과를 적고 관련 이슈가 있으면 연결합니다. Airflow UI나 동작에 영향을 주는 변경은 재현 단계 또는 화면 캡처를 첨부하세요.

## 보안 및 설정

비밀값은 `.env`에만 두고 커밋하지 마세요. `.env.example`에는 변수명과 안전한 기본값만 기록합니다. 기본 Airflow 관리자 자격 증명은 로컬 개발용이므로 배포 환경에서 반드시 변경하세요.
