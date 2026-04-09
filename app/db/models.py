from sqlalchemy import Column, Float, Index, Integer, String
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
