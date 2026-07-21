import asyncio
import html
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
from app.bot.services.announcement_service import (
    create_announcement,
    get_active_student_telegram_ids,
    get_announcement,
    get_published_announcements,
    publish_announcement,
)

from app.bot.services.purchase_service import (

    get_purchased_courses_count,

    grant_course_access,

    user_has_active_course,

)

from app.bot.services.lesson_progress_service import (
    get_completed_lesson_ids,
    get_course_progress,
    get_next_available_lesson,
    is_lesson_available,
    is_lesson_completed,
    mark_lesson_completed,
)
from app.bot.services.lesson_service import (
    get_all_lessons,
    update_lesson_description,
    update_lesson_pdf,
    update_lesson_video,
    update_lesson_title,
)
from app.bot.services.purchase_service import (
    get_purchased_courses_count,
    user_has_active_course,
)
from app.bot.services.user_service import (
    get_all_users,
    get_or_create_user,
    get_user_by_id,
    get_users_count,
)


from app.bot.services.review_service import (
    delete_review,
    get_review_summary,
    get_reviews,
    get_user_review,
    mark_review_read,
    save_rating,
    save_review_text,
)
from app.bot.services.statistics_service import get_platform_statistics
from app.database.database import Base, engine

Base.metadata.create_all(bind=engine)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    raise RuntimeError("BOT_TOKEN is not set in .env")
COURSE_ID = 1

COURSE_TITLE = "Монтаж гіпсокартону з нуля"

COURSE_PRICE = 1000

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
lessons = get_all_lessons()


class AdminLessonEdit(StatesGroup):
    waiting_for_video = State()
    waiting_for_pdf = State()
    waiting_for_title = State()
    waiting_for_description = State()


class AdminAnnouncementCreate(StatesGroup):
    waiting_for_title = State()
    waiting_for_text = State()
    waiting_for_image = State()


class CourseReviewCreate(StatesGroup):
    waiting_for_text = State()


def refresh_lessons() -> None:
    global lessons
    lessons = get_all_lessons()


def admin_news_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Создать новость", callback_data="admin_news_create")
    keyboard.button(text="📋 История новостей", callback_data="admin_news_history")
    keyboard.button(text="⬅️ Назад", callback_data="admin_panel")
    keyboard.adjust(1)
    return keyboard.as_markup()


def announcement_confirmation_keyboard(announcement_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text="✅ Опубликовать", callback_data=f"admin_news_publish:{announcement_id}"
    )
    keyboard.button(
        text="❌ Отмена", callback_data=f"admin_news_cancel:{announcement_id}"
    )
    keyboard.adjust(1)
    return keyboard.as_markup()


def get_user_from_telegram(telegram_user: Any):
    return get_or_create_user(
        telegram_id=telegram_user.id,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        username=telegram_user.username,
    )

def purchase_success_keyboard():

    keyboard = InlineKeyboardBuilder()

    keyboard.button(

        text="▶️ Розпочати навчання",

        callback_data="start_learning",

    )

    keyboard.button(

        text="👤 Особистий кабінет",

        callback_data="profile",

    )

    keyboard.adjust(1)

    return keyboard.as_markup()

def test_payment_keyboard(course_id: int):

    keyboard = InlineKeyboardBuilder()

    keyboard.button(

        text="🧪 Симулювати успішну оплату",

        callback_data=f"test_payment_success:{course_id}",

    )

    keyboard.button(

        text="⬅️ До особистого кабінету",

        callback_data="profile",

    )

    keyboard.adjust(1)

    return keyboard.as_markup()



def get_lesson_by_id(lesson_id: int):
    return next((lesson for lesson in lessons if lesson.id == lesson_id), None)


def get_lesson_by_position(position: int):
    return next((lesson for lesson in lessons if lesson.position == position), None)


def build_progress_bar(completed_lessons: int, total_lessons: int) -> str:
    filled = min(max(completed_lessons, 0), total_lessons)
    empty = max(total_lessons - filled, 0)
    return "🟩" * filled + "⬜" * empty


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
) -> None:
    if callback.message is None:
        return

    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest as error:
        if "message is not modified" in str(error):
            await callback.answer("Уже відкрито")
        else:
            raise




async def check_admin(callback: CallbackQuery):
    user = get_user_from_telegram(callback.from_user)
    if not user.is_admin:
        await callback.answer("⛔ У вас нет доступа к админ-панели.", show_alert=True)
        return None
    return user


async def check_course_access(callback: CallbackQuery):
    user = get_user_from_telegram(callback.from_user)
    if not user_has_active_course(user.id, COURSE_ID):
        await callback.answer(

            "🔒 Цей курс ще не придбано. "

            "Відкрийте особистий кабінет та натисніть "

            "«Придбати курс».",

            show_alert=True,

        )
        return None
    return user

async def send_purchase_success(

    telegram_id: int,

    course_title: str,

) -> None:

    await bot.send_message(

        chat_id=telegram_id,

        text=(

            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "🎉 <b>ОПЛАТУ УСПІШНО ОТРИМАНО!</b>\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "Доступ до курсу відкрито.\n\n"

            f"📦 <b>{html.escape(course_title)}</b>\n\n"

            "Матеріали вже доступні у вашому "

            "особистому кабінеті.\n\n"

            "Бажаємо успішного навчання!\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━"

        ),

        parse_mode="HTML",

        protect_content=True,

        reply_markup=purchase_success_keyboard(),

    )



async def show_profile(
    callback: CallbackQuery | None = None,
    message: Message | None = None,
) -> None:
    telegram_user = (
        callback.from_user
        if callback is not None
        else message.from_user
        if message is not None
        else None
    )

    if telegram_user is None:
        return

    user = get_user_from_telegram(telegram_user)

    purchased_courses_count = get_purchased_courses_count(
        user_id=user.id,
    )

    has_course_access = user_has_active_course(
        user_id=user.id,
        course_id=COURSE_ID,
    )

    username_line = (
        f"🔗 @{user.username}\n"
        if user.username
        else ""
    )

    if has_course_access:
        progress = get_course_progress(
            user_id=user.id,
            course_id=COURSE_ID,
        )

        completed_lessons = progress["completed"]
        total_lessons = progress["total"]
        progress_percent = progress["percent"]

        progress_bar = build_progress_bar(
            completed_lessons,
            total_lessons,
        )

        next_lesson = get_next_available_lesson(
            user_id=user.id,
            course_id=COURSE_ID,
        )

        if next_lesson is None:
            status_line = "🏆 Курс успішно завершено"
        else:
            status_line = (
                f"▶️ Наступний урок: "
                f"{next_lesson.position}. {next_lesson.title}"
            )

        course_block = (
            "🟢 ДОСТУПНИЙ КУРС\n\n"
            f"📦 {COURSE_TITLE}\n\n"
            f"{progress_bar}\n"
            f"Прогрес: {progress_percent}%\n\n"
            f"✅ Завершено: {completed_lessons} із "
            f"{total_lessons} уроків\n"
            f"{status_line}"
        )

    else:
        course_block = (
            "🔒 КУРС 1 - НЕ ПРИДБАНО\n\n"
            f"📦 {COURSE_TITLE}\n\n"
            f"🎥 {len(lessons)} відеоуроків\n"
            "📄 PDF-матеріали\n"
            "♾ Довічний доступ\n\n"
            f"💳 Вартість: {COURSE_PRICE} грн"
        )

    text = (
        "👤 ОСОБИСТИЙ КАБІНЕТ\n\n"
        f"Вітаємо, {user.first_name or 'учню'} 👋\n"
        f"{username_line}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 ВАША СТАТИСТИКА\n\n"
        f"🎓 Придбано курсів: {purchased_courses_count}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{course_block}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚧 КУРС 2\n\n"
        "Новий курс готується до запуску.\n"
        "Стежте за новинами платформи.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚧 КУРС 3\n\n"
        "У розробці"
    )

    keyboard = profile_courses_keyboard(
        has_course_access=has_course_access,
        is_admin=user.is_admin,
    )

    if callback is not None:
        await safe_edit(
            callback,
            text,
            reply_markup=keyboard,
        )
    elif message is not None:
        await message.answer(
            text,
            reply_markup=keyboard,
        )

