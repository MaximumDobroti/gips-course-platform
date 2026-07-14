from fastapi import FastAPI
import app.models.purchase
import app.models.lesson

import app.models.user
import app.models.announcement


import app.models.course

from app.database.database import Base, engine

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