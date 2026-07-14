from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.database import SessionLocal

from app.models.announcement import Announcement

from app.models.user import User

from app.models.purchase import Purchase

def create_announcement(

    title: str,

    text: str,

    image_file_id: str | None = None,

) -> Announcement:

    db: Session = SessionLocal()

    try:

        announcement = Announcement(

            title=title,

            text=text,

            image_file_id=image_file_id,

            is_published=False,

        )

        db.add(announcement)

        db.commit()

        db.refresh(announcement)

        return announcement

    finally:

        db.close()

def publish_announcement(

    announcement_id: int,

) -> bool:

    db: Session = SessionLocal()

    try:

        announcement = (

            db.query(Announcement)

            .filter(Announcement.id == announcement_id)

            .first()

        )

        if announcement is None:

            return False

        announcement.is_published = True

        announcement.published_at = datetime.now(timezone.utc)

        db.commit()

        return True

    finally:

        db.close()

def get_announcement(

    announcement_id: int,

):

    db: Session = SessionLocal()

    try:

        return (

            db.query(Announcement)

            .filter(Announcement.id == announcement_id)

            .first()

        )

    finally:

        db.close()

def get_published_announcements():

    db: Session = SessionLocal()

    try:

        return (

            db.query(Announcement)

            .filter(Announcement.is_published.is_(True))

            .order_by(Announcement.published_at.desc())

            .all()

        )

    finally:

        db.close()

def get_active_student_telegram_ids(

    course_id: int = 1,

) -> list[int]:

    db: Session = SessionLocal()

    try:

        rows = (

            db.query(User.telegram_id)

            .join(Purchase, Purchase.user_id == User.id)

            .filter(

                Purchase.course_id == course_id,

                Purchase.status == "active",

            )

            .distinct()

            .all()

        )

        return [row[0] for row in rows]

    finally:

        db.close()