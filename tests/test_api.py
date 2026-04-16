from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import router
from app.db.database import Base, get_db
from app.db.models import Game, ModelPrediction, PipelineRun


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def add_game(
    db,
    *,
    game_id,
    game_date,
    season="22025",
    team_id,
    team,
    opponent,
    matchup,
    wl,
    points,
    rebounds=42,
    assists=25,
    fg_pct=0.47,
    fg3_pct=0.36,
):
    db.add(
        Game(
            game_id=game_id,
            game_date=game_date,
            season=season,
            team_id=team_id,
            team=team,
            opponent_id=0,
            opponent=opponent,
            matchup=matchup,
            wl=wl,
            points=points,
            rebounds=rebounds,
            assists=assists,
            fg_pct=fg_pct,
            fg3_pct=fg3_pct,
            ft_pct=0.78,
        )
    )


def seed_data():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        teams = [
            ("001", "2026-04-10", 1610612743, "Denver Nuggets", "LAL", "DEN vs. LAL", "W", 130, 0.39),
            ("002", "2026-04-09", 1610612759, "San Antonio Spurs", "DAL", "SAS vs. DAL", "W", 126, 0.38),
            ("003", "2026-04-08", 1610612739, "Cleveland Cavaliers", "BOS", "CLE vs. BOS", "L", 118, 0.37),
            ("004", "2026-04-07", 1610612754, "Indiana Pacers", "OKC", "IND vs. OKC", "W", 121, 0.41),
            ("005", "2026-04-06", 1610612754, "Indiana Pacers", "NYK", "IND vs. NYK", "L", 108, 0.34),
            ("006", "2026-04-05", 1610612754, "Indiana Pacers", "MIL", "IND vs. MIL", "W", 115, 0.36),
            ("007", "2026-04-07", 1610612760, "Oklahoma City Thunder", "IND", "OKC @ IND", "L", 116, 0.35),
            ("008", "2026-04-06", 1610612760, "Oklahoma City Thunder", "POR", "OKC vs. POR", "W", 122, 0.4),
            ("009", "2026-04-05", 1610612760, "Oklahoma City Thunder", "MIN", "OKC vs. MIN", "W", 119, 0.38),
            ("010", "2026-04-04", 999, "Ratiopharm Ulm", "Team T", "ULM vs. T", "W", 150, 0.62),
        ]
        for row in teams:
            game_id, game_date, team_id, team, opponent, matchup, wl, points, fg3_pct = row
            add_game(
                db,
                game_id=game_id,
                game_date=game_date,
                team_id=team_id,
                team=team,
                opponent=opponent,
                matchup=matchup,
                wl=wl,
                points=points,
                fg3_pct=fg3_pct,
            )

        add_game(
            db,
            game_id="011",
            game_date="2025-04-10",
            season="22024",
            team_id=1610612743,
            team="Denver Nuggets",
            opponent="LAL",
            matchup="DEN vs. LAL",
            wl="W",
            points=140,
        )
        db.add(
            PipelineRun(
                pipeline_name="nba_games",
                season="22025",
                mode="full_refresh",
                rows_fetched=10,
                rows_inserted=10,
                rows_skipped=0,
                status="success",
                completed_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()


def setup_function():
    seed_data()


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_games_can_filter_to_current_season():
    response = client.get("/games?limit=20&season=2025-26")

    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert {row["season"] for row in rows} == {"22025"}


def test_team_rankings_exclude_non_nba_event_teams():
    response = client.get("/analytics/team-rankings?metric=fg3_pct&limit=10&season=2025-26")

    assert response.status_code == 200
    teams = [row["team"] for row in response.json()]
    assert "Ratiopharm Ulm" not in teams
    assert "Indiana Pacers" in teams


def test_data_quality_reports_non_nba_event_teams():
    response = client.get("/data-quality/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["status"] == "warning"
    assert summary["latest_season"] == "2025-26"
    assert "Ratiopharm Ulm" in summary["non_nba_or_event_teams"]


def test_matchup_prediction_returns_ml_result():
    response = client.get(
        "/predictions/matchup?team_a=Indiana%20Pacers&team_b=Oklahoma%20City%20Thunder&last_n=3"
    )

    assert response.status_code == 200
    prediction = response.json()
    assert prediction["model_type"] == "logistic_regression"
    assert prediction["last_n_games"] == 3
    assert set(prediction["win_probability"]) == {"Indiana Pacers", "Oklahoma City Thunder"}
    assert "training_metrics" in prediction
    assert "feature_inputs" in prediction
    assert "prediction_id" in prediction

    db = TestingSessionLocal()
    try:
        saved_prediction = db.query(ModelPrediction).filter_by(id=prediction["prediction_id"]).first()
        assert saved_prediction is not None
        assert saved_prediction.model_name == "logistic_regression"
    finally:
        db.close()


def test_prediction_history_returns_saved_predictions():
    client.get(
        "/predictions/matchup?team_a=Indiana%20Pacers&team_b=Oklahoma%20City%20Thunder&last_n=3"
    )

    response = client.get("/predictions/history?limit=5")

    assert response.status_code == 200
    history = response.json()
    assert history
    assert history[0]["model_name"] == "logistic_regression"
    assert history[0]["team_a"] == "Indiana Pacers"
    assert history[0]["team_b"] == "Oklahoma City Thunder"


def test_dashboard_renders_latest_season_view_without_non_nba_teams():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "NBA Team Dashboard" in response.text
    assert "Live Database Analytics | 2025-26" in response.text
    assert "Ratiopharm Ulm" not in response.text


def test_admin_ingestion_endpoint_starts_background_job(monkeypatch):
    calls = []

    def fake_ingest_games(season, full_refresh=False, source="stats"):
        calls.append({"season": season, "full_refresh": full_refresh, "source": source})
        return {
            "season": season,
            "mode": "incremental",
            "rows_fetched": 0,
            "rows_inserted": 0,
            "rows_skipped": 0,
            "status": "success",
        }

    monkeypatch.setattr("ingest_games.ingest_games", fake_ingest_games)

    response = client.post("/admin/ingest?season=2025-26")

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["trigger"] == "render_api"
    assert calls == [{"season": "2025-26", "full_refresh": False, "source": "live"}]
