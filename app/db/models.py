from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from app.db.database import Base


class Game(Base):
    # One NBA game produces two rows: one team-game record for each team.
    # This shape makes team rankings, trends, and rolling model features easier.
    __tablename__ = "games"
    __table_args__ = (
        Index("ux_games_game_id_team_id", "game_id", "team_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(String, nullable=False)
    game_date = Column(String, nullable=False)
    season = Column(String, nullable=False)

    team_id = Column(Integer, nullable=False)
    team = Column(String, nullable=False)

    opponent_id = Column(Integer, nullable=False)
    opponent = Column(String, nullable=False)

    matchup = Column(String, nullable=False)
    is_home = Column(Boolean, nullable=True)
    wl = Column(String, nullable=True)

    points = Column(Integer, nullable=False)
    rebounds = Column(Integer, nullable=True)
    assists = Column(Integer, nullable=True)
    fg_pct = Column(Float, nullable=True)
    fg3_pct = Column(Float, nullable=True)
    ft_pct = Column(Float, nullable=True)


class PipelineRun(Base):
    # Audit table for ingestion observability: every scheduled/manual load records
    # what happened, even when zero new games are available.
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_name = Column(String, nullable=False)
    season = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    rows_fetched = Column(Integer, nullable=False, default=0)
    rows_inserted = Column(Integer, nullable=False, default=0)
    rows_skipped = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ModelPrediction(Base):
    # Lightweight prediction log so the app can show model usage/history and prove
    # that the ML endpoint is serving real requests, not just static JSON.
    __tablename__ = "model_predictions"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=True)
    team_a = Column(String, nullable=False)
    team_b = Column(String, nullable=False)
    favorite = Column(String, nullable=False)
    team_a_probability = Column(Float, nullable=False)
    team_b_probability = Column(Float, nullable=False)
    last_n_games = Column(Integer, nullable=False)
    feature_inputs = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ModelPick(Base):
    # Pre-game pick ledger for V2: stores model probability, sportsbook line,
    # edge, and eventual settlement so the system can evaluate realized value.
    __tablename__ = "model_picks"
    __table_args__ = (
        UniqueConstraint("game_date", "home_team", "away_team", name="uq_model_picks_game_matchup"),
    )

    id = Column(Integer, primary_key=True, index=True)
    game_date = Column(String, nullable=False)
    game_id = Column(String, nullable=True)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    model_home_win_prob = Column(Float, nullable=False)
    model_away_win_prob = Column(Float, nullable=False)
    home_moneyline = Column(Integer, nullable=True)
    away_moneyline = Column(Integer, nullable=True)
    implied_home_win_prob = Column(Float, nullable=True)
    implied_away_win_prob = Column(Float, nullable=True)
    edge = Column(Float, nullable=True)
    pick = Column(String, nullable=True)
    confidence_tier = Column(String, nullable=True)
    pick_reason = Column(Text, nullable=True)
    actual_winner = Column(String, nullable=True)
    correct = Column(Boolean, nullable=True)
    settled = Column(Boolean, nullable=False, default=False, server_default="false")
    model_version = Column(String, nullable=True)
    odds_source = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    settled_at = Column(DateTime(timezone=True), nullable=True)
