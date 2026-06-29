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


def create_user(
    telegram_id: int,
    first_name: str | None,
    last_name: str | None,
    username: str | None,
):
    db: Session = SessionLocal()

    try:
        user = User(
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            current_lesson=1,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    finally:
        db.close()


def get_or_create_user(
    telegram_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    username: str | None = None,
):
    user = get_user(telegram_id)

    if user:

        changed = False

        db: Session = SessionLocal()

        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()

            if user.first_name != first_name:
                user.first_name = first_name
                changed = True

            if user.last_name != last_name:
                user.last_name = last_name
                changed = True

            if user.username != username:
                user.username = username
                changed = True

            if changed:
                db.commit()

            return user

        finally:
            db.close()

    return create_user(
        telegram_id,
        first_name,
        last_name,
        username,
    )


def update_current_lesson(telegram_id: int, lesson: int):
    db: Session = SessionLocal()

    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

        if user:
            user.current_lesson = lesson
            db.commit()

    finally:
        db.close()