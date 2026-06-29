from fastapi import FastAPI

app = FastAPI(
    title="Gips Course Platform",
    description="Backend for Telegram-based course platform",
    version="0.1.0",
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "Gips Course Platform API is running"}