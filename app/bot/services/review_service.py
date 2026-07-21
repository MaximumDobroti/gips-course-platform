from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.review import Review
from app.models.user import User


def get_user_review(user_id: int, course_id: int) -> Review | None:
    db: Session = SessionLocal()
    try:
        return db.query(Review).filter(Review.user_id == user_id, Review.course_id == course_id).first()
    finally:
        db.close()


def save_rating(user_id: int, course_id: int, rating: int) -> Review:
    if rating not in range(1, 6):
        raise ValueError("rating must be between 1 and 5")
    db: Session = SessionLocal()
    try:
        review = db.query(Review).filter(Review.user_id == user_id, Review.course_id == course_id).first()
        if review is None:
            review = Review(user_id=user_id, course_id=course_id, rating=rating, status="new")
            db.add(review)
        else:
            review.rating = rating
            review.status = "new"
        db.commit()
        db.refresh(review)
        return review
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_review_text(user_id: int, course_id: int, text: str) -> Review | None:
    db: Session = SessionLocal()
    try:
        review = db.query(Review).filter(Review.user_id == user_id, Review.course_id == course_id).first()
        if review is None:
            return None
        review.text = text.strip() or None
        review.status = "new"
        db.commit()
        db.refresh(review)
        return review
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_reviews(status: str | None = None, limit: int = 20):
    db: Session = SessionLocal()
    try:
        query = db.query(Review, User).join(User, User.id == Review.user_id)
        if status:
            query = query.filter(Review.status == status)
        rows = query.order_by(Review.created_at.desc()).limit(limit).all()
        return [(review, user) for review, user in rows]
    finally:
        db.close()


def mark_review_read(review_id: int) -> bool:
    db: Session = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if review is None:
            return False
        review.status = "read"
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def delete_review(review_id: int) -> bool:
    db: Session = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if review is None:
            return False
        db.delete(review)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_review_summary() -> dict:
    db: Session = SessionLocal()
    try:
        total = db.query(Review).count()
        unread = db.query(Review).filter(Review.status == "new").count()
        average = db.query(func.avg(Review.rating)).scalar()
        return {"total": total, "unread": unread, "average": round(float(average or 0), 1)}
    finally:
        db.close()