def main_menu(is_admin: bool = False):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📢 Новости", callback_data="student_news")
    keyboard.button(text="📚 Начать обучение", callback_data="start_learning")
    keyboard.button(text="👤 Мой профиль", callback_data="profile")
    if is_admin:
        keyboard.button(text="👨\u200d💼 Админ-панель", callback_data="admin_panel")
    keyboard.adjust(1)
    return keyboard.as_markup()

def profile_courses_keyboard(
    has_course_access: bool,
    is_admin: bool = False,
):
    keyboard = InlineKeyboardBuilder()

    if has_course_access:
        keyboard.button(
            text="▶️ Продовжити навчання",
            callback_data="start_learning",
        )

        keyboard.button(
            text="📚 Програма курсу",
            callback_data="lessons",
        )

        keyboard.button(
            text="⭐ Мій відгук",
            callback_data=f"profile_review:{COURSE_ID}",
        )

    else:
        keyboard.button(
            text=f"💳 Придбати курс — {COURSE_PRICE} грн",
            callback_data=f"buy_course:{COURSE_ID}",
        )

    keyboard.button(
        text="📢 Новини",
        callback_data="student_news",
    )

    if is_admin:
        keyboard.button(
            text="👨‍💼 Панель адміністратора",
            callback_data="admin_panel",
        )

    keyboard.adjust(1)
    return keyboard.as_markup()


def user_review_empty_keyboard(course_id: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="⭐ Залишити оцінку",
        callback_data=f"user_review_create:{course_id}",
    )

    keyboard.button(
        text="⬅️ До особистого кабінету",
        callback_data="profile",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def user_review_actions_keyboard(course_id: int, review_id: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="⭐ Змінити оцінку",
        callback_data=f"user_review_change_rating:{course_id}",
    )

    keyboard.button(
        text="✍️ Змінити текст",
        callback_data=f"user_review_change_text:{course_id}",
    )

    keyboard.button(
        text="🗑 Видалити відгук",
        callback_data=f"user_review_delete:{review_id}",
    )

    keyboard.button(
        text="⬅️ До особистого кабінету",
        callback_data="profile",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def review_after_course_keyboard(course_id: int):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="⭐ Оцінити курс",
        callback_data=f"user_review_create:{course_id}",
    )

    keyboard.button(
        text="⏭ Оцінити пізніше",
        callback_data="profile",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()




def lesson_only_keyboard(lesson_position: int):
    keyboard = InlineKeyboardBuilder()
    if lesson_position < len(lessons):
        button_text = "✅ Завершити урок"
    else:
        button_text = "🏁 Завершити курс"
    keyboard.button(text=button_text, callback_data=f"complete:{lesson_position}")
    keyboard.adjust(1)
    return keyboard.as_markup()


def announcement_image_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⏭ Без изображения", callback_data="admin_news_without_image")
    keyboard.button(text="❌ Отмена", callback_data="admin_news")
    keyboard.adjust(1)
    return keyboard.as_markup()


def navigation_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📚 Все уроки", callback_data="lessons")
    keyboard.button(text="👤 Мой профиль", callback_data="profile")
    keyboard.adjust(1)
    return keyboard.as_markup()

def navigation_keyboard():

    keyboard = InlineKeyboardBuilder()

    keyboard.button(

        text="📚 Програма курсу",

        callback_data="lessons",

    )

    keyboard.button(

        text="👤 Особистий кабінет",

        callback_data="profile",

    )

    keyboard.adjust(1)

    return keyboard.as_markup()




def lesson_keyboard(lesson_position: int):
    keyboard = InlineKeyboardBuilder()
    if lesson_position < len(lessons):
        button_text = "▶️ Відкрити наступний урок"
    else:
        button_text = "🏁 Завершити курс"
    keyboard.button(text=button_text, callback_data=f"complete:{lesson_position}")
    keyboard.button(text="📚 Все уроки", callback_data="lessons")
    keyboard.adjust(1)
    return keyboard.as_markup()


def lessons_list_keyboard(
    course_lessons,
    completed_lesson_ids: set[int],
    available_lesson_id: int | None,
):
    keyboard = InlineKeyboardBuilder()

    for lesson in course_lessons:
        if lesson.id in completed_lesson_ids:
            text = f"✅ {lesson.position}. {lesson.title}"
            callback_data = f"open_lesson:{lesson.position}"

        elif lesson.id == available_lesson_id:
            text = f"▶️ {lesson.position}. {lesson.title}"
            callback_data = f"open_lesson:{lesson.position}"

        else:
            text = f"🔒 {lesson.position}. {lesson.title}"
            callback_data = f"locked_lesson:{lesson.position}"

        keyboard.button(
            text=text,
            callback_data=callback_data,
        )

    keyboard.button(
        text="⬅️ До особистого кабінету",
        callback_data="profile",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()



def rating_keyboard(course_id: int):
    keyboard = InlineKeyboardBuilder()
    for rating in range(5, 0, -1):
        keyboard.button(text="⭐" * rating, callback_data=f"review_rating:{course_id}:{rating}")
    keyboard.button(text="⏭ Не оцінювати", callback_data="review_skip")
    keyboard.adjust(1)
    return keyboard.as_markup()


def review_text_keyboard(course_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✍️ Залишити відгук", callback_data=f"review_write:{course_id}")
    keyboard.button(text="⏭ Пропустити", callback_data="review_skip")
    keyboard.adjust(1)
    return keyboard.as_markup()


def admin_reviews_keyboard():
    summary = get_review_summary()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text=f"🆕 Нові ({summary['unread']})", callback_data="admin_reviews_new")
    keyboard.button(text=f"📚 Усі відгуки ({summary['total']})", callback_data="admin_reviews_all")
    keyboard.button(text="⬅️ Назад", callback_data="admin_panel")
    keyboard.adjust(1)
    return keyboard.as_markup()


def review_admin_actions(review_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Прочитано", callback_data=f"admin_review_read:{review_id}")
    keyboard.button(text="🗑 Видалити", callback_data=f"admin_review_delete:{review_id}")
    keyboard.adjust(2)
    return keyboard.as_markup()


def admin_menu():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📚 Курсы", callback_data="admin_courses")
    keyboard.button(text="📢 Новости", callback_data="admin_news")
    keyboard.button(text="👥 Ученики", callback_data="admin_students")
    keyboard.button(text="⭐ Отзывы", callback_data="admin_reviews")
    keyboard.button(text="📊 Статистика", callback_data="admin_statistics")
    keyboard.button(text="⬅️ Личный кабинет", callback_data="profile")
    keyboard.adjust(1)
    return keyboard.as_markup()


def admin_students_keyboard(
    users,
    page: int,
    total_users: int,
    page_size: int = 10,
):
    keyboard = InlineKeyboardBuilder()

    for student in users:
        full_name = " ".join(
            part
            for part in [
                student.first_name,
                student.last_name,
            ]
            if part
        ).strip()

        if not full_name:
            full_name = (
                f"@{student.username}"
                if student.username
                else f"Користувач {student.id}"
            )

        admin_icon = " 👨‍💼" if student.is_admin else ""

        keyboard.button(
            text=f"👤 {full_name}{admin_icon}",
            callback_data=f"admin_student:{student.id}",
        )

    total_pages = max(
        1,
        (total_users + page_size - 1) // page_size,
    )

    navigation_buttons = 1

    if page > 1:
        keyboard.button(
            text="⬅️",
            callback_data=f"admin_students_page:{page - 1}",
        )
        navigation_buttons += 1

    keyboard.button(
        text=f"{page}/{total_pages}",
        callback_data="admin_students_page_info",
    )

    if page < total_pages:
        keyboard.button(
            text="➡️",
            callback_data=f"admin_students_page:{page + 1}",
        )
        navigation_buttons += 1

    keyboard.button(
        text="⬅️ Назад",
        callback_data="admin_panel",
    )

    keyboard.adjust(
        *([1] * len(users)),
        navigation_buttons,
        1,
    )

    return keyboard.as_markup()

def admin_student_keyboard(
    student_id: int,
    has_course_access: bool,
    page: int = 1,
):
    keyboard = InlineKeyboardBuilder()

    if not has_course_access:
        keyboard.button(
            text="🔓 Видати доступ до курсу",
            callback_data=f"admin_grant_course:{student_id}:{page}",
        )

    keyboard.button(
        text="🔄 Оновити дані",
        callback_data=f"admin_student:{student_id}:{page}",
    )

    keyboard.button(
        text="⬅️ До списку учнів",
        callback_data=f"admin_students_page:{page}",
    )

    keyboard.adjust(1)
    return keyboard.as_markup()


def admin_courses_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text="🎓 Курс 1. Монтаж гипсокартона", callback_data=f"admin_course:{COURSE_ID}"
    )
    keyboard.button(text="⬅️ Назад", callback_data="admin_panel")
    keyboard.adjust(1)
    return keyboard.as_markup()


def admin_course_keyboard(course_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📖 Уроки", callback_data=f"admin_course_lessons:{course_id}")
    keyboard.button(text="⬅️ К курсам", callback_data="admin_courses")
    keyboard.adjust(1)
    return keyboard.as_markup()


def buy_course_keyboard(course_id: int):

    keyboard = InlineKeyboardBuilder()

    keyboard.button(

        text=f"💳 Оплатити {COURSE_PRICE} грн",

        callback_data=f"create_payment:{course_id}",

    )

    keyboard.button(

        text="⬅️ Повернутися до кабінету",

        callback_data="profile",

    )

    keyboard.adjust(1)

    return keyboard.as_markup()


def admin_lessons_keyboard(course_lessons, course_id: int):
    keyboard = InlineKeyboardBuilder()
    for lesson in course_lessons:
        video_icon = "🎥" if lesson.video_file_id else "⚪️"
        pdf_icon = "📄" if lesson.pdf_file_id else "⚪️"
        keyboard.button(
            text=f"{lesson.position}. {lesson.title} {video_icon}{pdf_icon}",
            callback_data=f"admin_lesson:{lesson.id}",
        )
    keyboard.button(text="⬅️ Назад", callback_data=f"admin_course:{course_id}")
    keyboard.adjust(1)
    return keyboard.as_markup()


def admin_lesson_keyboard(lesson_id: int, course_id: int):
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
        text="✏️ Изменить название",
        callback_data=f"admin_lesson_title:{lesson_id}",
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
        text="⬅️ К урокам", callback_data=f"admin_course_lessons:{course_id}"
    )

    keyboard.adjust(1)
    return keyboard.as_markup()

async def send_lesson(callback: CallbackQuery, lesson):

    if callback.message is None:
        return

    caption = (
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎥 УРОК {lesson.position}\n\n"
        f"📖 <b>{lesson.title}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{lesson.description or 'Опис уроку ще не додано.'}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ Після перегляду уроку натисніть кнопку\n"
        "<b>«Завершити урок»</b>, щоб відкрити наступний."
    )

    if lesson.video_file_id:

        await callback.message.answer_video(
            video=lesson.video_file_id,
            caption=caption,
            parse_mode="HTML",
            protect_content=True,
            reply_markup=lesson_only_keyboard(
                lesson.position
            ),
        )

    else:

        await callback.message.answer(
            caption
            + "\n\n⚠️ Відео ще не завантажено.",
            parse_mode="HTML",
            protect_content=True,
            reply_markup=lesson_only_keyboard(
                lesson.position
            ),
        )

    await callback.message.answer(
        "📚 <b>Навігація</b>",
        parse_mode="HTML",
        reply_markup=navigation_keyboard(),
    )



@dp.message(CommandStart())
async def start(message: Message):
    await show_profile(message=message)


@dp.callback_query(F.data == "student_news")
async def student_news(callback: CallbackQuery):
    user = get_user_from_telegram(
        callback.from_user
    )

    if callback.message is None:
        return

    announcements = get_published_announcements()

    if not announcements:
        await safe_edit(
            callback,
            (
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "📢 <b>НОВИНИ ПЛАТФОРМИ</b>\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "Поки що новин немає.\n\n"
                "Усі важливі повідомлення та оновлення "
                "з’являться у цьому розділі.\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            ),
            parse_mode="HTML",
            reply_markup=profile_courses_keyboard(
                has_course_access=user_has_active_course(
                    user_id=user.id,
                    course_id=COURSE_ID,
                ),
                is_admin=user.is_admin,
            ),
        )
        return

    await safe_edit(
        callback,
        (
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📢 <b>ОСТАННІ НОВИНИ</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Нижче відображено останні повідомлення "
            "платформи."
        ),
        parse_mode="HTML",
        reply_markup=None,
    )

    for announcement in announcements[:5]:
        title = html.escape(
            announcement.title
        )
        announcement_text = html.escape(
            announcement.text
        )

        news_text = (
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📢 <b>НОВИНА ПЛАТФОРМИ</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📰 <b>{title}</b>\n\n"
            f"{announcement_text}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎓 Монтаж по Фрейду"
        )

        if announcement.image_file_id:
            await callback.message.answer_photo(
                photo=announcement.image_file_id,
                caption=news_text,
                parse_mode="HTML",
                protect_content=True,
            )
        else:
            await callback.message.answer(
                news_text,
                parse_mode="HTML",
                protect_content=True,
            )

    has_course_access = user_has_active_course(
        user_id=user.id,
        course_id=COURSE_ID,
    )

    await callback.message.answer(
        "Оберіть подальшу дію:",
        reply_markup=profile_courses_keyboard(
            has_course_access=has_course_access,
            is_admin=user.is_admin,
        ),
    )

    await callback.answer()



@dp.callback_query(F.data == "start_learning")
async def start_learning(callback: CallbackQuery):
    user = await check_course_access(callback)
    if user is None:
        return
    lesson = get_next_available_lesson(user_id=user.id, course_id=COURSE_ID)
    if lesson is None:
        await safe_edit(
            callback,
            "🎉 Вы уже прошли весь курс!",
            reply_markup=main_menu(is_admin=user.is_admin),
        )
        return
    await send_lesson(callback, lesson)


@dp.callback_query(F.data == "lessons")
async def show_lessons(callback: CallbackQuery):
    user = await check_course_access(callback)

    if user is None:
        return

    completed_ids = get_completed_lesson_ids(
        user_id=user.id,
        course_id=COURSE_ID,
    )

    next_lesson = get_next_available_lesson(
        user_id=user.id,
        course_id=COURSE_ID,
    )

    available_lesson_id = (
        next_lesson.id
        if next_lesson is not None
        else None
    )

    progress = get_course_progress(
        user_id=user.id,
        course_id=COURSE_ID,
    )

    await safe_edit(
        callback,
        (
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📚 <b>ПРОГРАМА КУРСУ</b>\n\n"
            f"<b>{COURSE_TITLE}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Прогрес: {progress['percent']}%\n"
            f"Завершено: {progress['completed']} із "
            f"{progress['total']} уроків\n\n"
            "✅ — завершено\n"
            "▶️ — доступно зараз\n"
            "🔒 — ще закрито\n\n"
            "Оберіть потрібний урок:"
        ),
        parse_mode="HTML",
        reply_markup=lessons_list_keyboard(
            lessons,
            completed_ids,
            available_lesson_id,
        ),
    )



@dp.callback_query(F.data.startswith("open_lesson:"))
async def open_lesson(callback: CallbackQuery):
    user = await check_course_access(callback)
    if user is None or callback.data is None:
        return
    lesson_position = int(callback.data.split(":")[1])
    lesson = get_lesson_by_position(lesson_position)
    if lesson is None:
        await callback.answer("Урок не найден.", show_alert=True)
        return
    available = is_lesson_available(user_id=user.id, lesson_id=lesson.id)
    completed = is_lesson_completed(user_id=user.id, lesson_id=lesson.id)
    if not available and (not completed):
        await callback.answer(
            "🔒 Этот урок пока закрыт. Сначала пройдите предыдущий.", show_alert=True
        )
        return
    await send_lesson(callback, lesson)


@dp.callback_query(F.data.startswith("locked_lesson:"))

async def locked_lesson(callback: CallbackQuery):

    await callback.answer(

        "🔒 Цей урок поки що закритий.\n\n"

        "Спочатку завершіть попередній урок.",

        show_alert=True,

    )




@dp.callback_query(F.data.startswith("complete:"))
async def complete_lesson(callback: CallbackQuery):
    user = await check_course_access(callback)
    if user is None or callback.data is None or callback.message is None:
        return
    lesson_position = int(callback.data.split(":")[1])
    lesson = get_lesson_by_position(lesson_position)
    if lesson is None:
        await callback.answer("Урок не найден.", show_alert=True)
        return
    already_completed = is_lesson_completed(user_id=user.id, lesson_id=lesson.id)
    if already_completed:
        await callback.answer("✅ Этот урок уже пройден.", show_alert=True)
        return
    available = is_lesson_available(user_id=user.id, lesson_id=lesson.id)
    if not available:
        await callback.answer("🔒 Сначала пройдите предыдущий урок.", show_alert=True)
        return
    saved = mark_lesson_completed(user_id=user.id, lesson_id=lesson.id)
    if not saved:
        await callback.answer("Не удалось сохранить прогресс.", show_alert=True)
        return
    progress = get_course_progress(user_id=user.id, course_id=COURSE_ID)
    next_lesson = get_next_available_lesson(user_id=user.id, course_id=COURSE_ID)
    if next_lesson is None:
        await callback.message.answer(
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🏆 <b>Курс завершено!</b>\n\n"
            "Вітаємо! Ви успішно завершили курс\n\n"
            f"<b>{html.escape(COURSE_TITLE)}</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML",
        )

        existing_review = get_user_review(
            user.id,
            COURSE_ID,
        )

        if existing_review is None:
            await callback.message.answer(
                "⭐ <b>Будемо вдячні за вашу оцінку</b>\n\n"
                "Ви можете оцінити курс зараз або повернутися "
                "до цього пізніше через особистий кабінет.",
                parse_mode="HTML",
                reply_markup=review_after_course_keyboard(
                    COURSE_ID
                ),
            )
        else:
            await callback.message.answer(
                "❤️ Дякуємо за проходження курсу та ваш відгук!",
                reply_markup=profile_courses_keyboard(
                    has_course_access=True,
                    is_admin=user.is_admin,
                ),
            )

        return
    await callback.message.answer(

        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🎉 <b>Вітаємо!</b>\n\n"

        "Урок успішно завершено.\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"🔓 Відкрито новий урок\n\n"

        f"📖 <b>{next_lesson.title}</b>\n\n"

        "Бажаємо успіхів у навчанні!\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━",

        parse_mode="HTML",

        reply_markup=lesson_keyboard(

            next_lesson.position

        ),

    )

@dp.callback_query(F.data.startswith("profile_review:"))
async def profile_review(callback: CallbackQuery):
    if callback.data is None:
        return

    user = await check_course_access(callback)

    if user is None:
        return

    course_id = int(
        callback.data.split(":")[1]
    )

    review = get_user_review(
        user.id,
        course_id,
    )

    if review is None:
        await safe_edit(
            callback,
            (
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "⭐ <b>МІЙ ВІДГУК</b>\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📦 <b>{html.escape(COURSE_TITLE)}</b>\n\n"
                "Ви ще не залишили оцінку цьому курсу.\n\n"
                "Ви можете зробити це зараз або повернутися "
                "до цього розділу пізніше."
            ),
            parse_mode="HTML",
            reply_markup=user_review_empty_keyboard(
                course_id
            ),
        )
        return

    review_text = (
        html.escape(review.text)
        if review.text
        else "Текстовий відгук не залишено."
    )

    await safe_edit(
        callback,
        (
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⭐ <b>МІЙ ВІДГУК</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 <b>{html.escape(COURSE_TITLE)}</b>\n\n"
            f"Ваша оцінка:\n{'⭐' * review.rating}\n\n"
            f"Ваш відгук:\n{review_text}"
        ),
        parse_mode="HTML",
        reply_markup=user_review_actions_keyboard(
            course_id=course_id,
            review_id=review.id,
        ),
    )


@dp.callback_query(F.data.startswith("user_review_create:"))
async def user_review_create(callback: CallbackQuery):
    if callback.data is None:
        return

    user = await check_course_access(callback)

    if user is None:
        return

    course_id = int(
        callback.data.split(":")[1]
    )

    await safe_edit(
        callback,
        (
            "⭐ <b>ОЦІНІТЬ КУРС</b>\n\n"
            f"📦 {html.escape(COURSE_TITLE)}\n\n"
            "Оберіть оцінку від 1 до 5:"
        ),
        parse_mode="HTML",
        reply_markup=rating_keyboard(
            course_id
        ),
    )


@dp.callback_query(F.data.startswith("review_rating:"))
async def review_rating(callback: CallbackQuery):
    if callback.data is None or callback.message is None:
        return

    user = await check_course_access(callback)

    if user is None:
        return

    _, course_id_raw, rating_raw = (
        callback.data.split(":")
    )

    course_id = int(course_id_raw)
    rating = int(rating_raw)

    if rating < 1 or rating > 5:
        await callback.answer(
            "Некоректна оцінка.",
            show_alert=True,
        )
        return

    previous_review = get_user_review(
        user.id,
        course_id,
    )

    review = save_rating(
        user.id,
        course_id,
        rating,
    )

    if review is None:
        await callback.answer(
            "Не вдалося зберегти оцінку.",
            show_alert=True,
        )
        return

    if previous_review is not None:
        review_text = (
            html.escape(review.text)
            if review.text
            else "Текстовий відгук не залишено."
        )

        await safe_edit(
            callback,
            (
                "✅ <b>Оцінку оновлено</b>\n\n"
                f"Ваша нова оцінка:\n{'⭐' * rating}\n\n"
                f"Ваш відгук:\n{review_text}"
            ),
            parse_mode="HTML",
            reply_markup=user_review_actions_keyboard(
                course_id=course_id,
                review_id=review.id,
            ),
        )
        return

    await safe_edit(
        callback,
        (
            f"Дякуємо за оцінку: {'⭐' * rating}\n\n"
            "Хочете залишити короткий текстовий відгук?"
        ),
        reply_markup=review_text_keyboard(
            course_id
        ),
    )

@dp.callback_query(F.data.startswith("admin_lesson_title:"))
async def admin_lesson_title(
    callback: CallbackQuery,
    state: FSMContext,
):
    await callback.answer()

    user = get_user_from_telegram(callback.from_user)

    if user is None or not user.is_admin:
        await callback.answer(
            "⛔ Нет доступа.",
            show_alert=True,
        )
        return

    if callback.data is None:
        return

    try:
        lesson_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        if callback.message:
            await callback.message.answer(
                "❌ Не удалось определить урок."
            )
        return

    await state.update_data(lesson_id=lesson_id)
    await state.set_state(
        AdminLessonEdit.waiting_for_title
    )

    if callback.message:
        await callback.message.answer(
            "✏️ Отправьте новое название урока "
            "обычным текстовым сообщением."
        )

@dp.message(AdminLessonEdit.waiting_for_title, F.text)
async def save_admin_lesson_title(message: Message, state: FSMContext):
    if message.from_user is None or message.text is None:
        return

    user = get_user_from_telegram(message.from_user)

    if not user.is_admin:
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return

    title = message.text.strip()

    if len(title) < 2:
        await message.answer("Название слишком короткое.")
        return

    data = await state.get_data()
    lesson_id = data.get("lesson_id")

    if lesson_id is None:
        await message.answer("Не удалось определить урок.")
        await state.clear()
        return

    saved = update_lesson_title(
        lesson_id=int(lesson_id),
        title=title,
    )

    if not saved:
        await message.answer("Урок не найден.")
        await state.clear()
        return

    refresh_lessons()

    await message.answer("✅ Название урока обновлено.")

    await state.clear()


@dp.message(AdminLessonEdit.waiting_for_title)
async def wrong_admin_lesson_title(message: Message):
    await message.answer(
        "Пожалуйста, отправьте название обычным текстом."
    )




@dp.callback_query(
    F.data.startswith("user_review_change_rating:")
)
async def user_review_change_rating(
    callback: CallbackQuery,
):
    if callback.data is None:
        return

    user = await check_course_access(callback)

    if user is None:
        return

    course_id = int(
        callback.data.split(":")[1]
    )

    await safe_edit(
        callback,
        (
            "⭐ <b>ЗМІНА ОЦІНКИ</b>\n\n"
            f"📦 {html.escape(COURSE_TITLE)}\n\n"
            "Оберіть нову оцінку:"
        ),
        parse_mode="HTML",
        reply_markup=rating_keyboard(
            course_id
        ),
    )

@dp.callback_query(
    F.data.startswith("user_review_change_text:")
)
async def user_review_change_text(
    callback: CallbackQuery,
    state: FSMContext,
):
    if callback.data is None or callback.message is None:
        return

    user = await check_course_access(callback)

    if user is None:
        return

    course_id = int(
        callback.data.split(":")[1]
    )

    review = get_user_review(
        user.id,
        course_id,
    )

    if review is None:
        await callback.answer(
            "Спочатку поставте оцінку курсу.",
            show_alert=True,
        )
        return

    await state.update_data(
        review_course_id=course_id
    )

    await state.set_state(
        CourseReviewCreate.waiting_for_text
    )

    await callback.message.answer(
        "✍️ Напишіть новий текст відгуку одним повідомленням.\n\n"
        "Попередній текст буде замінено."
    )

    await callback.answer()

@dp.callback_query(
    F.data.startswith("user_review_delete:")
)
async def user_review_delete(
    callback: CallbackQuery,
):
    if callback.data is None:
        return

    user = get_user_from_telegram(
        callback.from_user
    )

    review_id = int(
        callback.data.split(":")[1]
    )

    review = get_user_review(
        user.id,
        COURSE_ID,
    )

    if review is None or review.id != review_id:
        await callback.answer(
            "Відгук не знайдено.",
            show_alert=True,
        )
        return

    deleted = delete_review(
        review_id
    )

    if not deleted:
        await callback.answer(
            "Не вдалося видалити відгук.",
            show_alert=True,
        )
        return

    await safe_edit(
        callback,
        (
            "🗑 <b>Відгук видалено</b>\n\n"
            "Ви зможете залишити нову оцінку в будь-який момент."
        ),
        parse_mode="HTML",
        reply_markup=user_review_empty_keyboard(
            COURSE_ID
        ),
    )



@dp.callback_query(F.data.startswith("review_write:"))
async def review_write(callback: CallbackQuery, state: FSMContext):
    if callback.data is None or callback.message is None:
        return
    course_id = int(callback.data.split(":")[1])
    await state.update_data(review_course_id=course_id)
    await state.set_state(CourseReviewCreate.waiting_for_text)
    await callback.message.answer("✍️ Напишіть кілька слів про курс одним повідомленням.")
    await callback.answer()


@dp.message(
    CourseReviewCreate.waiting_for_text,
    F.text,
)
async def review_text_received(
    message: Message,
    state: FSMContext,
):
    if message.from_user is None or message.text is None:
        return

    text = message.text.strip()

    if len(text) < 3:
        await message.answer(
            "Відгук надто короткий. "
            "Напишіть хоча б 3 символи."
        )
        return

    if len(text) > 2000:
        await message.answer(
            "Відгук надто довгий. "
            "Максимальна довжина — 2000 символів."
        )
        return

    user = get_user_from_telegram(
        message.from_user
    )

    data = await state.get_data()

    course_id = int(
        data.get(
            "review_course_id",
            COURSE_ID,
        )
    )

    review = save_review_text(
        user.id,
        course_id,
        text,
    )

    await state.clear()

    if review is None:
        await message.answer(
            "Спочатку поставте оцінку курсу."
        )
        return

    await message.answer(
        (
            "❤️ <b>Дякуємо!</b>\n\n"
            "Ваш відгук збережено.\n\n"
            f"Оцінка: {'⭐' * review.rating}\n\n"
            f"Відгук:\n{html.escape(review.text or '')}"
        ),
        parse_mode="HTML",
        reply_markup=user_review_actions_keyboard(
            course_id=course_id,
            review_id=review.id,
        ),
    )


@dp.callback_query(F.data == "review_skip")
async def review_skip(callback: CallbackQuery):
    user = get_user_from_telegram(
        callback.from_user
    )

    has_course_access = user_has_active_course(
        user_id=user.id,
        course_id=COURSE_ID,
    )

    await safe_edit(
        callback,
        (
            "❤️ Дякуємо!\n\n"
            "Ви можете залишити або змінити відгук "
            "у будь-який момент через особистий кабінет."
        ),
        reply_markup=profile_courses_keyboard(
            has_course_access=has_course_access,
            is_admin=user.is_admin,
        ),
    )


@dp.callback_query(F.data.startswith("buy_course:"))

async def buy_course(callback: CallbackQuery):

    if callback.data is None:

        return

    course_id = int(callback.data.split(":")[1])

    if course_id != COURSE_ID:

        await callback.answer(

            "Курс не знайдено.",

            show_alert=True,

        )

        return

    course_lessons = [

        lesson

        for lesson in lessons

        if lesson.course_id == course_id

        and lesson.is_active

    ]

    await safe_edit(

        callback,

        (

            "🎓 ПРИДБАННЯ КУРСУ\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"📦 {COURSE_TITLE}\n\n"

            "Практичний навчальний курс для тих, хто хоче "

            "освоїти монтаж гіпсокартону з нуля та уникнути "

            "типових помилок.\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "📚 ЩО ВХОДИТЬ У КУРС\n\n"

            f"🎥 {len(course_lessons)} відеоуроків\n"

            "📄 PDF-матеріали до уроків\n"

            "♾ Довічний доступ\n"

            "🔄 Можливість повторного перегляду\n"

            "📢 Оновлення та новини курсу\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"💳 Вартість курсу: {COURSE_PRICE} грн\n\n"

            "Після успішної оплати курс автоматично "

            "з’явиться у вашому особистому кабінеті."

        ),

        reply_markup=buy_course_keyboard(course_id),

    )

@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    await show_profile(callback=callback)


@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None:
        return
    await safe_edit(
        callback,
        "👨\u200d💼 Панель администратора\n\nВыберите раздел:",
        reply_markup=admin_menu(),
    )


@dp.callback_query(F.data == "admin_courses")
async def admin_courses(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None:
        return
    await safe_edit(
        callback,
        "📚 Управление курсами\n\nВыберите курс:",
        reply_markup=admin_courses_keyboard(),
    )


# @dp.callback_query(F.data.startswith("create_payment:"))
#
# async def create_payment(callback: CallbackQuery):
#
#     if callback.data is None:
#
#         return
#
#     course_id = int(callback.data.split(":")[1])
#
#     if course_id != COURSE_ID:
#
#         await callback.answer(
#
#             "Курс не знайдено.",
#
#             show_alert=True,
#
#         )
#
#         return
#
#     await callback.answer(
#
#         "💳 Платіжна система зараз підключається.\n\n"
#
#         "Незабаром тут відкриватиметься безпечна "
#
#         "сторінка оплати LiqPay.",
#
#         show_alert=True,
#
#     )
#

# @dp.callback_query(F.data.startswith("create_payment:"))
# async def create_payment(callback: CallbackQuery):
#     if callback.data is None or callback.message is None:
#         return
#
#     user = get_user_from_telegram(
#         callback.from_user
#     )
#
#     course_id = int(
#         callback.data.split(":")[1]
#     )
#
#     if course_id != COURSE_ID:
#         await callback.answer(
#             "Курс не знайдено.",
#             show_alert=True,
#         )
#         return
#
#     if user.is_admin:
#         await safe_edit(
#             callback,
#             (
#                 "🧪 <b>ТЕСТОВИЙ ПЛАТІЖ</b>\n\n"
#                 "Ця кнопка імітує успішну оплату "
#                 "без списання коштів."
#             ),
#             parse_mode="HTML",
#             reply_markup=test_payment_keyboard(
#                 course_id
#             ),
#         )
#         return
#
#     await callback.answer(
#         "💳 Платіжна система зараз підключається.",
#         show_alert=True,
#     )

@dp.callback_query(F.data.startswith("create_payment:"))
async def create_payment(callback: CallbackQuery):
    if callback.data is None or callback.message is None:
        return

    user = get_user_from_telegram(
        callback.from_user
    )

    course_id = int(
        callback.data.split(":")[1]
    )

    if course_id != COURSE_ID:
        await callback.answer(
            "Курс не знайдено.",
            show_alert=True,
        )
        return

    # Тестовая оплата только для аккаунта Вики
    if user.telegram_id == 984614878:
        grant_course_access(
            user_id=user.id,
            course_id=course_id,
        )

        await send_purchase_success(
            telegram_id=user.telegram_id,
            course_title=COURSE_TITLE,
        )

        await callback.answer(
            "✅ Тестову оплату успішно проведено.",
            show_alert=True,
        )
        return

    await callback.answer(
        "💳 Платіжна система зараз підключається.\n\n"
        "Незабаром тут відкриватиметься "
        "безпечна сторінка оплати LiqPay.",
        show_alert=True,
    )




@dp.callback_query(F.data.startswith("admin_course:"))
async def admin_course(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None or callback.data is None:
        return
    course_id = int(callback.data.split(":")[1])
    course_lessons = [lesson for lesson in lessons if lesson.course_id == course_id]
    await safe_edit(
        callback,
        f"🎓 {COURSE_TITLE}\n\nЦена: {COURSE_PRICE} грн\nСтатус: активен\nУроков: {len(course_lessons)}",
        reply_markup=admin_course_keyboard(course_id),
    )


@dp.callback_query(

    F.data.startswith("test_payment_success:")

)

async def test_payment_success(

    callback: CallbackQuery,

):

    if callback.data is None:

        return

    user = get_user_from_telegram(

        callback.from_user

    )

    if not user.is_admin:

        await callback.answer(

            "⛔ Недостатньо прав.",

            show_alert=True,

        )

        return

    course_id = int(

        callback.data.split(":")[1]

    )

    grant_course_access(

        user_id=user.id,

        course_id=course_id,

    )

    await send_purchase_success(

        telegram_id=user.telegram_id,

        course_title=COURSE_TITLE,

    )

    await callback.answer(

        "Доступ успішно відкрито.",

        show_alert=True,

    )


@dp.callback_query(F.data.startswith("admin_course_lessons:"))
async def admin_course_lessons(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None or callback.data is None:
        return
    course_id = int(callback.data.split(":")[1])
    course_lessons = [lesson for lesson in lessons if lesson.course_id == course_id]
    await safe_edit(
        callback,
        "📖 Уроки курса\n\nВыберите урок:\n\n🎥 — видео загружено\n📄 — PDF загружен\n⚪️ — материал отсутствует",
        reply_markup=admin_lessons_keyboard(course_lessons, course_id),
    )


@dp.callback_query(F.data.startswith("admin_lesson_video:"))
async def admin_lesson_video(callback: CallbackQuery, state: FSMContext):
    user = await check_admin(callback)
    if user is None or callback.data is None or callback.message is None:
        return
    lesson_id = int(callback.data.split(":")[1])
    await state.update_data(lesson_id=lesson_id)
    await state.set_state(AdminLessonEdit.waiting_for_video)
    await callback.message.answer(
        "🎥 Отправьте видео для этого урока.\n\nПосле загрузки бот автоматически сохранит его."
    )


@dp.message(AdminLessonEdit.waiting_for_video)
async def save_admin_video(message: Message, state: FSMContext):
    if message.from_user is None:
        return

    user = get_user_from_telegram(message.from_user)

    if not user.is_admin:
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return

    video_file_id = None

    # Видео, отправленное обычным способом
    if message.video:
        video_file_id = message.video.file_id

    # Видео, отправленное как файл без сжатия
    elif message.document:
        filename = (message.document.file_name or "").lower()

        allowed_extensions = (
            ".mp4",
            ".mov",
            ".mkv",
            ".avi",
            ".m4v",
            ".webm",
        )

        if not filename.endswith(allowed_extensions):
            await message.answer(
                "❌ Отправленный файл не является видео.\n\n"
                "Поддерживаются: MP4, MOV, MKV, AVI, M4V, WEBM."
            )
            return

        video_file_id = message.document.file_id

    else:
        await message.answer(
            "❌ Отправьте видео обычным способом "
            "или как файл без потери качества."
        )
        return

    data = await state.get_data()
    lesson_id = data.get("lesson_id")

    if lesson_id is None:
        await message.answer("Не удалось определить урок.")
        await state.clear()
        return

    saved = update_lesson_video(
        lesson_id=int(lesson_id),
        video_file_id=video_file_id,
    )

    if not saved:
        await message.answer("Урок не найден.")
        await state.clear()
        return

    refresh_lessons()

    await message.answer(
        f"✅ Видео успешно сохранено.\n\n"
        f"Урок ID: {lesson_id}"
    )

    await state.clear()

@dp.callback_query(F.data.startswith("admin_lesson_pdf:"))
async def admin_lesson_pdf(callback: CallbackQuery, state: FSMContext):
    user = await check_admin(callback)
    if user is None or callback.data is None or callback.message is None:
        return
    lesson_id = int(callback.data.split(":")[1])
    await state.update_data(lesson_id=lesson_id)
    await state.set_state(AdminLessonEdit.waiting_for_pdf)
    await callback.message.answer("📄 Отправьте PDF-файл для этого урока.")


@dp.message(AdminLessonEdit.waiting_for_pdf, F.document)
async def save_admin_pdf(message: Message, state: FSMContext):
    if message.from_user is None or message.document is None:
        return
    user = get_user_from_telegram(message.from_user)
    if not user.is_admin:
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return
    file_name = message.document.file_name or ""
    is_pdf = (
        message.document.mime_type == "application/pdf"
        or file_name.lower().endswith(".pdf")
    )
    if not is_pdf:
        await message.answer("⚠️ Это не PDF. Отправьте файл формата .pdf.")
        return
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    if lesson_id is None:
        await message.answer("Не удалось определить урок.")
        await state.clear()
        return
    saved = update_lesson_pdf(
        lesson_id=int(lesson_id), pdf_file_id=message.document.file_id
    )
    if not saved:
        await message.answer("Урок не найден.")
        await state.clear()
        return
    refresh_lessons()
    await message.answer(f"✅ PDF успешно сохранён.\n\nУрок ID: {lesson_id}")
    await state.clear()


@dp.message(AdminLessonEdit.waiting_for_pdf)
async def wrong_admin_pdf(message: Message):
    await message.answer("Пожалуйста, отправьте PDF как файл.")


@dp.callback_query(F.data.startswith("admin_lesson_description:"))
async def admin_lesson_description(callback: CallbackQuery, state: FSMContext):
    user = await check_admin(callback)
    if user is None or callback.data is None or callback.message is None:
        return
    lesson_id = int(callback.data.split(":")[1])
    await state.update_data(lesson_id=lesson_id)
    await state.set_state(AdminLessonEdit.waiting_for_description)
    await callback.message.answer(
        "📝 Отправьте новое описание урока одним текстовым сообщением."
    )


@dp.message(AdminLessonEdit.waiting_for_description, F.text)
async def save_admin_description(message: Message, state: FSMContext):
    if message.from_user is None or message.text is None:
        return
    user = get_user_from_telegram(message.from_user)
    if not user.is_admin:
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return
    description = message.text.strip()
    if len(description) < 5:
        await message.answer("Описание слишком короткое. Введите хотя бы 5 символов.")
        return
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    if lesson_id is None:
        await message.answer("Не удалось определить урок.")
        await state.clear()
        return
    saved = update_lesson_description(lesson_id=int(lesson_id), description=description)
    if not saved:
        await message.answer("Урок не найден.")
        await state.clear()
        return
    refresh_lessons()
    await message.answer("✅ Описание урока обновлено.")
    await state.clear()


@dp.message(AdminLessonEdit.waiting_for_description)
async def wrong_admin_description(message: Message):
    await message.answer("Пожалуйста, отправьте описание обычным текстом.")


@dp.callback_query(F.data.startswith("admin_lesson_preview:"))
async def admin_lesson_preview(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None or callback.data is None:
        return
    lesson_id = int(callback.data.split(":")[1])
    lesson = get_lesson_by_id(lesson_id)
    if lesson is None:
        await callback.answer("Урок не найден.", show_alert=True)
        return
    await send_lesson(callback, lesson)


@dp.callback_query(F.data.startswith("admin_lesson:"))
async def admin_lesson(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None or callback.data is None:
        return
    lesson_id = int(callback.data.split(":")[1])
    lesson = get_lesson_by_id(lesson_id)
    if lesson is None:
        await callback.answer("Урок не найден.", show_alert=True)
        return
    video_status = "✅ загружено" if lesson.video_file_id else "❌ не загружено"
    pdf_status = "✅ загружено" if lesson.pdf_file_id else "❌ не загружено"
    await safe_edit(
        callback,
        f"📖 {lesson.title}\n\nПозиция: {lesson.position}\nВидео: {video_status}\nPDF: {pdf_status}\n\nОписание:\n{lesson.description or 'Описание не добавлено'}",
        reply_markup=admin_lesson_keyboard(lesson.id, lesson.course_id),
    )


@dp.callback_query(F.data == "admin_news")
async def admin_news(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None:
        return
    await safe_edit(
        callback,
        "📢 Управление новостями\n\nЗдесь можно создать объявление и отправить его активным ученикам.",
        reply_markup=admin_news_keyboard(),
    )


@dp.callback_query(F.data == "admin_news_create")
async def admin_news_create(callback: CallbackQuery, state: FSMContext):
    user = await check_admin(callback)
    if user is None or callback.message is None:
        return
    await state.clear()
    await state.set_state(AdminAnnouncementCreate.waiting_for_title)
    await callback.message.answer("📝 Введите заголовок новости.")


@dp.message(AdminAnnouncementCreate.waiting_for_title, F.text)
async def admin_news_title(message: Message, state: FSMContext):
    if message.text is None:
        return
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("Заголовок слишком короткий.")
        return
    await state.update_data(title=title)
    await state.set_state(AdminAnnouncementCreate.waiting_for_text)
    await message.answer("📄 Теперь отправьте текст новости.")


@dp.message(AdminAnnouncementCreate.waiting_for_text, F.text)
async def admin_news_text(message: Message, state: FSMContext):
    if message.text is None:
        return
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Текст новости слишком короткий.")
        return
    await state.update_data(text=text)
    await state.set_state(AdminAnnouncementCreate.waiting_for_image)
    await message.answer(
        "🖼 Отправьте одну картинку для новости.\n\nИли опубликуйте новость без изображения.",
        reply_markup=announcement_image_keyboard(),
    )


@dp.message(AdminAnnouncementCreate.waiting_for_image, F.photo)
async def admin_news_image(message: Message, state: FSMContext):
    if not message.photo:
        return
    data = await state.get_data()
    title = data.get("title")
    text = data.get("text")
    if not title or not text:
        await message.answer("Не удалось получить данные новости.")
        await state.clear()
        return
    image_file_id = message.photo[-1].file_id
    announcement = create_announcement(
        title=title, text=text, image_file_id=image_file_id
    )
    await state.clear()
    await message.answer_photo(
        photo=image_file_id,
        caption=f"📢 <b>Предпросмотр новости</b>\n\n<b>{announcement.title}</b>\n\n{announcement.text}",
        parse_mode="HTML",
        reply_markup=announcement_confirmation_keyboard(announcement.id),
    )


@dp.callback_query(F.data == "admin_news_without_image")
async def admin_news_without_image(callback: CallbackQuery, state: FSMContext):
    user = await check_admin(callback)
    if user is None or callback.message is None:
        return
    data = await state.get_data()
    title = data.get("title")
    text = data.get("text")
    if not title or not text:
        await callback.answer("Не удалось получить данные новости.", show_alert=True)
        await state.clear()
        return
    announcement = create_announcement(title=title, text=text, image_file_id=None)
    await state.clear()
    await callback.message.answer(
        f"📢 <b>Предпросмотр новости</b>\n\n<b>{announcement.title}</b>\n\n{announcement.text}",
        parse_mode="HTML",
        reply_markup=announcement_confirmation_keyboard(announcement.id),
    )


@dp.message(AdminAnnouncementCreate.waiting_for_image)
async def wrong_announcement_image(message: Message):
    await message.answer(
        "Отправьте изображение как фотографию или нажмите «Без изображения»."
    )


@dp.callback_query(F.data.startswith("admin_news_publish:"))
async def admin_news_publish(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None or callback.data is None or callback.message is None:
        return
    announcement_id = int(callback.data.split(":")[1])
    announcement = get_announcement(announcement_id)
    if announcement is None:
        await callback.answer("Новость не найдена.", show_alert=True)
        return
    published = publish_announcement(announcement_id)
    if not published:
        await callback.answer("Не удалось опубликовать новость.", show_alert=True)
        return
    telegram_ids = get_active_student_telegram_ids(course_id=COURSE_ID)
    delivered = 0
    failed = 0
    for telegram_id in telegram_ids:
        try:
            if announcement.image_file_id:
                await bot.send_photo(
                    chat_id=telegram_id,
                    photo=announcement.image_file_id,
                    caption=f"📢 <b>{html.escape(announcement.title)}</b>\n\n{html.escape(announcement.text)}",
                    parse_mode="HTML",
                    protect_content=True,
                )
            else:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=f"📢 <b>{html.escape(announcement.title)}</b>\n\n{html.escape(announcement.text)}",
                    parse_mode="HTML",
                    protect_content=True,
                )
            delivered += 1
        except Exception:
            failed += 1
    await callback.message.answer(
        f"✅ Новость опубликована.\n\nДоставлено: {delivered}\nОшибок: {failed}"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_news_cancel:"))
async def admin_news_cancel(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None:
        return
    await safe_edit(
        callback, "❌ Публикация отменена.", reply_markup=admin_news_keyboard()
    )


@dp.callback_query(F.data == "admin_news_history")
async def admin_news_history(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None:
        return
    announcements = get_published_announcements()
    if not announcements:
        text = "📋 Опубликованных новостей пока нет."
    else:
        parts = ["📋 История новостей\n"]
        for announcement in announcements[:10]:
            parts.append(f"• {announcement.title}")
        text = "\n".join(parts)
    await safe_edit(callback, text, reply_markup=admin_news_keyboard())




@dp.callback_query(F.data == "admin_students")
async def show_admin_students(
    callback: CallbackQuery,
    page: int = 1,
) -> None:
    page_size = 10
    total_users = get_users_count()

    total_pages = max(
        1,
        (total_users + page_size - 1) // page_size,
    )

    page = max(
        1,
        min(page, total_pages),
    )

    offset = (page - 1) * page_size

    users = get_all_users(
        limit=page_size,
        offset=offset,
    )

    purchased_count = 0
    started_count = 0
    completed_count = 0

    for student in users:
        if user_has_active_course(
            user_id=student.id,
            course_id=COURSE_ID,
        ):
            purchased_count += 1

            progress = get_course_progress(
                user_id=student.id,
                course_id=COURSE_ID,
            )

            if progress["completed"] > 0:
                started_count += 1

            if (
                progress["total"] > 0
                and progress["completed"] >= progress["total"]
            ):
                completed_count += 1

    await safe_edit(
        callback,
        (
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👥 <b>УЧНІ ПЛАТФОРМИ</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Усього користувачів: <b>{total_users}</b>\n"
            f"📄 Поточна сторінка: <b>{page}/{total_pages}</b>\n\n"
            "На цій сторінці:\n"
            f"💳 Придбали курс: <b>{purchased_count}</b>\n"
            f"🎓 Почали навчання: <b>{started_count}</b>\n"
            f"🏆 Завершили курс: <b>{completed_count}</b>\n\n"
            "Оберіть користувача:"
        ),
        parse_mode="HTML",
        reply_markup=admin_students_keyboard(
            users=users,
            page=page,
            total_users=total_users,
            page_size=page_size,
        ),
    )

@dp.callback_query(F.data == "admin_students")
async def admin_students(
    callback: CallbackQuery,
):
    user = await check_admin(callback)

    if user is None:
        return

    await show_admin_students(
        callback,
        page=1,
    )

@dp.callback_query(
    F.data.startswith("admin_students_page:")
)
async def admin_students_page(
    callback: CallbackQuery,
):
    user = await check_admin(callback)

    if user is None or callback.data is None:
        return

    page = int(
        callback.data.split(":")[1]
    )

    await show_admin_students(
        callback,
        page=page,
    )

@dp.callback_query(
    F.data == "admin_students_page_info"
)
async def admin_students_page_info(
    callback: CallbackQuery,
):
    await callback.answer(
        "Поточна сторінка списку учнів."
    )

@dp.callback_query(
    F.data.startswith("admin_student:")
)
async def admin_student(
    callback: CallbackQuery,
):
    admin = await check_admin(callback)

    if admin is None or callback.data is None:
        return

    parts = callback.data.split(":")

    student_id = int(parts[1])

    page = (
        int(parts[2])
        if len(parts) > 2
        else 1
    )

    student = get_user_by_id(
        student_id
    )

    if student is None:
        await callback.answer(
            "Користувача не знайдено.",
            show_alert=True,
        )
        return

    has_course_access = user_has_active_course(
        user_id=student.id,
        course_id=COURSE_ID,
    )

    full_name = " ".join(
        part
        for part in [
            student.first_name,
            student.last_name,
        ]
        if part
    ).strip()

    if not full_name:
        full_name = "Ім’я не вказано"

    username_line = (
        f"🔗 Username: @{html.escape(student.username)}"
        if student.username
        else "🔗 Username: не вказано"
    )

    role_line = (
        "👨‍💼 Роль: адміністратор"
        if student.is_admin
        else "👤 Роль: учень"
    )

    if has_course_access:
        progress = get_course_progress(
            user_id=student.id,
            course_id=COURSE_ID,
        )

        progress_bar = build_progress_bar(
            progress["completed"],
            progress["total"],
        )

        if (
            progress["total"] > 0
            and progress["completed"] >= progress["total"]
        ):
            course_status = "🏆 Курс завершено"
        elif progress["completed"] > 0:
            course_status = "🎓 Навчання розпочато"
        else:
            course_status = "⏳ Навчання ще не розпочато"

        course_block = (
            "✅ Доступ до курсу: активний\n\n"
            f"{progress_bar}\n"
            f"📈 Прогрес: <b>{progress['percent']}%</b>\n"
            f"✅ Завершено уроків: "
            f"<b>{progress['completed']} із {progress['total']}</b>\n"
            f"{course_status}"
        )
    else:
        course_block = (
            "❌ Доступ до курсу: відсутній\n\n"
            "Користувач ще не придбав курс."
        )

    review = get_user_review(
        student.id,
        COURSE_ID,
    )

    if review is None:
        review_block = "⭐ Оцінка курсу: не залишена"
    else:
        review_block = (
            f"⭐ Оцінка курсу: {'⭐' * review.rating}"
        )

    await safe_edit(
        callback,
        (
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 <b>КАРТКА УЧНЯ</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Ім’я: <b>{html.escape(full_name)}</b>\n"
            f"{username_line}\n"
            f"🆔 Telegram ID: "
            f"<code>{student.telegram_id}</code>\n"
            f"🗄 ID у базі: <code>{student.id}</code>\n"
            f"{role_line}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 <b>{html.escape(COURSE_TITLE)}</b>\n\n"
            f"{course_block}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{review_block}"
        ),
        parse_mode="HTML",
        reply_markup=admin_student_keyboard(
            student_id=student.id,
            has_course_access=has_course_access,
            page=page,
        ),
    )

@dp.callback_query(
    F.data.startswith("admin_grant_course:")
)
async def admin_grant_course(
    callback: CallbackQuery,
):
    admin = await check_admin(callback)

    if admin is None or callback.data is None:
        return

    parts = callback.data.split(":")

    student_id = int(parts[1])

    page = (
        int(parts[2])
        if len(parts) > 2
        else 1
    )

    student = get_user_by_id(
        student_id
    )

    if student is None:
        await callback.answer(
            "Користувача не знайдено.",
            show_alert=True,
        )
        return

    if user_has_active_course(
        user_id=student.id,
        course_id=COURSE_ID,
    ):
        await callback.answer(
            "У користувача вже є доступ до курсу.",
            show_alert=True,
        )
        return

    purchase = grant_course_access(
        user_id=student.id,
        course_id=COURSE_ID,
    )

    if purchase is None:
        await callback.answer(
            "Не вдалося видати доступ.",
            show_alert=True,
        )
        return

    try:
        await send_purchase_success(
            telegram_id=student.telegram_id,
            course_title=COURSE_TITLE,
        )

        notification_text = (
            "Доступ видано. Користувачу надіслано повідомлення."
        )
    except Exception:
        notification_text = (
            "Доступ видано, але повідомлення користувачу "
            "не вдалося доставити."
        )

    await callback.answer(
        notification_text,
        show_alert=True,
    )

    callback.data = (
        f"admin_student:{student.id}:{page}"
    )

    await admin_student(
        callback
    )


@dp.callback_query(F.data == "admin_reviews")
async def admin_reviews(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None:
        return
    summary = get_review_summary()
    await safe_edit(
        callback,
        f"⭐ <b>ВІДГУКИ</b>\n\n🆕 Нових: {summary['unread']}\n📝 Усього: {summary['total']}\n⭐ Середня оцінка: {summary['average']}",
        parse_mode="HTML",
        reply_markup=admin_reviews_keyboard(),
    )


async def show_admin_reviews(callback: CallbackQuery, only_new: bool):
    rows = get_reviews(status="new" if only_new else None, limit=20)
    title = "🆕 Нові відгуки" if only_new else "📚 Усі відгуки"
    await safe_edit(callback, f"{title}\n\nЗнайдено: {len(rows)}", reply_markup=admin_reviews_keyboard())
    if callback.message is None:
        return
    if not rows:
        await callback.message.answer("Відгуків у цьому розділі немає.")
        return
    for review, review_user in rows:
        name = " ".join(part for part in [review_user.first_name, review_user.last_name] if part) or "Користувач"
        username = f"@{review_user.username}" if review_user.username else "без username"
        text = html.escape(review.text) if review.text else "Текст не залишено"
        await callback.message.answer(
            f"{'⭐' * review.rating}\n\n<b>{html.escape(name)}</b>\n{html.escape(username)}\n\n{text}\n\nСтатус: {review.status}",
            parse_mode="HTML",
            reply_markup=review_admin_actions(review.id),
        )


@dp.callback_query(F.data == "admin_reviews_new")
async def admin_reviews_new(callback: CallbackQuery):
    if await check_admin(callback) is not None:
        await show_admin_reviews(callback, only_new=True)


@dp.callback_query(F.data == "admin_reviews_all")
async def admin_reviews_all(callback: CallbackQuery):
    if await check_admin(callback) is not None:
        await show_admin_reviews(callback, only_new=False)


@dp.callback_query(F.data.startswith("admin_review_read:"))
async def admin_review_read(callback: CallbackQuery):
    if await check_admin(callback) is None or callback.data is None:
        return
    review_id = int(callback.data.split(":")[1])
    mark_review_read(review_id)
    await callback.answer("Відгук позначено як прочитаний.", show_alert=True)


@dp.callback_query(F.data.startswith("admin_review_delete:"))
async def admin_review_delete(callback: CallbackQuery):
    if await check_admin(callback) is None or callback.data is None:
        return
    review_id = int(callback.data.split(":")[1])
    deleted = delete_review(review_id)
    await callback.answer("Відгук видалено." if deleted else "Відгук не знайдено.", show_alert=True)
    if deleted and callback.message is not None:
        await callback.message.delete()


@dp.callback_query(F.data == "admin_statistics")
async def admin_statistics(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None:
        return
    stats = get_platform_statistics(COURSE_ID, COURSE_PRICE)
    await safe_edit(
        callback,
        "📊 <b>СТАТИСТИКА ПЛАТФОРМИ</b>\n\n"
        f"👥 Користувачів: <b>{stats['users_total']}</b>\n"
        f"💳 Активних покупок: <b>{stats['active_purchases']}</b>\n"
        f"💰 Розрахунковий дохід: <b>{stats['income']} грн</b>\n\n"
        f"🎓 Розпочали курс: <b>{stats['started']}</b>\n"
        f"🏆 Завершили курс: <b>{stats['completed']}</b>\n"
        f"📈 Середній прогрес: <b>{stats['average_progress']}%</b>\n\n"
        f"⭐ Середня оцінка: <b>{stats['average_rating']}</b>\n"
        f"📝 Відгуків: <b>{stats['review_total']}</b>\n"
        f"🔔 Нових відгуків: <b>{stats['unread_reviews']}</b>\n\n"
        "ℹ️ До підключення LiqPay дохід рахується як кількість активних покупок × ціна курсу.",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
