from sqlalchemy import Column, Integer, BigInteger, String

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    telegram_id = Column(BigInteger, unique=True, nullable=False)

    first_name = Column(String)
    last_name = Column(String)
    username = Column(String)

    current_lesson = Column(Integer, default=1)