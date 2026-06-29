from sqlalchemy import Column, Integer, String

from app.database.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    price = Column(Integer, nullable=False, default=750)