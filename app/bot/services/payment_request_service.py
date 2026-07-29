from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.payment_request import PaymentRequest


FINAL_STATUSES = {"paid", "rejected", "cancelled"}


def create_payment_request(user_id: int, course_id: int, amount: int, payment_method: str) -> PaymentRequest | None:
    db: Session = SessionLocal()
    try:
        existing = (
            db.query(PaymentRequest)
            .filter(
                PaymentRequest.user_id == user_id,
                PaymentRequest.course_id == course_id,
                PaymentRequest.status.in_(["pending", "submitted"]),
            )
            .order_by(PaymentRequest.id.desc())
            .first()
        )
        if existing is not None:
            existing.amount = amount
            existing.payment_method = payment_method
            db.commit()
            db.refresh(existing)
            return existing

        request = PaymentRequest(
            user_id=user_id,
            course_id=course_id,
            amount=amount,
            payment_method=payment_method,
            status="pending",
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def get_payment_request(request_id: int) -> PaymentRequest | None:
    db: Session = SessionLocal()
    try:
        return db.query(PaymentRequest).filter(PaymentRequest.id == request_id).first()
    finally:
        db.close()


def submit_receipt(request_id: int, file_id: str, file_type: str) -> PaymentRequest | None:
    db: Session = SessionLocal()
    try:
        request = db.query(PaymentRequest).filter(PaymentRequest.id == request_id).first()
        if request is None or request.status in FINAL_STATUSES:
            return None
        request.receipt_file_id = file_id
        request.receipt_file_type = file_type
        request.status = "submitted"
        request.submitted_at = func.now()
        db.commit()
        db.refresh(request)
        return request
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def get_payment_requests(status: str | None = None, limit: int = 50) -> list[PaymentRequest]:
    db: Session = SessionLocal()
    try:
        query = db.query(PaymentRequest)
        if status is not None:
            query = query.filter(PaymentRequest.status == status)
        return query.order_by(PaymentRequest.id.desc()).limit(limit).all()
    finally:
        db.close()


def count_submitted_payment_requests() -> int:
    db: Session = SessionLocal()
    try:
        return db.query(PaymentRequest).filter(PaymentRequest.status == "submitted").count()
    finally:
        db.close()


def confirm_payment_request(request_id: int, admin_user_id: int) -> PaymentRequest | None:
    db: Session = SessionLocal()
    try:
        request = db.query(PaymentRequest).filter(PaymentRequest.id == request_id).first()
        if request is None or request.status != "submitted":
            return None
        request.status = "paid"
        request.confirmed_at = func.now()
        request.confirmed_by = admin_user_id
        db.commit()
        db.refresh(request)
        return request
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def reject_payment_request(request_id: int, admin_user_id: int) -> PaymentRequest | None:
    db: Session = SessionLocal()
    try:
        request = db.query(PaymentRequest).filter(PaymentRequest.id == request_id).first()
        if request is None or request.status not in {"pending", "submitted"}:
            return None
        request.status = "rejected"
        request.confirmed_at = func.now()
        request.confirmed_by = admin_user_id
        db.commit()
        db.refresh(request)
        return request
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def get_payment_totals() -> dict:
    db: Session = SessionLocal()
    try:
        paid_sales = db.query(PaymentRequest).filter(PaymentRequest.status == "paid").count()
        income = (
            db.query(func.coalesce(func.sum(PaymentRequest.amount), 0))
            .filter(PaymentRequest.status == "paid")
            .scalar()
        )
        submitted = db.query(PaymentRequest).filter(PaymentRequest.status == "submitted").count()
        pending = db.query(PaymentRequest).filter(PaymentRequest.status == "pending").count()
        return {
            "paid_sales": paid_sales,
            "income": int(income or 0),
            "submitted": submitted,
            "pending": pending,
        }
    finally:
        db.close()
