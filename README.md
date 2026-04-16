# NBA Data Pipeline

A deployed NBA analytics project built with FastAPI, PostgreSQL, SQLAlchemy, Docker, and Render. The project ingests real NBA game data, stores it in Postgres, exposes analytics endpoints, tracks ingestion runs, and includes a simple live dashboard.

## Project Highlights

- Automated data pipeline with incremental, idempotent NBA game ingestion
- Production-style observability through `pipeline_runs`
- Deployed FastAPI service backed by managed PostgreSQL
- Live dashboard for analytics, ingestion health, and ML prediction
- Baseline scikit-learn model served through an API endpoint
- GitHub Actions for CI and scheduled ingestion triggers

## Live Demo

- Dashboard: https://nba-data-pipeline-api.onrender.com/dashboard
- API docs: https://nba-data-pipeline-api.onrender.com/docs
- Health check: https://nba-data-pipeline-api.onrender.com/health
- Recent games: https://nba-data-pipeline-api.onrender.com/games?limit=5
- Team rankings: https://nba-data-pipeline-api.onrender.com/analytics/team-rankings?metric=points&limit=10&season=2025-26
- Data quality: https://nba-data-pipeline-api.onrender.com/data-quality/summary
- Matchup prediction: https://nba-data-pipeline-api.onrender.com/predictions/matchup?team_a=Indiana%20Pacers&team_b=Oklahoma%20City%20Thunder&last_n=10

Recommended demo path:

1. Open the dashboard and point out live database metrics, pipeline status, and ML model metrics.
2. Open `/pipeline/runs?limit=3` to show scheduled ingestion history.
3. Open `/data-quality/summary` to show automated data quality checks.
4. Open `/predictions/matchup?...` to show the model-backed prediction response.

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
- Baseline ML training pipeline for matchup win probability

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

This repo includes `.github/workflows/daily-ingestion.yml`, which triggers an incremental current-season ingestion every day at 11:30 UTC and can also be triggered manually from GitHub Actions.

The workflow calls the deployed Render API instead of fetching NBA data directly from GitHub Actions. This avoids GitHub runner timeouts against `stats.nba.com` and keeps ingestion close to the deployed database.

```text
POST https://nba-data-pipeline-api.onrender.com/admin/ingest?season=2025-26
```

Expected result:

- GitHub Actions receives an immediate `accepted` response from Render
- New NBA team-game rows are inserted when new games are available
- Existing rows are skipped by the `(game_id, team_id)` uniqueness rule
- Every scheduled run is recorded in `pipeline_runs`
- Ingestion success or failure is visible in `/pipeline/runs`

## ML Baseline Training

Train the first baseline win-probability model inside the virtual environment:

```bash
python scripts/train_win_model.py
```

The training script:

- reads official NBA team-game rows from PostgreSQL
- builds one modeling row per completed matchup
- creates pre-game rolling 10-game form features for home and away teams
- splits train/test chronologically to avoid future-data leakage
- trains a logistic regression classifier
- saves model artifacts under `models/`

Current local baseline metrics:

```text
Accuracy: 0.6514
ROC-AUC: 0.7286
Log loss: 0.6098
Training rows: 2,096
Test rows: 525
```

Saved artifacts:

- `models/win_probability_model.joblib`
- `models/win_probability_metrics.json`
- `models/training_sample.csv`

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

Built and deployed an NBA data pipeline using FastAPI, PostgreSQL, SQLAlchemy, Docker, GitHub Actions, scikit-learn, and Render. Implemented idempotent incremental ingestion from NBA data sources, scheduled daily refreshes, pipeline run tracking, analytics endpoints, baseline ML model training, and a live dashboard backed by real NBA game data.

Resume bullets:

- Built a deployed NBA analytics pipeline with FastAPI, PostgreSQL, SQLAlchemy, Docker, Render, and GitHub Actions.
- Implemented idempotent incremental ingestion, scheduled refreshes, pipeline run tracking, and data quality endpoints.
- Trained and served a scikit-learn logistic regression model for matchup win probability using rolling team-form features.
- Designed API endpoints and a live dashboard for analytics, ingestion health, and model-backed predictions.

## Future Improvements

- Add data quality checks for row counts, nulls, and duplicate keys
- Add a richer frontend dashboard with interactive charts
- Add model monitoring and prediction history storage
- Expand CI to include linting and deployment smoke tests
