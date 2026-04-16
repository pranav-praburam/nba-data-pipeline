from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.sql import func
from app.db.database import Base

class Game(Base):
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
    wl = Column(String, nullable=True)

    points = Column(Integer, nullable=False)
    rebounds = Column(Integer, nullable=True)
    assists = Column(Integer, nullable=True)
    fg_pct = Column(Float, nullable=True)
    fg3_pct = Column(Float, nullable=True)
    ft_pct = Column(Float, nullable=True)


class PipelineRun(Base):
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
