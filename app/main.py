# from fastapi import FastAPI
#
# import app.models
#
# from app.database.database import Base, engine
#
# Base.metadata.create_all(bind=engine)
#
# app = FastAPI(
#
#     title="Gips Course Platform",
#
#     description="Backend for Telegram-based course platform",
#
#     version="0.1.0",
#
# )
#
# @app.get("/")
#
# async def root():
#
#     return {
#
#         "status": "ok",
#
#         "message": "Gips Course Platform API is running",
#
#     }

from fastapi import FastAPI

from app.database.database import Base, engine

# Явные импорты нужны, чтобы модели зарегистрировались в Base.metadata.
from app.models.announcement import Announcement
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.lesson_progress import LessonProgress
from app.models.purchase import Purchase
from app.models.user import User


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Gips Course Platform",
    description="Backend for Telegram-based course platform",
    version="0.1.0",
)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Gips Course Platform API is running",
    }