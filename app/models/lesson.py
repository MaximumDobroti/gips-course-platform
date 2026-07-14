from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text

from app.database.database import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True)

    course_id = Column(
        Integer,
        ForeignKey("courses.id"),
        nullable=False,
    )

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    video_file_id = Column(String, nullable=True)
    pdf_file_id = Column(String, nullable=True)

    position = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)