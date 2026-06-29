import asyncio
import os

from app.bot.services.purchase_service import user_has_active_course
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


def get_user_from_telegram(telegram_user):
    return get_or_create_user(
        telegram_id=telegram_user.id,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        username=telegram_user.username,
    )


def build_progress_bar(current_lesson: int, total_lessons: int) -> str:
    completed = max(current_lesson - 1, 0)
    filled = min(completed, total_lessons)
    empty = max(total_lessons - filled, 0)

    return "🟩" * filled + "⬜" * empty


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="📚 Начать обучение", callback_data="start_learning")
    kb.button(text="👤 Мой профиль", callback_data="profile")
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


def lesson_keyboard(lesson_position: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Урок пройден", callback_data=f"complete:{lesson_position}")
    kb.button(text="📚 Все уроки", callback_data="lessons")
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


@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user is None:
        return

    get_user_from_telegram(message.from_user)

    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Курс: «Монтаж гипсокартона с нуля»",
        reply_markup=main_menu(),
    )

@dp.callback_query(F.data == "start_learning")
async def start_learning(callback: CallbackQuery):
    user_id = callback.from_user.id

    user = get_or_create_user(
        telegram_id=user_id,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name,
        username=callback.from_user.username,
    )

    if not user_has_active_course(user.id, 1):
        await safe_edit(
            callback,
            "🔒 У вас пока нет доступа к этому курсу.\n\n"
            "После оплаты курс станет доступен.",
            reply_markup=main_menu(),
        )
        return

    lesson = lessons[user.current_lesson - 1]

    await send_lesson(callback, lesson)

@dp.callback_query(F.data == "lessons")
async def show_lessons(callback: CallbackQuery):
    user = get_user_from_telegram(callback.from_user)
    current_lesson = user.current_lesson

    await safe_edit(
        callback,
        "📚 Все уроки курса:\n\nВыберите урок:",
        reply_markup=lessons_list_keyboard(lessons, current_lesson),
    )


@dp.callback_query(F.data.startswith("open_lesson:"))
async def open_lesson(callback: CallbackQuery):
    user = get_user_from_telegram(callback.from_user)
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
    if callback.data is None:
        return

    user = get_user_from_telegram(callback.from_user)

    lesson_position = int(callback.data.split(":")[1])
    current_lesson = user.current_lesson

    if lesson_position < current_lesson:
        await callback.answer(
            "✅ Этот урок уже пройден. Вы можете пересмотреть его в любое время.",
            show_alert=True,
        )
        return

    if lesson_position == current_lesson and current_lesson < len(lessons):
        update_current_lesson(user.telegram_id, current_lesson + 1)
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
    user = get_user_from_telegram(callback.from_user)

    total_lessons = len(lessons)
    completed_lessons = max(user.current_lesson - 1, 0)
    progress_percent = int((completed_lessons / total_lessons) * 100) if total_lessons else 0
    progress_bar = build_progress_bar(user.current_lesson, total_lessons)

    full_name = " ".join(
        part for part in [user.first_name, user.last_name] if part
    )

    username = f"@{user.username}" if user.username else "Username не указан"

    await safe_edit(
        callback,
        f"👤 Особистий кабінет\n\n"
        f"Вітаємо, {user.first_name or 'учню'} 👋\n"
        f"{username}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 Ваш прогрес\n\n"
        f"📚 Придбано курсів: 1\n"
        f"🎓 Завершено уроків: {completed_lessons}\n"
        f"⭐ Загальний прогрес: {progress_percent}%\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 КУРС 1\n\n"
        f"Монтаж гіпсокартону з нуля\n\n"
        f"{progress_bar} {progress_percent}%\n\n"
        f"✔ {completed_lessons} із {total_lessons} уроків\n"
        f"▶ Поточний урок: {min(user.current_lesson, total_lessons)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔒 КУРС 2\n\n"
        f"У розробці\n"
        f"🚧 Незабаром\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔒 КУРС 3\n\n"
        f"У розробці\n"
        f"🚧 Незабаром",
        reply_markup=main_menu(),
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())