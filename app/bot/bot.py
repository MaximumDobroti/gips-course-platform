import asyncio
import os
from typing import Any

import app.models

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from app.bot.services.lesson_service import (
    get_all_lessons,
    update_lesson_description,
    update_lesson_pdf,
    update_lesson_video,
)
from app.bot.services.purchase_service import user_has_active_course
from app.bot.services.user_service import (
    get_or_create_user,
    update_current_lesson,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if BOT_TOKEN is None:
    raise RuntimeError("BOT_TOKEN is not set in .env")

COURSE_ID = 1
COURSE_TITLE = "Монтаж гипсокартона с нуля"
COURSE_PRICE = 750

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

lessons = get_all_lessons()


# =========================================================
# FSM-СОСТОЯНИЯ АДМИНИСТРАТОРА
# =========================================================

class AdminLessonEdit(StatesGroup):
    waiting_for_video = State()
    waiting_for_pdf = State()
    waiting_for_description = State()


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def refresh_lessons() -> None:
    global lessons
    lessons = get_all_lessons()


def get_user_from_telegram(telegram_user: Any):
    return get_or_create_user(
        telegram_id=telegram_user.id,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        username=telegram_user.username,
    )


def get_lesson_by_id(lesson_id: int):
    return next(
        (lesson for lesson in lessons if lesson.id == lesson_id),
        None,
    )


def get_lesson_by_position(position: int):
    return next(
        (lesson for lesson in lessons if lesson.position == position),
        None,
    )


def build_progress_bar(
    current_lesson: int,
    total_lessons: int,
) -> str:
    completed = min(
        max(current_lesson - 1, 0),
        total_lessons,
    )

    filled = completed
    empty = max(total_lessons - filled, 0)

    return "🟩" * filled + "⬜" * empty


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as error:
        if "message is not modified" in str(error):
            await callback.answer("Уже открыто")
        else:
            raise


async def check_admin(callback: CallbackQuery):
    user = get_user_from_telegram(callback.from_user)

    if not user.is_admin:
        await callback.answer(
            "⛔ У вас нет доступа к админ-панели.",
            show_alert=True,
        )
        return None

    return user


async def check_course_access(callback: CallbackQuery):
    user = get_user_from_telegram(callback.from_user)

    if not user_has_active_course(user.id, COURSE_ID):
        await callback.answer(
            "🔒 У вас нет активного доступа к этому курсу.",
            show_alert=True,
        )
        return None

    return user


# =========================================================
# КЛАВИАТУРЫ УЧЕНИКА
# =========================================================

def main_menu(is_admin: bool = False):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="📚 Начать обучение",
        callback_data="start_learning",
    )
    keyboard.button(
        text="👤 Мой профиль",
        callback_data="profile",
    )

    if is_admin:
        keyboard.button(
            text="👨‍💼 Админ-панель",
            callback_data="admin_panel",
        )

    keyboard.adjust(1)
    return keyboard.as_markup()


