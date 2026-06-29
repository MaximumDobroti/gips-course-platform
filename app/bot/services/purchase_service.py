from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.purchase import Purchase


def user_has_active_course(user_id: int, course_id: int) -> bool:
    db: Session = SessionLocal()

    try:
        purchase = (
            db.query(Purchase)
            .filter(
                Purchase.user_id == user_id,
                Purchase.course_id == course_id,
                Purchase.status == "active",
            )
            .first()
        )

        return purchase is not None

    finally:
        db.close()