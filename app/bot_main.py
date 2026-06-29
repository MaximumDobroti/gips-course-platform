import asyncio
import os

from app.services.user_service import get_or_create_user, update_current_lesson
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiogram.exceptions import TelegramBadRequest

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if BOT_TOKEN is None:

    raise RuntimeError("BOT_TOKEN is not set in .env")

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()


lessons = [
    {"id": 1, "title": "Урок 1. Что будет в курсе"},
    {"id": 2, "title": "Урок 2. Ошибки новичков"},
    {"id": 3, "title": "Урок 3. Инструменты"},
]


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Начать обучение", callback_data="start_learning")
    kb.button(text="👤 Мой профиль", callback_data="profile")
    kb.adjust(1)
    return kb.as_markup()


def lesson_keyboard(lesson_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Урок пройден", callback_data=f"complete:{lesson_id}")
    kb.button(text="📚 Все уроки", callback_data="lessons")
    kb.adjust(1)
    return kb.as_markup()


@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user is None:
        return

    user_id = message.from_user.id

    get_or_create_user(user_id)

    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Курс: «Монтаж гипсокартона с нуля»",
        reply_markup=main_menu()
    )


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None):

    if callback.message is None:

        return

    try:

        await callback.message.edit_text(text, reply_markup=reply_markup)

    except TelegramBadRequest as e:

        if "message is not modified" in str(e):

            await callback.answer("Уже открыто")

        else:

            raise

@dp.callback_query(F.data == "start_learning")

async def start_learning(callback: CallbackQuery):

    user_id = callback.from_user.id

    user = get_or_create_user(user_id)

    current_lesson = user.current_lesson

    lesson = lessons[current_lesson - 1]

    await safe_edit(

        callback,

        f"📚 {lesson['title']}\n\n"

        "Здесь будет видеоурок и материалы.",

        reply_markup=lesson_keyboard(lesson["id"])

    )

@dp.callback_query(F.data == "lessons")
async def show_lessons(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_or_create_user(user_id)

    current_lesson = user.current_lesson

    text = "📚 Все уроки:\n\n"

    for lesson in lessons:
        if lesson["id"] < current_lesson:
            status = "✅"
        elif lesson["id"] == current_lesson:
            status = "▶️"
        else:
            status = "🔒"

        text += f"{status} {lesson['title']}\n"

    await callback.message.edit_text(text, reply_markup=main_menu())


@dp.callback_query(F.data.startswith("complete:"))
async def complete_lesson(callback: CallbackQuery):
    user_id = callback.from_user.id

    if callback.data is None:
        return

    lesson_id = int(callback.data.split(":")[1])

    user = get_or_create_user(user_id)
    current_lesson = user.current_lesson

    if lesson_id == current_lesson and current_lesson < len(lessons):
        update_current_lesson(user_id, current_lesson + 1)
        next_lesson = lessons[current_lesson]

        await callback.message.edit_text(
            f"✅ Урок {lesson_id} завершён!\n\n"
            f"Открыт следующий урок:\n\n"
            f"📚 {next_lesson['title']}",
            reply_markup=lesson_keyboard(next_lesson["id"])
        )

    elif lesson_id == len(lessons):
        await callback.message.edit_text(
            "🎉 Поздравляем!\n\n"
            "Вы прошли весь курс.",
            reply_markup=main_menu()
        )
    else:
        await callback.answer("Этот урок пока недоступен", show_alert=True)

@dp.callback_query(F.data == "profile")

async def profile(callback: CallbackQuery):

    user_id = callback.from_user.id

    user = get_or_create_user(user_id)

    current_lesson = user.current_lesson

    try:

        await callback.message.edit_text(

            f"👤 Профиль\n\n"

            f"Ваш текущий урок: {current_lesson}\n"

            f"Курс: Монтаж гипсокартона с нуля",

            reply_markup=main_menu()

        )

    except TelegramBadRequest:

        await callback.answer("Вы уже в профиле")
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())