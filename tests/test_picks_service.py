from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import Game, ModelPick
from app.db.models import PipelineRun
from app.services.odds import NormalizedOddsEvent
from app.services.picks import generate_model_picks, picks_performance_summary, settle_model_picks


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_generate_model_picks_inserts_idempotent_rows(monkeypatch):
    db = TestingSessionLocal()
    try:
        event = NormalizedOddsEvent(
            game_id="evt_1",
            commence_time="2026-05-02T00:00:00Z",
            home_team="Indiana Pacers",
            away_team="Oklahoma City Thunder",
            bookmaker="draftkings",
            odds_source="the-odds-api",
            home_moneyline=120,
            away_moneyline=-140,
            implied_home_win_prob=0.45,
            implied_away_win_prob=0.55,
        )

        def fake_predict(db_session, home, away, last_n):
            return {
                "model_type": "logistic_regression",
                "model_version": "v1",
                "last_n_games": last_n,
                "favorite": away,
                "win_probability": {home: 0.52, away: 0.48},
            }

        monkeypatch.setattr("app.services.picks.predict_matchup_win_probability", fake_predict)

        result = generate_model_picks(db, target_date="2026-05-02", odds_events=[event], edge_threshold=0.03)
        assert result["rows_inserted"] == 1
        assert result["pipeline_run_id"]

        # Second run should update the same row, not insert a duplicate.
        event.home_moneyline = 130
        result2 = generate_model_picks(db, target_date="2026-05-02", odds_events=[event], edge_threshold=0.03)
        assert result2["rows_inserted"] == 0
        assert result2["rows_updated"] == 1
        assert result2["pipeline_run_id"]

        picks = db.query(ModelPick).all()
        assert len(picks) == 1
        assert picks[0].home_moneyline == 130

        runs = db.query(PipelineRun).filter(PipelineRun.pipeline_name == "model_picks_generate").all()
        assert len(runs) == 2
    finally:
        db.close()


def test_settle_model_picks_marks_correct_winner():
    db = TestingSessionLocal()
    try:
        db.add(
            ModelPick(
                game_date="2026-04-10",
                game_id="evt_x",
                home_team="Denver Nuggets",
                away_team="Los Angeles Lakers",
                model_home_win_prob=0.6,
                model_away_win_prob=0.4,
                home_moneyline=-150,
                away_moneyline=130,
                implied_home_win_prob=0.58,
                implied_away_win_prob=0.42,
                edge=0.02,
                pick="Denver Nuggets",
                confidence_tier="low",
                pick_reason="test",
                settled=False,
                model_version="v1",
                odds_source="the-odds-api",
            )
        )
        db.commit()

        # Seed games rows for settlement matching (home/away).
        db.add(
            Game(
                game_id="nba_1",
                game_date="2026-04-10",
                season="22025",
                team_id=1,
                team="Denver Nuggets",
                opponent_id=0,
                opponent="Los Angeles Lakers",
                matchup="DEN vs. LAL",
                is_home=True,
                wl="W",
                points=120,
                rebounds=40,
                assists=25,
                fg_pct=0.47,
                fg3_pct=0.36,
                ft_pct=0.78,
            )
        )
        db.add(
            Game(
                game_id="nba_1",
                game_date="2026-04-10",
                season="22025",
                team_id=2,
                team="Los Angeles Lakers",
                opponent_id=0,
                opponent="Denver Nuggets",
                matchup="LAL @ DEN",
                is_home=False,
                wl="L",
                points=110,
                rebounds=38,
                assists=22,
                fg_pct=0.44,
                fg3_pct=0.33,
                ft_pct=0.79,
            )
        )
        db.commit()

        result = settle_model_picks(db, settle_before_date="2026-04-11")
        assert result["settled_count"] == 1
        assert result["pipeline_run_id"]

        pick = db.query(ModelPick).first()
        assert pick.settled is True
        assert pick.actual_winner == "Denver Nuggets"
        assert pick.correct is True

        run = db.query(PipelineRun).filter(PipelineRun.pipeline_name == "model_picks_settle").first()
        assert run is not None
    finally:
        db.close()


def test_picks_performance_summary_computes_accuracy_and_roi():
    db = TestingSessionLocal()
    try:
        # One correct underdog (+200 => +2.0 profit) and one incorrect favorite (-200 => -1.0 loss).
        db.add(
            ModelPick(
                game_date="2026-04-10",
                home_team="Team A",
                away_team="Team B",
                model_home_win_prob=0.55,
                model_away_win_prob=0.45,
                home_moneyline=200,
                away_moneyline=-240,
                implied_home_win_prob=0.35,
                implied_away_win_prob=0.65,
                edge=0.2,
                pick="Team A",
                confidence_tier="high",
                pick_reason="test",
                actual_winner="Team A",
                correct=True,
                settled=True,
                odds_source="the-odds-api",
            )
        )
        db.add(
            ModelPick(
                game_date="2026-04-10",
                home_team="Team C",
                away_team="Team D",
                model_home_win_prob=0.6,
                model_away_win_prob=0.4,
                home_moneyline=-200,
                away_moneyline=170,
                implied_home_win_prob=0.6,
                implied_away_win_prob=0.4,
                edge=0.05,
                pick="Team C",
                confidence_tier="low",
                pick_reason="test",
                actual_winner="Team D",
                correct=False,
                settled=True,
                odds_source="the-odds-api",
            )
        )
        db.commit()

        summary = picks_performance_summary(db)
        assert summary["total_picks"] == 2
        assert summary["settled_picks"] == 2
        assert summary["accuracy"] == 0.5
        assert summary["stake_units"] == 2
        assert summary["profit_units"] == 1.0
        assert summary["roi_per_pick"] == 0.5
        assert summary["tiers"]["high"]["accuracy"] == 1.0
        assert summary["tiers"]["low"]["accuracy"] == 0.0
    finally:
        db.close()
