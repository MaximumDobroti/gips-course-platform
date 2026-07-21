from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.lesson_progress import LessonProgress
from app.models.purchase import Purchase
from app.models.review import Review
from app.models.user import User


def get_platform_statistics(course_id: int, course_price: int | None = None) -> dict:
    db: Session = SessionLocal()
    try:
        users_total = db.query(User).count()
        active_purchases = db.query(Purchase).filter(Purchase.status == "active").count()

        course = db.query(Course).filter(Course.id == course_id).first()
        effective_price = int(course_price) if course_price is not None else (int(course.price) if course else 0)
        income = active_purchases * effective_price

        lesson_ids = [row[0] for row in db.query(Lesson.id).filter(Lesson.course_id == course_id, Lesson.is_active.is_(True)).all()]
        total_lessons = len(lesson_ids)

        started = 0
        completed = 0
        average_progress = 0
        if lesson_ids and total_lessons:
            completed_by_user = (
                db.query(LessonProgress.user_id, func.count(distinct(LessonProgress.lesson_id)).label("done"))
                .filter(LessonProgress.lesson_id.in_(lesson_ids), LessonProgress.completed.is_(True))
                .group_by(LessonProgress.user_id)
                .all()
            )
            started = len(completed_by_user)
            completed = sum(1 for _, done in completed_by_user if done >= total_lessons)
            average_progress = round(sum(min(done, total_lessons) / total_lessons * 100 for _, done in completed_by_user) / started) if started else 0

        review_total = db.query(Review).filter(Review.course_id == course_id).count()
        unread_reviews = db.query(Review).filter(Review.course_id == course_id, Review.status == "new").count()
        average_rating = db.query(func.avg(Review.rating)).filter(Review.course_id == course_id).scalar()

        return {
            "users_total": users_total,
            "active_purchases": active_purchases,
            "income": income,
            "started": started,
            "completed": completed,
            "average_progress": average_progress,
            "average_rating": round(float(average_rating or 0), 1),
            "review_total": review_total,
            "unread_reviews": unread_reviews,
        }
    finally:
        db.close()

