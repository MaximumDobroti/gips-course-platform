from sqlalchemy import Boolean, Column, Integer, String, Text

from app.database.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)

    title = Column(String, nullable=False)
    subtitle = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    price = Column(Integer, nullable=False, default=750)

    cover_url = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    is_visible = Column(Boolean, default=True)
    is_free = Column(Boolean, default=False)

    position = Column(Integer, nullable=False, default=1)