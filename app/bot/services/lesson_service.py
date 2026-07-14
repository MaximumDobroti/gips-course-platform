from sqlalchemy.orm import Session

from app.database.database import SessionLocal

from app.models.course import Course

from app.models.lesson import Lesson

from sqlalchemy.orm import Session

from app.database.database import SessionLocal

from app.models.course import Course

from app.models.lesson import Lesson



def get_all_lessons():

    db: Session = SessionLocal()

    try:

        return (

            db.query(Lesson)

            .order_by(Lesson.position)

            .all()

        )

    finally:

        db.close()

def update_lesson_video(

    lesson_id: int,

    video_file_id: str,

) -> bool:

    db: Session = SessionLocal()

    try:

        lesson = (

            db.query(Lesson)

            .filter(Lesson.id == lesson_id)

            .first()

        )

        if lesson is None:

            return False

        lesson.video_file_id = video_file_id

        db.commit()

        return True

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()

def update_lesson_pdf(

    lesson_id: int,

    pdf_file_id: str,

) -> bool:

    db: Session = SessionLocal()

    try:

        lesson = (

            db.query(Lesson)

            .filter(Lesson.id == lesson_id)

            .first()

        )

        if lesson is None:

            return False

        lesson.pdf_file_id = pdf_file_id

        db.commit()

        return True

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()

def update_lesson_description(

    lesson_id: int,

    description: str,

) -> bool:

    db: Session = SessionLocal()

    try:

        lesson = (

            db.query(Lesson)

            .filter(Lesson.id == lesson_id)

            .first()

        )

        if lesson is None:

            return False

        lesson.description = description

        db.commit()

        return True

    except Exception:

        db.rollback()

        raise

    finally:

        db.close()