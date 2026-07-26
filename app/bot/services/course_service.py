from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.lesson_progress import LessonProgress

# from app.models.payment import Payment

from app.models.purchase import Purchase

from app.models.review import Review



def get_all_courses() -> list[Course]:
    db: Session = SessionLocal()

    try:
        return (
            db.query(Course)
            .order_by(Course.position.asc(), Course.id.asc())
            .all()
        )
    finally:
        db.close()


def get_course_by_id(course_id: int) -> Course | None:
    db: Session = SessionLocal()

    try:
        return (
            db.query(Course)
            .filter(Course.id == course_id)
            .first()
        )
    finally:
        db.close()


def create_course_with_lessons(
    title: str,
    price: int,
    lesson_titles: list[str],
) -> Course | None:
    db: Session = SessionLocal()

    try:
        last_course = (
            db.query(Course)
            .order_by(Course.position.desc())
            .first()
        )

        next_course_position = (
            last_course.position + 1
            if last_course is not None
            else 1
        )

        course = Course(
            title=title,
            price=price,
            is_active=True,
            is_visible=True,
            is_free=False,
            position=next_course_position,
        )

        db.add(course)
        db.flush()

        for lesson_position, lesson_title in enumerate(
            lesson_titles,
            start=1,
        ):
            lesson = Lesson(
                course_id=course.id,
                title=lesson_title,
                description=None,
                video_file_id=None,
                pdf_file_id=None,
                position=lesson_position,
                is_active=True,
            )

            db.add(lesson)

        db.commit()
        db.refresh(course)

        return course

    except Exception:
        db.rollback()
        return None

    finally:
        db.close()


def update_course_price(
    course_id: int,
    price: int,
) -> bool:
    db: Session = SessionLocal()

    try:
        course = (
            db.query(Course)
            .filter(Course.id == course_id)
            .first()
        )

        if course is None:
            return False

        course.price = price

        db.commit()

        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()
def delete_lesson(
    lesson_id: int,
) -> tuple[bool, int | None]:
    db: Session = SessionLocal()

    try:
        lesson = (
            db.query(Lesson)
            .filter(Lesson.id == lesson_id)
            .first()
        )

        if lesson is None:
            return False, None

        course_id = lesson.course_id

        # Удаляем прогресс учеников по этому уроку
        (
            db.query(LessonProgress)
            .filter(
                LessonProgress.lesson_id == lesson_id
            )
            .delete(synchronize_session=False)
        )

        db.delete(lesson)
        db.flush()

        # Перенумеровываем оставшиеся уроки курса
        remaining_lessons = (
            db.query(Lesson)
            .filter(Lesson.course_id == course_id)
            .order_by(
                Lesson.position.asc(),
                Lesson.id.asc(),
            )
            .all()
        )

        for new_position, remaining_lesson in enumerate(
            remaining_lessons,
            start=1,
        ):
            remaining_lesson.position = new_position

        db.commit()

        return True, course_id

    except Exception:
        db.rollback()
        return False, None

    finally:
        db.close()

def delete_course(
    course_id: int,
) -> bool:
    db: Session = SessionLocal()

    try:
        course = (
            db.query(Course)
            .filter(Course.id == course_id)
            .first()
        )

        if course is None:
            return False

        lesson_ids = [
            row[0]
            for row in (
                db.query(Lesson.id)
                .filter(Lesson.course_id == course_id)
                .all()
            )
        ]

        if lesson_ids:
            (
                db.query(LessonProgress)
                .filter(
                    LessonProgress.lesson_id.in_(
                        lesson_ids
                    )
                )
                .delete(synchronize_session=False)
            )

        (
            db.query(Review)
            .filter(Review.course_id == course_id)
            .delete(synchronize_session=False)
        )

        # (
        #     db.query(Payment)
        #     .filter(Payment.course_id == course_id)
        #     .delete(synchronize_session=False)
        # )

        (
            db.query(Purchase)
            .filter(Purchase.course_id == course_id)
            .delete(synchronize_session=False)
        )

        (
            db.query(Lesson)
            .filter(Lesson.course_id == course_id)
            .delete(synchronize_session=False)
        )

        db.delete(course)
        db.flush()

        # Перенумеровываем оставшиеся курсы
        remaining_courses = (
            db.query(Course)
            .order_by(
                Course.position.asc(),
                Course.id.asc(),
            )
            .all()
        )

        for new_position, remaining_course in enumerate(
            remaining_courses,
            start=1,
        ):
            remaining_course.position = new_position

        db.commit()

        return True

    except Exception:
        db.rollback()
        return False

    finally:
        db.close()



