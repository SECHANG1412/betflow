# BetFlow

Betman의 과거·현재 배당과 배당 흐름을 분석해 승·무·패 통계를 제공하는 서비스입니다.

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

Python 가상환경 디렉터리는 `apps/api/venv`를 사용합니다.

```powershell
Set-Location apps/api
uv venv venv --python 3.12
$env:UV_PROJECT_ENVIRONMENT = "venv"
uv sync
uv run fastapi dev app/main.py --port 8001
```

API 문서는 `http://localhost:8001/docs`, 헬스 체크는 `http://localhost:8001/health`에서 확인합니다.

테스트와 정적 검사는 다음 명령으로 실행합니다.

```powershell
$env:UV_PROJECT_ENVIRONMENT = "venv"
uv run pytest
uv run ruff check app tests migrations
```

## 데이터베이스 마이그레이션

`apps/api`에서 다음 명령을 실행합니다.

```powershell
$env:UV_PROJECT_ENVIRONMENT = "venv"
uv run alembic upgrade head
```

새 마이그레이션을 생성할 때는 변경 목적이 드러나는 이름을 사용합니다.

```powershell
uv run alembic revision --autogenerate -m "create odds tables"
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

