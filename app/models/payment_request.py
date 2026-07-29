from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database.database import Base


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)

    amount = Column(Integer, nullable=False)
    payment_method = Column(String, nullable=False)  # card | iban
    status = Column(String, nullable=False, default="pending", index=True)

    receipt_file_id = Column(String, nullable=True)
    receipt_file_type = Column(String, nullable=True)  # photo | document

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
