# NBA Data Pipeline

A deployed NBA analytics project built with FastAPI, PostgreSQL, SQLAlchemy, Docker, and Render. The project ingests real NBA game data, stores it in Postgres, exposes analytics endpoints, tracks ingestion runs, and includes a simple live dashboard.

## Live Demo

- Dashboard: https://nba-data-pipeline-api.onrender.com/dashboard
- API docs: https://nba-data-pipeline-api.onrender.com/docs
- Health check: https://nba-data-pipeline-api.onrender.com/health
- Recent games: https://nba-data-pipeline-api.onrender.com/games?limit=5
- Team rankings: https://nba-data-pipeline-api.onrender.com/analytics/team-rankings?metric=points&limit=10&season=2025-26
- Data quality: https://nba-data-pipeline-api.onrender.com/data-quality/summary
- Matchup prediction: https://nba-data-pipeline-api.onrender.com/predictions/matchup?team_a=Indiana%20Pacers&team_b=Oklahoma%20City%20Thunder&last_n=10

## What This Project Demonstrates

- Backend API development with FastAPI
- Relational modeling with PostgreSQL and SQLAlchemy
- Real data ingestion from `nba_api`
- Idempotent loading with `(game_id, team_id)` uniqueness
- Incremental ingestion based on latest ingested game date
- Scheduled daily ingestion with GitHub Actions
- Pipeline observability with a `pipeline_runs` table
- Current-season and historical-season filtering
- Dockerized deployment
- Cloud deployment with Render and managed Postgres
- Analytics endpoints and a live HTML dashboard
- Automated endpoint tests with GitHub Actions CI

## Architecture

```text
nba_api
  -> ingest_games.py
  -> PostgreSQL games + pipeline_runs tables
  -> FastAPI analytics endpoints
  -> Render-hosted API + dashboard
```

## API Endpoints

- `GET /health`
- `GET /games?limit=5`
- `GET /games?team=Indiana&result=W&limit=5`
- `GET /teams/Indiana Pacers/summary`
- `GET /teams/Indiana Pacers/trends?last_n=5`
- `GET /leaders/points`
- `GET /analytics/team-rankings?metric=points&limit=10&season=2025-26`
- `GET /data-quality/summary`
- `GET /predictions/matchup?team_a=Indiana Pacers&team_b=Oklahoma City Thunder&last_n=10`
- `GET /pipeline/runs?limit=3`
- `GET /dashboard`

## Local Run

Inside the virtual environment:

```bash
source /Users/lalitha/nba-data-pipeline/venv/bin/activate
uvicorn main:app --reload
```

Expected result:

- `http://localhost:8000/health` returns `{"status":"ok"}`
- `http://localhost:8000/dashboard` shows the analytics dashboard

## Ingestion

Run a normal incremental load inside the virtual environment:

```bash
python ingest_games.py 2025-26
```

Run a full refresh-style load that still stays idempotent:

```bash
python ingest_games.py 2025-26 --full-refresh
```

Expected result:

- If new games exist, rows are inserted into `games`
- If data already exists, duplicates are skipped
- Every run is recorded in `pipeline_runs`

The project currently supports both the 2024-25 and 2025-26 seasons. The dashboard defaults to the latest loaded season.

## Scheduled Ingestion

This repo includes `.github/workflows/daily-ingestion.yml`, which runs an incremental current-season ingestion every day at 11:30 UTC and can also be triggered manually from GitHub Actions.

Required GitHub repository secret:

```text
RENDER_DATABASE_URL
```

Use the Render Postgres external database URL as the secret value. The workflow maps that secret to `DATABASE_URL`, installs dependencies, and runs:

```bash
python scripts/run_daily_ingestion.py
```

Expected result:

- New NBA team-game rows are inserted when new games are available
- Existing rows are skipped by the `(game_id, team_id)` uniqueness rule
- Every scheduled run is recorded in `pipeline_runs`
- A failed ingestion exits non-zero so GitHub Actions marks the run as failed

## Docker Run

Build the image outside the virtual environment:

```bash
docker build -t nba-data-pipeline .
```

Run the API container:

```bash
docker run --env-file .env -p 8000:8000 nba-data-pipeline
```

If PostgreSQL is running on your Mac host, use a Docker-accessible connection string:

```env
DATABASE_URL=postgresql://lalitha@host.docker.internal/nba_pipeline
```

Expected result:

- `http://localhost:8000/health` returns `{"status":"ok"}`

## Render Deployment

This repo includes `render.yaml`, which defines:

- a Docker-based FastAPI web service
- a managed Render Postgres database
- automatic `DATABASE_URL` wiring from the database to the web service

After a successful Render deploy, the production database starts empty. Populate it by running ingestion against the Render external database URL.

## Resume Summary

Built and deployed an NBA data pipeline using FastAPI, PostgreSQL, SQLAlchemy, Docker, GitHub Actions, and Render. Implemented idempotent incremental ingestion from `nba_api`, scheduled daily refreshes, pipeline run tracking, analytics endpoints, and a live dashboard backed by real NBA game data.

## Future Improvements

- Add data quality checks for row counts, nulls, and duplicate keys
- Add a richer frontend dashboard with interactive charts
- Replace the heuristic prediction endpoint with a trained model
- Expand CI to include linting and deployment smoke tests
