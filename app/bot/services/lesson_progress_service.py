from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.lesson_progress import LessonProgress
from app.models.user import User


def get_completed_lesson_ids(
    user_id: int,
    course_id: int,
) -> set[int]:
    db: Session = SessionLocal()

    try:
        rows = (
            db.query(LessonProgress.lesson_id)
            .join(
                Lesson,
                Lesson.id == LessonProgress.lesson_id,
            )
            .filter(
                LessonProgress.user_id == user_id,
                LessonProgress.completed.is_(True),
                Lesson.course_id == course_id,
            )
            .all()
        )

        return {row[0] for row in rows}

    finally:
        db.close()


def is_lesson_completed(
    user_id: int,
    lesson_id: int,
) -> bool:
    db: Session = SessionLocal()

    try:
        progress = (
            db.query(LessonProgress)
            .filter(
                LessonProgress.user_id == user_id,
                LessonProgress.lesson_id == lesson_id,
                LessonProgress.completed.is_(True),
            )
            .first()
        )

        return progress is not None

    finally:
        db.close()


def mark_lesson_completed(
    user_id: int,
    lesson_id: int,
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

        progress = (
            db.query(LessonProgress)
            .filter(
                LessonProgress.user_id == user_id,
                LessonProgress.lesson_id == lesson_id,
            )
            .first()
        )

        if progress is None:
            progress = LessonProgress(
                user_id=user_id,
                lesson_id=lesson_id,
                completed=True,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(progress)
        else:
            progress.completed = True

            if progress.completed_at is None:
                progress.completed_at = datetime.now(timezone.utc)

        db.commit()
        return True

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_next_available_lesson(
    user_id: int,
    course_id: int,
):
    db: Session = SessionLocal()

    try:
        course_lessons = (
            db.query(Lesson)
            .filter(
                Lesson.course_id == course_id,
                Lesson.is_active.is_(True),
            )
            .order_by(Lesson.position)
            .all()
        )

        completed_ids = {
            row[0]
            for row in (
                db.query(LessonProgress.lesson_id)
                .join(
                    Lesson,
                    Lesson.id == LessonProgress.lesson_id,
                )
                .filter(
                    LessonProgress.user_id == user_id,
                    LessonProgress.completed.is_(True),
                    Lesson.course_id == course_id,
                )
                .all()
            )
        }

        for lesson in course_lessons:
            if lesson.id not in completed_ids:
                return lesson

        return None

    finally:
        db.close()


def is_lesson_available(
    user_id: int,
    lesson_id: int,
) -> bool:
    db: Session = SessionLocal()

    try:
        lesson = (
            db.query(Lesson)
            .filter(
                Lesson.id == lesson_id,
                Lesson.is_active.is_(True),
            )
            .first()
        )

        if lesson is None:
            return False

        previous_lessons = (
            db.query(Lesson)
            .filter(
                Lesson.course_id == lesson.course_id,
                Lesson.position < lesson.position,
                Lesson.is_active.is_(True),
            )
            .all()
        )

        if not previous_lessons:
            return True

        previous_ids = {
            previous_lesson.id
            for previous_lesson in previous_lessons
        }

        completed_ids = {
            row[0]
            for row in (
                db.query(LessonProgress.lesson_id)
                .filter(
                    LessonProgress.user_id == user_id,
                    LessonProgress.lesson_id.in_(previous_ids),
                    LessonProgress.completed.is_(True),
                )
                .all()
            )
        }

        return previous_ids.issubset(completed_ids)

    finally:
        db.close()


def get_course_progress(
    user_id: int,
    course_id: int,
) -> dict:
    db: Session = SessionLocal()

    try:
        total_lessons = (
            db.query(Lesson)
            .filter(
                Lesson.course_id == course_id,
                Lesson.is_active.is_(True),
            )
            .count()
        )

        completed_lessons = (
            db.query(LessonProgress)
            .join(
                Lesson,
                Lesson.id == LessonProgress.lesson_id,
            )
            .filter(
                LessonProgress.user_id == user_id,
                LessonProgress.completed.is_(True),
                Lesson.course_id == course_id,
                Lesson.is_active.is_(True),
            )
            .count()
        )

        percent = (
            int(completed_lessons / total_lessons * 100)
            if total_lessons
            else 0
        )

        return {
            "completed": completed_lessons,
            "total": total_lessons,
            "percent": percent,
        }

    finally:
        db.close()