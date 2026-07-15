from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.purchase import Purchase


def get_active_purchase(
    user_id: int,
    course_id: int,
) -> Purchase | None:
    db: Session = SessionLocal()

    try:
        return (
            db.query(Purchase)
            .filter(
                Purchase.user_id == user_id,
                Purchase.course_id == course_id,
                Purchase.status == "active",
            )
            .order_by(Purchase.id.desc())
            .first()
        )

    finally:
        db.close()


def user_has_active_course(
    user_id: int,
    course_id: int,
) -> bool:
    return (
        get_active_purchase(
            user_id=user_id,
            course_id=course_id,
        )
        is not None
    )


def grant_course_access(
    user_id: int,
    course_id: int,
) -> Purchase:
    db: Session = SessionLocal()

    try:
        purchase = (
            db.query(Purchase)
            .filter(
                Purchase.user_id == user_id,
                Purchase.course_id == course_id,
            )
            .order_by(Purchase.id.desc())
            .first()
        )

        if purchase is None:
            purchase = Purchase(
                user_id=user_id,
                course_id=course_id,
                status="active",
                expires_at=None,
            )
            db.add(purchase)
        else:
            purchase.status = "active"
            purchase.expires_at = None

        db.commit()
        db.refresh(purchase)

        return purchase

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def revoke_course_access(
    user_id: int,
    course_id: int,
) -> bool:
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

        if purchase is None:
            return False

        purchase.status = "revoked"
        db.commit()

        return True

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_purchased_courses_count(
    user_id: int,
) -> int:
    db: Session = SessionLocal()

    try:
        return (
            db.query(Purchase.course_id)
            .filter(
                Purchase.user_id == user_id,
                Purchase.status == "active",
            )
            .distinct()
            .count()
        )

    finally:
        db.close()