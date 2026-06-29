import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from app.bot.services.lesson_service import get_all_lessons
from app.bot.services.user_service import get_or_create_user, update_current_lesson

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if BOT_TOKEN is None:
    raise RuntimeError("BOT_TOKEN is not set in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

lessons = get_all_lessons()


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Начать обучение", callback_data="start_learning")
    kb.button(text="👤 Мой профиль", callback_data="profile")
    kb.adjust(1)
    return kb.as_markup()


def lesson_keyboard(lesson_position: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Урок пройден", callback_data=f"complete:{lesson_position}")
    kb.button(text="📚 Все уроки", callback_data="lessons")
    kb.adjust(1)
    return kb.as_markup()

def lesson_only_keyboard(lesson_position: int):

    kb = InlineKeyboardBuilder()

    kb.button(text="✅ Урок пройден", callback_data=f"complete:{lesson_position}")

    kb.adjust(1)

    return kb.as_markup()
def navigation_keyboard():

    kb = InlineKeyboardBuilder()

    kb.button(text="📚 Все уроки", callback_data="lessons")

    kb.button(text="👤 Мой профиль", callback_data="profile")

    kb.adjust(1)

    return kb.as_markup()

def lessons_list_keyboard(lessons, current_lesson: int):
    kb = InlineKeyboardBuilder()

    for lesson in lessons:
        if lesson.position <= current_lesson:
            text = f"✅ {lesson.title}" if lesson.position < current_lesson else f"▶️ {lesson.title}"
            callback_data = f"open_lesson:{lesson.position}"
        else:
            text = f"🔒 {lesson.title}"
            callback_data = f"locked_lesson:{lesson.position}"

        kb.button(text=text, callback_data=callback_data)

    kb.button(text="👤 Мой профиль", callback_data="profile")
    kb.adjust(1)
    return kb.as_markup()


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


@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user is None:
        return

    user_id = message.from_user.id
    get_or_create_user(user_id)

    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Курс: «Монтаж гипсокартона с нуля»",
        reply_markup=main_menu(),
    )


@dp.callback_query(F.data == "start_learning")
async def start_learning(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_or_create_user(user_id)
    current_lesson = user.current_lesson

    lesson = lessons[current_lesson - 1]
    await send_lesson(callback, lesson)


@dp.callback_query(F.data == "lessons")
async def show_lessons(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_or_create_user(user_id)
    current_lesson = user.current_lesson

    await safe_edit(
        callback,
        "📚 Все уроки курса:\n\nВыберите урок:",
        reply_markup=lessons_list_keyboard(lessons, current_lesson),
    )


@dp.callback_query(F.data.startswith("open_lesson:"))
async def open_lesson(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_or_create_user(user_id)
    current_lesson = user.current_lesson

    if callback.data is None:
        return

    lesson_position = int(callback.data.split(":")[1])

    if lesson_position > current_lesson:
        await callback.answer(
            "🔒 Этот урок пока закрыт. Сначала пройдите предыдущий.",
            show_alert=True,
        )
        return

    lesson = lessons[lesson_position - 1]

    await send_lesson(callback, lesson)


@dp.callback_query(F.data.startswith("locked_lesson:"))
async def locked_lesson(callback: CallbackQuery):
    await callback.answer(
        "🔒 Этот урок пока закрыт. Сначала пройдите предыдущий.",
        show_alert=True,
    )


@dp.callback_query(F.data.startswith("complete:"))
async def complete_lesson(callback: CallbackQuery):
    user_id = callback.from_user.id

    if callback.data is None:
        return

    lesson_position = int(callback.data.split(":")[1])

    user = get_or_create_user(user_id)
    current_lesson = user.current_lesson

    if lesson_position < current_lesson:
        await callback.answer(
            "✅ Этот урок уже пройден. Вы можете пересмотреть его в любое время.",
            show_alert=True,
        )
        return

    if lesson_position == current_lesson and current_lesson < len(lessons):
        update_current_lesson(user_id, current_lesson + 1)
        next_lesson = lessons[current_lesson]

        await callback.message.answer(
            f"🎉 Отлично! Урок {lesson_position} завершён.\n\n"
            f"Открыт следующий урок:\n\n"
            f"📚 {next_lesson.title}",
            reply_markup=lesson_keyboard(next_lesson.position),
        )
        return

    if lesson_position == len(lessons):
        await callback.message.answer(
            "🎉 Поздравляем!\n\n"
            "Вы прошли весь курс.",
            reply_markup=main_menu(),
        )
        return

    await callback.answer(
        "🔒 Этот урок пока закрыт. Сначала пройдите предыдущий.",
        show_alert=True,
    )

@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_or_create_user(user_id)
    current_lesson = user.current_lesson

    await safe_edit(
        callback,
        f"👤 Профиль\n\n"
        f"Ваш текущий урок: {current_lesson}\n"
        f"Курс: Монтаж гипсокартона с нуля",
        reply_markup=main_menu(),
    )
async def send_lesson(callback: CallbackQuery, lesson):
    if callback.message is None:
        return

    await callback.message.answer(
        f"🎥 Видео урока {lesson.position}\n\n"
        f"📚 {lesson.title}\n\n"
        "Здесь будет видеоурок и материалы.",
        reply_markup=lesson_only_keyboard(lesson.position),
    )

    await callback.message.answer(
        "Выберите дальнейшее действие:",
        reply_markup=navigation_keyboard(),
    )

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())