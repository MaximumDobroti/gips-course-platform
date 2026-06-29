from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.user import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user(telegram_id: int):
    db: Session = SessionLocal()

    try:
        return db.query(User).filter(User.telegram_id == telegram_id).first()
    finally:
        db.close()


def create_user(telegram_id: int):
    db: Session = SessionLocal()

    try:
        user = User(
            telegram_id=telegram_id,
            current_lesson=1,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    finally:
        db.close()


def get_or_create_user(telegram_id: int):
    user = get_user(telegram_id)

    if user:
        return user

    return create_user(telegram_id)


def update_current_lesson(telegram_id: int, lesson: int):
    db: Session = SessionLocal()

    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

        if user:
            user.current_lesson = lesson
            db.commit()

    finally:
        db.close()