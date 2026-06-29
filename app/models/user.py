from sqlalchemy import Column, Integer, BigInteger

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    current_lesson = Column(Integer, default=1)