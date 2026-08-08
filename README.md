# BetFlow

과거 스포츠 경기의 승·무·패 배당 변화 시퀀스를 분석해 경기 결과 예측에 활용하는 프로젝트입니다.
초기 배당과 최종 배당만 비교하지 않고, 공개된 중간 변경 순서까지 하나의 흐름으로 다루는 것을
핵심 목표로 합니다.

## 현재 개발 단계

와이즈토토 공개 데이터로 2010~2026년 회차를 조사해 로그인이나 유료 API 없이 배당 변경 순서와
경기 결과를 수집할 수 있음을 확인했습니다. 현재는 이 검증 결과를 바탕으로 실제 분석·학습용 원본
시퀀스를 수집하는 파이프라인을 개발하기 직전입니다.

현재 우선순위는 다음과 같습니다.

1. 2010~2026년 배당 시퀀스 전체 수집
2. 재시도·체크포인트·오류 격리를 포함한 수집 안정화
3. 수집 데이터의 중복·결측·분포 검증
4. 검증된 학습 데이터셋 구축

데이터 검증이 끝나기 전까지 예측 모델, 프론트엔드 기능 확장, 최종 데이터베이스 설계는 본격적으로
진행하지 않습니다.

## 확인된 데이터 제약

- 배당 변경의 정확한 시각은 공개되지 않으며 변경 순서만 확인 가능
- 공개 이력이 실제 발생한 모든 변경을 포함한다는 보장 부재
- 2010~2012년 데이터에서 경기당 최대 2개 스냅샷만 확인
- 원문이 불일치하는 데이터는 임의 보정하지 않고 별도 격리 필요
- 비공식 HTML·AJAX 구조 의존에 따른 사이트 개편 대응 필요

검증 과정과 결과는 [`docs`](docs)에서 확인할 수 있습니다.

## 기술 스택
- Web: Next.js 16, React 19, TypeScript, Tailwind CSS
- API: FastAPI, Python 3.12, SQLAlchemy
- Database: PostgreSQL 17, Alembic
- Package managers: pnpm, uv

## 사전 요구사항

- Docker Desktop
- Node.js 22 이상
- pnpm 10
- uv

## 환경변수

API 개발용 환경변수 파일을 생성합니다.

```powershell
Copy-Item .env.example apps/api/.env
```

`.env.example`에는 로컬 개발 기본값만 포함되어 있습니다. 실제 비밀번호나 운영 환경 값은 커밋하지 않습니다.

## Python 가상환경

Python 가상환경은 프로젝트 루트의 `venv` 디렉터리를 사용합니다.

프로젝트 루트에서 가상환경을 생성하고 활성화합니다.

```powershell
uv venv venv --python 3.12
venv\scripts\activate
```

활성화한 루트 가상환경에 API 의존성을 설치합니다.

```powershell
uv sync --project apps/api --active
```

가상환경을 종료할 때는 다음 명령을 실행합니다.

```powershell
deactivate
```

## PostgreSQL 실행

프로젝트 루트에서 다음 명령을 실행합니다.

```powershell
docker compose up -d postgres
docker compose ps
```

PostgreSQL은 `localhost:5432`에서 실행됩니다.

종료할 때는 데이터 볼륨을 유지한 채 컨테이너만 중지합니다.

```powershell
docker compose stop postgres
```

## API 실행

프로젝트 루트에서 가상환경을 활성화한 뒤 API 디렉터리로 이동합니다.

```powershell
venv\scripts\activate
Set-Location apps/api
fastapi dev app/main.py --port 8001
```

API 문서는 `http://localhost:8001/docs`, 헬스 체크는 `http://localhost:8001/health`에서 확인합니다.

테스트와 정적 검사는 `apps/api`에서 실행합니다.

```powershell
pytest
ruff check app tests migrations
```

## 데이터베이스 마이그레이션

루트 가상환경을 활성화하고 `apps/api`로 이동한 뒤 실행합니다.

```powershell
alembic upgrade head
```

새 마이그레이션을 생성할 때는 변경 목적이 드러나는 이름을 사용합니다.

```powershell
alembic revision --autogenerate -m "create odds tables"
```

## Web 실행

프로젝트 루트에서 의존성을 설치하고 개발 서버를 실행합니다.

```powershell
pnpm.cmd install
pnpm.cmd dev:web
```

Web은 `http://localhost:3000`에서 실행됩니다.

검증 명령은 다음과 같습니다.

```powershell
pnpm.cmd --filter @betflow/web lint
pnpm.cmd --filter @betflow/web typecheck
pnpm.cmd --filter @betflow/web build
```

PowerShell 실행 정책으로 `pnpm.ps1` 실행이 차단된 환경에서는 `pnpm` 대신 `pnpm.cmd`를 사용합니다.

