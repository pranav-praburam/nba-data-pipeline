# AWS Lightsail Deployment Guide

This guide moves the project from Render's sleeping free tier to an always-on AWS Lightsail instance that should fit within a roughly `$7/month` budget.

## Recommended Lightsail Plan

- Instance: `Linux/Unix Micro-1GB with public IPv4`
- Typical monthly cost: about `$7/month`
- Why this plan: enough RAM to run both FastAPI and PostgreSQL in Docker on one machine without paying for a separate managed database

## Architecture

```text
GitHub repo
  -> Docker Compose on one Lightsail VM
     -> FastAPI container
     -> PostgreSQL container
     -> persistent Docker volume for Postgres data
```

## Files in This Repo

- `docker-compose.lightsail.yml`
- `.env.lightsail.example`
- `Dockerfile`

## Step 1: Create the Lightsail Instance

Inside AWS:

1. Open Lightsail.
2. Create an instance.
3. Choose `Linux/Unix`.
4. Choose `Ubuntu 24.04 LTS` or the current Ubuntu LTS option.
5. Choose the `$7/month` `Micro-1GB` plan.
6. Give it a name such as `nba-data-pipeline`.

Expected result:

- You see a public IPv4 address for the instance.

## Step 2: Open the Required Port

Inside the Lightsail networking tab for the instance:

1. Keep `SSH` open.
2. Add an `HTTP` rule for port `80`.

Expected result:

- Port `80` is open for the website.

## Step 3: SSH Into the Server

Outside the virtual environment, from your Mac terminal:

```bash
ssh ubuntu@YOUR_LIGHTSAIL_IP
```

Expected result:

- You reach a shell on the Lightsail server.

## Step 4: Install Docker and Docker Compose

On the Lightsail server:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

Expected result:

- Docker and Docker Compose both print version info.

## Step 5: Clone the Repo

On the Lightsail server:

```bash
git clone https://github.com/pranav-praburam/nba-data-pipeline.git
cd nba-data-pipeline
```

Expected result:

- The project files are present on the server.

## Step 6: Create the Lightsail Environment File

On the Lightsail server:

```bash
cp .env.lightsail.example .env.lightsail
nano .env.lightsail
```

Update at least:

- `POSTGRES_PASSWORD`
- `INGEST_API_KEY`
- `APP_PUBLIC_BASE_URL`
- `ALLOWED_HOSTS`

Expected result:

- `.env.lightsail` contains your real password instead of the placeholder.
- `.env.lightsail` contains a long random ingestion API key used by GitHub Actions.
- `.env.lightsail` contains the public URL or static IP used to derive the deployed host allowlist.

## Step 7: Start the App

On the Lightsail server:

```bash
docker compose --env-file .env.lightsail -f docker-compose.lightsail.yml up -d --build
```

Expected result:

- Two containers start: `nba-postgres` and `nba-api`

Verify:

```bash
docker compose --env-file .env.lightsail -f docker-compose.lightsail.yml ps
curl http://localhost/health
```

Expected result:

- `curl` returns `{"status":"ok"}`

## Step 8: Load Real NBA Data

On the Lightsail server:

```bash
docker compose --env-file .env.lightsail -f docker-compose.lightsail.yml exec api python ingest_games.py 2025-26
docker compose --env-file .env.lightsail -f docker-compose.lightsail.yml exec api python scripts/train_win_model.py
```

Expected result:

- Games are inserted into Postgres
- The trained model artifacts are refreshed using the Lightsail database data

## Step 9: Verify in the Browser

In your browser:

- `http://YOUR_LIGHTSAIL_IP/health`
- `http://YOUR_LIGHTSAIL_IP/dashboard`
- `http://YOUR_LIGHTSAIL_IP/predict`

Expected result:

- Health returns JSON status ok
- Dashboard loads
- Prediction page loads

## Step 10: Update GitHub Actions Scheduled Ingestion

Your current GitHub Actions workflow can keep working if it points to the deployed API.

Add the following GitHub repository secrets:

- `DEPLOYED_API_URL`
- `INGEST_API_KEY`

Example:

```text
DEPLOYED_API_URL=http://YOUR_LIGHTSAIL_IP
INGEST_API_KEY=your_long_random_ingestion_key
```

Expected result:

- Daily scheduled ingestion continues to hit `/admin/ingest`
- New rows keep loading without manual work

Security notes:

- Never commit `.env.lightsail` to GitHub.
- Keep `INGEST_API_KEY` only in GitHub Secrets and on the Lightsail box.
- When the public IP or domain changes, update `APP_PUBLIC_BASE_URL`, `ALLOWED_HOSTS`, and `DEPLOYED_API_URL` together before rebuilding the containers.

## Step 11: Deploy Future Code Changes

On the Lightsail server, after pushing new code to GitHub:

```bash
cd ~/nba-data-pipeline
git pull
docker compose --env-file .env.lightsail -f docker-compose.lightsail.yml up -d --build
```

Expected result:

- The latest commit is rebuilt and running

## Optional Next Upgrade

If you want a cleaner production setup later, the next step would be:

- add a domain name
- add Caddy or Nginx as a reverse proxy
- add HTTPS with Let's Encrypt
- add a small deploy script

That is optional. The setup in this guide is enough to keep the site always available for recruiter demos within budget.
