from sqlalchemy import BigInteger, Boolean, Column, Integer, String


from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    telegram_id = Column(
        BigInteger,
        unique=True,
        nullable=False,
    )

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)

    current_lesson = Column(
        Integer,
        nullable=False,
        default=1,
    )

    is_admin = Column(
        Boolean,
        nullable=False,
        default=False,
    )
