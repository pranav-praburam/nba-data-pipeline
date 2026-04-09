# NBA Data Pipeline

A personal project that ingests, processes, and serves NBA data through a deployed API.

## Current Features

- FastAPI backend with modular routes
- PostgreSQL storage via SQLAlchemy
- NBA game ingestion using `nba_api`
- Idempotent game loads with incremental ingestion
- Pipeline run tracking for observability
- Analytics endpoints for team summaries, leaders, and recent trends

## Local Run

Inside the virtual environment:

```bash
source /Users/lalitha/nba-data-pipeline/venv/bin/activate
uvicorn main:app --reload
```

## Docker Run

Build the image:

```bash
docker build -t nba-data-pipeline .
```

Run the API container:

```bash
docker run --env-file .env -p 8000:8000 nba-data-pipeline
```

If your PostgreSQL database is running on your host machine, use a host-accessible connection string in `.env` for Docker deployment. On many local setups that means replacing `localhost` with `host.docker.internal` and explicitly setting the database username.

Example:

```env
DATABASE_URL=postgresql://lalitha@host.docker.internal/nba_pipeline
```

## Demo Endpoints

- `/games?limit=5`
- `/games?team=Indiana&result=W&limit=5`
- `/teams/Indiana Pacers/summary`
- `/teams/Indiana Pacers/trends?last_n=5`
- `/leaders/points`
- `/pipeline/runs`

## Deployment Direction

The project is now containerized, which makes it straightforward to deploy to platforms that support Docker-based web services. For a resume project, the cleanest next deployment path is:

1. Provision a managed PostgreSQL database
2. Deploy this FastAPI app from the `Dockerfile`
3. Set `DATABASE_URL` in the deployment platform
4. Run ingestion against the deployed database on a schedule

## Render Deploy

This repo includes a `render.yaml` Blueprint for a simple Render deployment:

- a Docker-based FastAPI web service
- a managed Render Postgres database
- automatic wiring of `DATABASE_URL` from the database to the web service

### Deploy steps

1. Push this repo to GitHub
2. Sign in to Render
3. Click `New` -> `Blueprint`
4. Connect this GitHub repo
5. Select the `main` branch
6. Review the `render.yaml` resources and click deploy

After deploy finishes, open:

- `/health`
- `/docs`
- `/games?limit=5`

### Important note

Your deployed database will start empty. After the web service is live, run ingestion against the deployed `DATABASE_URL` to populate it with NBA data.
