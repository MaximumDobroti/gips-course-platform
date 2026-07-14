from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database.database import Base


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True)

    title = Column(String, nullable=False)
    text = Column(Text, nullable=False)

    image_file_id = Column(
        String,
        nullable=True,
    )

    is_published = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    published_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )