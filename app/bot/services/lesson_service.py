from app.database.database import SessionLocal
from app.models.lesson import Lesson


def get_all_lessons():
    db = SessionLocal()

    try:
        return db.query(Lesson).order_by(Lesson.position).all()
    finally:
        db.close()