def lesson_only_keyboard(lesson_position: int):
    keyboard = InlineKeyboardBuilder()

    if lesson_position < len(lessons):
        button_text = "➡️ Перейти до наступного уроку"
    else:
        button_text = "🏁 Завершити курс"

    keyboard.button(
        text=button_text,
        callback_data=f"complete:{lesson_position}",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def navigation_keyboard():
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="📚 Все уроки",
        callback_data="lessons",
    )
    keyboard.button(
        text="👤 Мой профиль",
        callback_data="profile",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def lesson_keyboard(lesson_position: int):
    keyboard = InlineKeyboardBuilder()

    if lesson_position < len(lessons):
        button_text = "➡️ Перейти до наступного уроку"
    else:
        button_text = "🏁 Завершити курс"

    keyboard.button(
        text=button_text,
        callback_data=f"complete:{lesson_position}",
    )
    keyboard.button(
        text="📚 Все уроки",
        callback_data="lessons",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def lessons_list_keyboard(
    course_lessons,
    current_lesson: int,
):
    keyboard = InlineKeyboardBuilder()

    for lesson in course_lessons:
        if lesson.position < current_lesson:
            text = f"✅ {lesson.title}"
            callback_data = f"open_lesson:{lesson.position}"

        elif lesson.position == current_lesson:
            text = f"▶️ {lesson.title}"
            callback_data = f"open_lesson:{lesson.position}"

        else:
            text = f"🔒 {lesson.title}"
            callback_data = f"locked_lesson:{lesson.position}"

        keyboard.button(
            text=text,
            callback_data=callback_data,
        )

    keyboard.button(
        text="👤 Мой профиль",
        callback_data="profile",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


# =========================================================
# КЛАВИАТУРЫ АДМИНИСТРАТОРА
# =========================================================

def admin_menu():
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="📚 Курсы",
        callback_data="admin_courses",
    )
    keyboard.button(
        text="📢 Новости",
        callback_data="admin_news",
    )
    keyboard.button(
        text="👥 Ученики",
        callback_data="admin_students",
    )
    keyboard.button(
        text="📊 Статистика",
        callback_data="admin_statistics",
    )
    keyboard.button(
        text="⬅️ Личный кабинет",
        callback_data="profile",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def admin_courses_keyboard():
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🎓 Курс 1. Монтаж гипсокартона",
        callback_data=f"admin_course:{COURSE_ID}",
    )
    keyboard.button(
        text="⬅️ Назад",
        callback_data="admin_panel",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def admin_course_keyboard(course_id: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="📖 Уроки",
        callback_data=f"admin_course_lessons:{course_id}",
    )
    keyboard.button(
        text="⬅️ К курсам",
        callback_data="admin_courses",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def admin_lessons_keyboard(
    course_lessons,
    course_id: int,
):
    keyboard = InlineKeyboardBuilder()

    for lesson in course_lessons:
        video_icon = "🎥" if lesson.video_file_id else "⚪️"
        pdf_icon = "📄" if lesson.pdf_file_id else "⚪️"

        keyboard.button(
            text=(
                f"{lesson.position}. {lesson.title} "
                f"{video_icon}{pdf_icon}"
            ),
            callback_data=f"admin_lesson:{lesson.id}",
        )

    keyboard.button(
        text="⬅️ Назад",
        callback_data=f"admin_course:{course_id}",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def admin_lesson_keyboard(
    lesson_id: int,
    course_id: int,
):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🎥 Загрузить или заменить видео",
        callback_data=f"admin_lesson_video:{lesson_id}",
    )
    keyboard.button(
        text="📄 Загрузить или заменить PDF",
        callback_data=f"admin_lesson_pdf:{lesson_id}",
    )
    keyboard.button(
        text="📝 Изменить описание",
        callback_data=f"admin_lesson_description:{lesson_id}",
    )
    keyboard.button(
        text="👁 Предпросмотр для ученика",
        callback_data=f"admin_lesson_preview:{lesson_id}",
    )
    keyboard.button(
        text="⬅️ К урокам",
        callback_data=f"admin_course_lessons:{course_id}",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


# =========================================================
# ОТПРАВКА УРОКА УЧЕНИКУ
# =========================================================

async def send_lesson(
    callback: CallbackQuery,
    lesson,
) -> None:
    if callback.message is None:
        return

    caption = (
        f"🎥 {lesson.title}\n\n"
        f"{lesson.description or 'Описание урока пока не добавлено.'}"
    )

    if lesson.video_file_id:
        await callback.message.answer_video(
            video=lesson.video_file_id,
            caption=caption,
            protect_content=True,
            reply_markup=lesson_only_keyboard(
                lesson.position,
            ),
        )
    else:
        await callback.message.answer(
            f"{caption}\n\n"
            "⚠️ Видео пока не загружено.",
            protect_content=True,
            reply_markup=lesson_only_keyboard(
                lesson.position,
            ),
        )

    if lesson.pdf_file_id:
        await callback.message.answer_document(
            document=lesson.pdf_file_id,
            caption=f"📄 Материалы к уроку {lesson.position}",
            protect_content=True,
        )

    await callback.message.answer(
        "Выберите дальнейшее действие:",
        reply_markup=navigation_keyboard(),
    )


# =========================================================
# ОБРАБОТЧИКИ УЧЕНИКА
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user is None:
        return

    user = get_user_from_telegram(message.from_user)

    await message.answer(
        "👋 Добро пожаловать!\n\n"
        f"Курс: «{COURSE_TITLE}»",
        reply_markup=main_menu(
            is_admin=user.is_admin,
        ),
    )


@dp.callback_query(F.data == "start_learning")
async def start_learning(callback: CallbackQuery):
    user = await check_course_access(callback)

    if user is None:
        return

    lesson_position = min(
        max(user.current_lesson, 1),
        len(lessons),
    )

    lesson = get_lesson_by_position(lesson_position)

    if lesson is None:
        await callback.answer(
            "Урок не найден.",
            show_alert=True,
        )
        return

    await send_lesson(callback, lesson)


@dp.callback_query(F.data == "lessons")
async def show_lessons(callback: CallbackQuery):
    user = await check_course_access(callback)

    if user is None:
        return

    await safe_edit(
        callback,
        "📚 Все уроки курса\n\n"
        "Выберите урок:",
        reply_markup=lessons_list_keyboard(
            lessons,
            user.current_lesson,
        ),
    )


@dp.callback_query(F.data.startswith("open_lesson:"))
async def open_lesson(callback: CallbackQuery):
    user = await check_course_access(callback)

    if user is None or callback.data is None:
        return

    lesson_position = int(
        callback.data.split(":")[1]
    )

    if lesson_position > user.current_lesson:
        await callback.answer(
            "🔒 Этот урок пока закрыт. "
            "Сначала пройдите предыдущий.",
            show_alert=True,
        )
        return

    lesson = get_lesson_by_position(lesson_position)

    if lesson is None:
        await callback.answer(
            "Урок не найден.",
            show_alert=True,
        )
        return

    await send_lesson(callback, lesson)


@dp.callback_query(F.data.startswith("locked_lesson:"))
async def locked_lesson(callback: CallbackQuery):
    await callback.answer(
        "🔒 Этот урок пока закрыт. "
        "Сначала пройдите предыдущий.",
        show_alert=True,
    )


@dp.callback_query(F.data.startswith("complete:"))
async def complete_lesson(callback: CallbackQuery):
    user = await check_course_access(callback)

    if (
        user is None
        or callback.data is None
        or callback.message is None
    ):
        return

    lesson_position = int(
        callback.data.split(":")[1]
    )
    current_lesson = user.current_lesson
    total_lessons = len(lessons)

    if lesson_position < current_lesson:
        await callback.answer(
            "✅ Этот урок уже пройден. "
            "Вы можете пересмотреть его в любое время.",
            show_alert=True,
        )
        return

    if lesson_position > current_lesson:
        await callback.answer(
            "🔒 Сначала завершите текущий урок.",
            show_alert=True,
        )
        return

    if lesson_position < total_lessons:
        next_position = lesson_position + 1

        update_current_lesson(
            user.telegram_id,
            next_position,
        )

        next_lesson = get_lesson_by_position(
            next_position
        )

        if next_lesson is None:
            await callback.answer(
                "Следующий урок не найден.",
                show_alert=True,
            )
            return

        completed_percent = int(
            (lesson_position / total_lessons) * 100
        )

        await callback.message.answer(
            f"🎉 Отлично! Урок {lesson_position} завершён.\n\n"
            f"Прогресс курса: {completed_percent}%\n\n"
            f"Открыт следующий урок:\n"
            f"📚 {next_lesson.title}",
            reply_markup=lesson_keyboard(
                next_lesson.position,
            ),
        )
        return

    update_current_lesson(
        user.telegram_id,
        total_lessons + 1,
    )

    await callback.message.answer(
        "🎉 Поздравляем!\n\n"
        "Вы прошли весь курс!",
        reply_markup=main_menu(
            is_admin=user.is_admin,
        ),
    )


@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user = get_user_from_telegram(
        callback.from_user
    )

    total_lessons = len(lessons)

    completed_lessons = min(
        max(user.current_lesson - 1, 0),
        total_lessons,
    )

    progress_percent = (
        int(
            completed_lessons
            / total_lessons
            * 100
        )
        if total_lessons
        else 0
    )

    progress_bar = build_progress_bar(
        user.current_lesson,
        total_lessons,
    )

    username = (
        f"@{user.username}"
        if user.username
        else "Username не указан"
    )

    if completed_lessons >= total_lessons:
        current_status = "✅ Курс завершён"
    else:
        current_status = (
            f"▶ Поточний урок: "
            f"{min(user.current_lesson, total_lessons)}"
        )

    await safe_edit(
        callback,
        f"👤 Особистий кабінет\n\n"
        f"Вітаємо, {user.first_name or 'учню'} 👋\n"
        f"{username}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏆 Ваш прогрес\n\n"
        f"📚 Придбано курсів: 1\n"
        f"🎓 Завершено уроків: "
        f"{completed_lessons}\n"
        f"⭐ Загальний прогрес: "
        f"{progress_percent}%\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 КУРС 1\n\n"
        f"Монтаж гіпсокартону з нуля\n\n"
        f"{progress_bar} {progress_percent}%\n\n"
        f"✔ {completed_lessons} із "
        f"{total_lessons} уроків\n"
        f"{current_status}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔒 КУРС 2\n\n"
        f"У розробці\n"
        f"🚧 Незабаром\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔒 КУРС 3\n\n"
        f"У розробці\n"
        f"🚧 Незабаром",
        reply_markup=main_menu(
            is_admin=user.is_admin,
        ),
    )


# =========================================================
# ГЛАВНЫЙ ЭКРАН АДМИНИСТРАТОРА
# =========================================================

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    user = await check_admin(callback)

    if user is None:
        return

    await safe_edit(
        callback,
        "👨‍💼 Панель администратора\n\n"
        "Выберите раздел:",
        reply_markup=admin_menu(),
    )


# =========================================================
# АДМИН: КУРСЫ И УРОКИ
# =========================================================

@dp.callback_query(F.data == "admin_courses")
async def admin_courses(callback: CallbackQuery):
    user = await check_admin(callback)

    if user is None:
        return

    await safe_edit(
        callback,
        "📚 Управление курсами\n\n"
        "Выберите курс:",
        reply_markup=admin_courses_keyboard(),
    )


@dp.callback_query(F.data.startswith("admin_course:"))
async def admin_course(callback: CallbackQuery):
    user = await check_admin(callback)

    if user is None or callback.data is None:
        return

    course_id = int(
        callback.data.split(":")[1]
    )

    course_lessons = [
        lesson
        for lesson in lessons
        if lesson.course_id == course_id
    ]

    await safe_edit(
        callback,
        f"🎓 {COURSE_TITLE}\n\n"
        f"Цена: {COURSE_PRICE} грн\n"
        f"Статус: активен\n"
        f"Уроков: {len(course_lessons)}",
        reply_markup=admin_course_keyboard(
            course_id
        ),
    )


@dp.callback_query(
    F.data.startswith("admin_course_lessons:")
)
async def admin_course_lessons(
    callback: CallbackQuery,
):
    user = await check_admin(callback)

    if user is None or callback.data is None:
        return

    course_id = int(
        callback.data.split(":")[1]
    )

    course_lessons = [
        lesson
        for lesson in lessons
        if lesson.course_id == course_id
    ]

    await safe_edit(
        callback,
        "📖 Уроки курса\n\n"
        "Выберите урок:\n\n"
        "🎥 — видео загружено\n"
        "📄 — PDF загружен\n"
        "⚪️ — материал отсутствует",
        reply_markup=admin_lessons_keyboard(
            course_lessons,
            course_id,
        ),
    )


# =========================================================
# АДМИН: ЗАГРУЗКА ВИДЕО
# =========================================================

@dp.callback_query(
    F.data.startswith("admin_lesson_video:")
)
async def admin_lesson_video(
    callback: CallbackQuery,
    state: FSMContext,
):
    user = await check_admin(callback)

    if (
        user is None
        or callback.data is None
        or callback.message is None
    ):
        return

    lesson_id = int(
        callback.data.split(":")[1]
    )

    await state.update_data(
        lesson_id=lesson_id
    )
    await state.set_state(
        AdminLessonEdit.waiting_for_video
    )

    await callback.message.answer(
        "🎥 Отправьте видео для этого урока.\n\n"
        "После загрузки бот автоматически "
        "сохранит его."
    )


@dp.message(
    AdminLessonEdit.waiting_for_video,
    F.video,
)
async def save_admin_video(
    message: Message,
    state: FSMContext,
):
    if (
        message.from_user is None
        or message.video is None
    ):
        return

    user = get_user_from_telegram(
        message.from_user
    )

    if not user.is_admin:
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return

    data = await state.get_data()
    lesson_id = data.get("lesson_id")

    if lesson_id is None:
        await message.answer(
            "Не удалось определить урок."
        )
        await state.clear()
        return

    saved = update_lesson_video(
        lesson_id=int(lesson_id),
        video_file_id=message.video.file_id,
    )

    if not saved:
        await message.answer("Урок не найден.")
        await state.clear()
        return

    refresh_lessons()

    await message.answer(
        "✅ Видео успешно сохранено.\n\n"
        f"Урок ID: {lesson_id}"
    )

    await state.clear()


@dp.message(AdminLessonEdit.waiting_for_video)
async def wrong_admin_video(message: Message):
    await message.answer(
        "Пожалуйста, отправьте именно видео, "
        "а не документ или текст."
    )


# =========================================================
# АДМИН: ЗАГРУЗКА PDF
# =========================================================

@dp.callback_query(
    F.data.startswith("admin_lesson_pdf:")
)
async def admin_lesson_pdf(
    callback: CallbackQuery,
    state: FSMContext,
):
    user = await check_admin(callback)

    if (
        user is None
        or callback.data is None
        or callback.message is None
    ):
        return

    lesson_id = int(
        callback.data.split(":")[1]
    )

    await state.update_data(
        lesson_id=lesson_id
    )
    await state.set_state(
        AdminLessonEdit.waiting_for_pdf
    )

    await callback.message.answer(
        "📄 Отправьте PDF-файл для этого урока."
    )


@dp.message(
    AdminLessonEdit.waiting_for_pdf,
    F.document,
)
async def save_admin_pdf(
    message: Message,
    state: FSMContext,
):
    if (
        message.from_user is None
        or message.document is None
    ):
        return

    user = get_user_from_telegram(
        message.from_user
    )

    if not user.is_admin:
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return

    file_name = (
        message.document.file_name or ""
    )

    is_pdf = (
        message.document.mime_type
        == "application/pdf"
        or file_name.lower().endswith(".pdf")
    )

    if not is_pdf:
        await message.answer(
            "⚠️ Это не PDF. "
            "Отправьте файл формата .pdf."
        )
        return

    data = await state.get_data()
    lesson_id = data.get("lesson_id")

    if lesson_id is None:
        await message.answer(
            "Не удалось определить урок."
        )
        await state.clear()
        return

    saved = update_lesson_pdf(
        lesson_id=int(lesson_id),
        pdf_file_id=message.document.file_id,
    )

    if not saved:
        await message.answer("Урок не найден.")
        await state.clear()
        return

    refresh_lessons()

    await message.answer(
        "✅ PDF успешно сохранён.\n\n"
        f"Урок ID: {lesson_id}"
    )

    await state.clear()


@dp.message(AdminLessonEdit.waiting_for_pdf)
async def wrong_admin_pdf(message: Message):
    await message.answer(
        "Пожалуйста, отправьте PDF как файл."
    )


# =========================================================
# АДМИН: ИЗМЕНЕНИЕ ОПИСАНИЯ
# =========================================================

@dp.callback_query(
    F.data.startswith(
        "admin_lesson_description:"
    )
)
async def admin_lesson_description(
    callback: CallbackQuery,
    state: FSMContext,
):
    user = await check_admin(callback)

    if (
        user is None
        or callback.data is None
        or callback.message is None
    ):
        return

    lesson_id = int(
        callback.data.split(":")[1]
    )

    await state.update_data(
        lesson_id=lesson_id
    )
    await state.set_state(
        AdminLessonEdit.waiting_for_description
    )

    await callback.message.answer(
        "📝 Отправьте новое описание урока "
        "одним текстовым сообщением."
    )


@dp.message(
    AdminLessonEdit.waiting_for_description,
    F.text,
)
async def save_admin_description(
    message: Message,
    state: FSMContext,
):
    if (
        message.from_user is None
        or message.text is None
    ):
        return

    user = get_user_from_telegram(
        message.from_user
    )

    if not user.is_admin:
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return

    description = message.text.strip()

    if len(description) < 5:
        await message.answer(
            "Описание слишком короткое. "
            "Введите хотя бы 5 символов."
        )
        return

    data = await state.get_data()
    lesson_id = data.get("lesson_id")

    if lesson_id is None:
        await message.answer(
            "Не удалось определить урок."
        )
        await state.clear()
        return

    saved = update_lesson_description(
        lesson_id=int(lesson_id),
        description=description,
    )

    if not saved:
        await message.answer("Урок не найден.")
        await state.clear()
        return

    refresh_lessons()

    await message.answer(
        "✅ Описание урока обновлено."
    )

    await state.clear()


@dp.message(
    AdminLessonEdit.waiting_for_description
)
async def wrong_admin_description(
    message: Message,
):
    await message.answer(
        "Пожалуйста, отправьте описание "
        "обычным текстом."
    )


# =========================================================
# АДМИН: ПРЕДПРОСМОТР УРОКА
# =========================================================

@dp.callback_query(
    F.data.startswith("admin_lesson_preview:")
)
async def admin_lesson_preview(
    callback: CallbackQuery,
):
    user = await check_admin(callback)

    if user is None or callback.data is None:
        return

    lesson_id = int(
        callback.data.split(":")[1]
    )

    lesson = get_lesson_by_id(lesson_id)

    if lesson is None:
        await callback.answer(
            "Урок не найден.",
            show_alert=True,
        )
        return

    await send_lesson(callback, lesson)


# =========================================================
# АДМИН: КАРТОЧКА УРОКА
# ВАЖНО: общий обработчик размещён после video/pdf/description
# =========================================================

@dp.callback_query(F.data.startswith("admin_lesson:"))
async def admin_lesson(callback: CallbackQuery):
    user = await check_admin(callback)

    if user is None or callback.data is None:
        return

    lesson_id = int(
        callback.data.split(":")[1]
    )

    lesson = get_lesson_by_id(lesson_id)

    if lesson is None:
        await callback.answer(
            "Урок не найден.",
            show_alert=True,
        )
        return

    video_status = (
        "✅ загружено"
        if lesson.video_file_id
        else "❌ не загружено"
    )

    pdf_status = (
        "✅ загружено"
        if lesson.pdf_file_id
        else "❌ не загружено"
    )

    await safe_edit(
        callback,
        f"📖 {lesson.title}\n\n"
        f"Позиция: {lesson.position}\n"
        f"Видео: {video_status}\n"
        f"PDF: {pdf_status}\n\n"
        f"Описание:\n"
        f"{lesson.description or 'Описание не добавлено'}",
        reply_markup=admin_lesson_keyboard(
            lesson.id,
            lesson.course_id,
        ),
    )


# =========================================================
# ЗАГЛУШКИ ДЛЯ БУДУЩИХ РАЗДЕЛОВ
# =========================================================

@dp.callback_query(F.data == "admin_news")
async def admin_news(callback: CallbackQuery):
    user = await check_admin(callback)

    if user is None:
        return

    await callback.answer(
        "Раздел новостей добавим следующим этапом.",
        show_alert=True,
    )


@dp.callback_query(F.data == "admin_students")
async def admin_students(callback: CallbackQuery):
    user = await check_admin(callback)

    if user is None:
        return

    await callback.answer(
        "Раздел учеников добавим следующим этапом.",
        show_alert=True,
    )


@dp.callback_query(F.data == "admin_statistics")
async def admin_statistics(callback: CallbackQuery):
    user = await check_admin(callback)

    if user is None:
        return

    await callback.answer(
        "Раздел статистики добавим следующим этапом.",
        show_alert=True,
    )


# =========================================================
# ЗАПУСК
# =========================================================

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())