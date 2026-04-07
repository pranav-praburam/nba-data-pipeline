from sqlalchemy import Column, Integer, String
from app.db.database import Base

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    team = Column(String, nullable=False)
    opponent = Column(String, nullable=False)
    points = Column(Integer, nullable=False)