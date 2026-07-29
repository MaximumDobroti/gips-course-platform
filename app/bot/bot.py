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

from app.bot.services.course_service import (

    create_course_with_lessons,

    delete_course,

    delete_lesson,

    get_all_courses,

    get_course_by_id,

    update_course_price,

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
from app.bot.services.payment_request_service import (
    confirm_payment_request,
    count_submitted_payment_requests,
    create_payment_request,
    get_payment_request,
    get_payment_requests,
    reject_payment_request,
    submit_receipt,
)
from app.bot.services.statistics_service import get_platform_statistics
from app.database.database import Base, engine

Base.metadata.create_all(bind=engine)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    raise RuntimeError("BOT_TOKEN is not set in .env")

PAYMENT_CARD_NUMBER = os.getenv("PAYMENT_CARD_NUMBER", "").strip()
PAYMENT_CARD_HOLDER = os.getenv("PAYMENT_CARD_HOLDER", "").strip()
PAYMENT_IBAN = os.getenv("PAYMENT_IBAN", "").strip()
PAYMENT_RECIPIENT = os.getenv("PAYMENT_RECIPIENT", "").strip()
PAYMENT_EDRPOU = os.getenv("PAYMENT_EDRPOU", "").strip()

COURSE_ID = 1

COURSE_TITLE = "Теоретичний курс по Монтажу гіпсокартону з нуля"

COURSE_PRICE = 1000

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
lessons = get_all_lessons()


class AdminLessonEdit(StatesGroup):
    waiting_for_video = State()
    waiting_for_pdf = State()
    waiting_for_title = State()
    waiting_for_description = State()

class AdminCourseCreate(StatesGroup):

    waiting_for_title = State()

    waiting_for_lessons_count = State()

    waiting_for_lesson_title = State()

    waiting_for_price = State()

    waiting_for_confirmation = State()

class AdminCourseEdit(StatesGroup):

    waiting_for_price = State()



class AdminAnnouncementCreate(StatesGroup):
    waiting_for_title = State()
    waiting_for_text = State()
    waiting_for_image = State()


class CourseReviewCreate(StatesGroup):
    waiting_for_text = State()


class ManualPaymentReceipt(StatesGroup):
    waiting_for_receipt = State()


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

        callback_data="profile",

    )

    keyboard.button(

        text="👤 Особистий кабінет",

        callback_data="profile",

    )

    keyboard.adjust(1)

    return keyboard.as_markup()

def admin_course_delete_confirmation_keyboard(
    course_id: int,
):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🗑 Да, удалить курс",
        callback_data=(
            f"admin_course_delete_confirm:{course_id}"
        ),
    )

    keyboard.button(
        text="❌ Отмена",
        callback_data=f"admin_course:{course_id}",
    )

    keyboard.adjust(1)

    return keyboard.as_markup()


def admin_lesson_delete_confirmation_keyboard(
    lesson_id: int,
    course_id: int,
):
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="🗑 Да, удалить урок",
        callback_data=(
            f"admin_lesson_delete_confirm:{lesson_id}"
        ),
    )

    keyboard.button(
        text="❌ Отмена",
        callback_data=f"admin_lesson:{lesson_id}",
    )

    keyboard.button(
        text="⬅️ К урокам",
        callback_data=(
            f"admin_course_lessons:{course_id}"
        ),
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


def admin_course_create_cancel_keyboard():
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="❌ Отменить создание",
        callback_data="admin_course_create_cancel",
    )

    keyboard.adjust(1)

    return keyboard.as_markup()

def admin_course_create_confirmation_keyboard():
    keyboard = InlineKeyboardBuilder()

    keyboard.button(
        text="✅ Создать курс",
        callback_data="admin_course_create_confirm",
    )

    keyboard.button(
        text="❌ Отменить",
        callback_data="admin_course_create_cancel",
    )

    keyboard.adjust(1)

    return keyboard.as_markup()


def get_lesson_by_id(lesson_id: int):
    return next((lesson for lesson in lessons if lesson.id == lesson_id), None)


def get_lesson_by_position(position: int, course_id: int | None = None):
    return next(
        (
            lesson
            for lesson in lessons
            if lesson.position == position
            and (course_id is None or lesson.course_id == course_id)
        ),
        None,
    )


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


async def check_course_access(callback: CallbackQuery, course_id: int):
    user = get_user_from_telegram(callback.from_user)
    course = get_course_by_id(course_id)
    if course is None or not course.is_active:
        await callback.answer("Курс не знайдено.", show_alert=True)
        return None
    if not user_has_active_course(user.id, course_id):
        await callback.answer(
            "🔒 Цей курс ще не придбано. Відкрийте особистий кабінет та натисніть «Придбати курс».",
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
    telegram_user = callback.from_user if callback else message.from_user if message else None
    if telegram_user is None:
        return

    user = get_user_from_telegram(telegram_user)
    courses = [c for c in get_all_courses() if c.is_active and c.is_visible]
    blocks = []

    for course in courses:
        course_lessons = [l for l in lessons if l.course_id == course.id and l.is_active]
        if user_has_active_course(user.id, course.id):
            progress = get_course_progress(user.id, course.id)
            next_lesson = get_next_available_lesson(user.id, course.id)
            status = "🏆 Курс успішно завершено" if next_lesson is None else f"▶️ Наступний урок: {next_lesson.position}. {next_lesson.title}"
            blocks.append(
                "🟢 <b>ДОСТУПНИЙ КУРС</b>\n\n"
                f"📦 <b>{html.escape(course.title)}</b>\n\n"
                f"{build_progress_bar(progress['completed'], progress['total'])}\n"
                f"Прогрес: {progress['percent']}%\n\n"
                f"✅ Завершено: {progress['completed']} із {progress['total']} уроків\n"
                f"{html.escape(status)}"
            )
        else:
            price = "🎁 Безкоштовно" if course.is_free or course.price == 0 else f"💳 Вартість: {course.price} грн"
            subtitle = f"\n{html.escape(course.subtitle)}\n" if course.subtitle else ""
            blocks.append(
                "🔒 <b>КУРС НЕ ПРИДБАНО</b>\n\n"
                f"📦 <b>{html.escape(course.title)}</b>\n"
                f"{subtitle}\n"
                f"🎥 {len(course_lessons)} відеоуроків\n"
                "📄 PDF-матеріали\n♾ Довічний доступ\n\n"
                f"{price}"
            )

    courses_text = "\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n".join(blocks) if blocks else (
        "📚 <b>КУРСІВ ПОКИ НЕМАЄ</b>\n\nНові курси з’являться тут одразу після публікації."
    )
    username = f"🔗 @{user.username}\n" if user.username else ""
    text = (
        "👤 <b>ОСОБИСТИЙ КАБІНЕТ</b>\n\n"
        f"Вітаємо, {html.escape(user.first_name or 'учню')} 👋\n{username}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n📊 <b>ВАША СТАТИСТИКА</b>\n\n"
        f"🎓 Придбано курсів: {get_purchased_courses_count(user.id)}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{courses_text}"
    )
    keyboard = profile_courses_keyboard(user.id, courses, user.is_admin)
    if callback:
        await safe_edit(callback, text, reply_markup=keyboard, parse_mode="HTML")
    elif message:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

def main_menu(is_admin: bool = False):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📢 Новости", callback_data="student_news")
    keyboard.button(text="📚 Мої курси", callback_data="profile")
    keyboard.button(text="👤 Мой профиль", callback_data="profile")
    if is_admin:
        keyboard.button(text="👨\u200d💼 Админ-панель", callback_data="admin_panel")
    keyboard.adjust(1)
    return keyboard.as_markup()

def profile_courses_keyboard(user_id: int, courses, is_admin: bool = False):
    keyboard = InlineKeyboardBuilder()
    for course in courses:
        title = course.title[:30] + ("…" if len(course.title) > 30 else "")
        if user_has_active_course(user_id, course.id):
            keyboard.button(text=f"▶️ Продовжити: {title}", callback_data=f"start_learning:{course.id}")
            keyboard.button(text=f"📚 Програма: {title}", callback_data=f"lessons:{course.id}")
            keyboard.button(text=f"⭐ Відгук: {title}", callback_data=f"profile_review:{course.id}")
        else:
            price = "безкоштовно" if course.is_free or course.price == 0 else f"{course.price} грн"
            keyboard.button(text=f"💳 Придбати: {title} — {price}", callback_data=f"buy_course:{course.id}")
    keyboard.button(text="📢 Новини", callback_data="student_news")
    if is_admin:
        keyboard.button(text="👨‍💼 Панель адміністратора", callback_data="admin_panel")
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
        callback_data=f"user_review_delete:{course_id}:{review_id}",
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




def lesson_only_keyboard(lesson):
    keyboard = InlineKeyboardBuilder()
    course_lessons = [l for l in lessons if l.course_id == lesson.course_id and l.is_active]
    keyboard.button(
        text="🏁 Завершити курс" if lesson.position >= len(course_lessons) else "✅ Завершити урок",
        callback_data=f"complete:{lesson.id}",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()


def announcement_image_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⏭ Без изображения", callback_data="admin_news_without_image")
    keyboard.button(text="❌ Отмена", callback_data="admin_news")
    keyboard.adjust(1)
    return keyboard.as_markup()


def navigation_keyboard(course_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📚 Програма курсу", callback_data=f"lessons:{course_id}")
    keyboard.button(text="👤 Особистий кабінет", callback_data="profile")
    keyboard.adjust(1)
    return keyboard.as_markup()


def lesson_keyboard(lesson):

    keyboard = InlineKeyboardBuilder()

    keyboard.button(

        text="▶️ Відкрити наступний урок",

        callback_data=f"open_lesson:{lesson.id}",

    )

    keyboard.button(

        text="📚 Всі уроки",

        callback_data=f"lessons:{lesson.course_id}",

    )

    keyboard.adjust(1)

    return keyboard.as_markup()



# def lessons_list_keyboard(course_lessons, completed_lesson_ids: set[int], available_lesson_id: int | None):
#     keyboard = InlineKeyboardBuilder()
#     for lesson in course_lessons:
#         if lesson.id in completed_lesson_ids:
#             text, data = f"✅ {lesson.position}. {lesson.title}", f"open_lesson:{lesson.id}"
#         elif lesson.id == available_lesson_id:
#             text, data = f"▶️ {lesson.position}. {lesson.title}", f"open_lesson:{lesson.id}"
#         else:
#             text, data = f"🔒 {lesson.position}. {lesson.title}", f"locked_lesson:{lesson.id}"
#         keyboard.button(text=text, callback_data=data)
#     keyboard.button(text="⬅️ До особистого кабінету", callback_data="profile")
#     keyboard.adjust(1)
#     return keyboard.as_markup()


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
    pending_payments = count_submitted_payment_requests()
    payments_label = f"💳 Оплати ({pending_payments})" if pending_payments else "💳 Оплати"
    keyboard.button(text=payments_label, callback_data="admin_payments")
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
    courses,
    page: int = 1,
):
    keyboard = InlineKeyboardBuilder()

    access_buttons_count = 0

    for course in courses:
        has_access = user_has_active_course(
            user_id=student_id,
            course_id=course.id,
        )

        if has_access:
            continue

        short_title = course.title

        if len(short_title) > 28:
            short_title = short_title[:28] + "…"

        keyboard.button(
            text=f"🔓 Видати доступ: {short_title}",
            callback_data=(
                f"admin_grant_course:"
                f"{student_id}:"
                f"{course.id}:"
                f"{page}"
            ),
        )

        access_buttons_count += 1

    if courses and access_buttons_count == 0:
        keyboard.button(
            text="✅ Доступ до всіх курсів видано",
            callback_data="admin_student_all_courses_access",
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



def admin_courses_keyboard(courses):
    keyboard = InlineKeyboardBuilder()

    for course in courses:
        visibility_icon = (
            "🟢"
            if course.is_visible and course.is_active
            else "⚪️"
        )

        keyboard.button(
            text=(
                f"{visibility_icon} "
                f"{course.position}. {course.title}"
            ),
            callback_data=f"admin_course:{course.id}",
        )

    keyboard.button(
        text="➕ Добавить курс",
        callback_data="admin_course_create",
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
        text="💰 Изменить цену",
        callback_data=f"admin_course_price:{course_id}",
    )
    keyboard.button(

        text="🗑 Удалить курс",

        callback_data=f"admin_course_delete:{course_id}",

    )

    keyboard.button(
        text="⬅️ К курсам",
        callback_data="admin_courses",
    )

    keyboard.adjust(1)

    return keyboard.as_markup()



def payment_method_keyboard(course_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="💳 Оплатити на картку", callback_data=f"payment_method:{course_id}:card")
    keyboard.button(text="🏦 Оплатити за IBAN", callback_data=f"payment_method:{course_id}:iban")
    keyboard.button(text="⬅️ Назад", callback_data=f"buy_course:{course_id}")
    keyboard.adjust(1)
    return keyboard.as_markup()


def payment_details_keyboard(request_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Я оплатив", callback_data=f"payment_paid:{request_id}")
    keyboard.button(text="⬅️ До особистого кабінету", callback_data="profile")
    keyboard.adjust(1)
    return keyboard.as_markup()


# def admin_payments_keyboard(requests):
#     keyboard = InlineKeyboardBuilder()
#     for payment in requests:
#         keyboard.button(
#             text=f"🟠 Заявка #{payment.id} — {payment.amount} грн",
#             callback_data=f"admin_payment:{payment.id}",
#         )
#     keyboard.button(text="🔄 Оновити", callback_data="admin_payments")
#     keyboard.button(text="⬅️ Назад", callback_data="admin_panel")
#     keyboard.adjust(1)
#     return keyboard.as_markup()

def admin_payments_keyboard(requests):

    keyboard = InlineKeyboardBuilder()

    for payment in requests:

        payment_code = f"PAY-{payment.id:06d}"

        keyboard.button(

            text=(

                f"🟠 #{payment.id} · "

                f"{payment_code} · "

                f"{payment.amount} грн"

            ),

            callback_data=f"admin_payment:{payment.id}",

        )

    keyboard.button(

        text="🔄 Оновити",

        callback_data="admin_payments",

    )

    keyboard.button(

        text="⬅️ Назад",

        callback_data="admin_panel",

    )

    keyboard.adjust(1)

    return keyboard.as_markup()


def admin_payment_actions_keyboard(request_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Підтвердити оплату", callback_data=f"admin_payment_confirm:{request_id}")
    keyboard.button(text="❌ Відхилити", callback_data=f"admin_payment_reject:{request_id}")
    keyboard.button(text="⬅️ До оплат", callback_data="admin_payments")
    keyboard.adjust(1)
    return keyboard.as_markup()


def buy_course_keyboard(course):
    keyboard = InlineKeyboardBuilder()
    price = "безкоштовно" if course.is_free or course.price == 0 else f"{course.price} грн"
    keyboard.button(text=f"💳 Оплатити {price}", callback_data=f"create_payment:{course.id}")
    keyboard.button(text="⬅️ Повернутися до кабінету", callback_data="profile")
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

        text="🗑 Удалить урок",

        callback_data=(

            f"admin_lesson_delete:{lesson_id}"

        ),

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

# async def send_lesson(callback: CallbackQuery, lesson):
#
#     if callback.message is None:
#         return
#
#     caption = (
#         "━━━━━━━━━━━━━━━━━━━━━━\n\n"
#         f"🎥 УРОК {lesson.position}\n\n"
#         f"📖 <b>{lesson.title}</b>\n\n"
#         "━━━━━━━━━━━━━━━━━━━━━━\n\n"
#         f"{lesson.description or 'Опис уроку ще не додано.'}\n\n"
#         "━━━━━━━━━━━━━━━━━━━━━━\n\n"
#         "✅ Після перегляду уроку натисніть кнопку\n"
#         "<b>«Завершити урок»</b>, щоб відкрити наступний."
#     )
#
#     if lesson.video_file_id:
#
#         await callback.message.answer_video(
#             video=lesson.video_file_id,
#             caption=caption,
#             parse_mode="HTML",
#             protect_content=True,
#             reply_markup=lesson_only_keyboard(lesson),
#         )
#
#     else:
#
#         await callback.message.answer(
#             caption
#             + "\n\n⚠️ Відео ще не завантажено.",
#             parse_mode="HTML",
#             protect_content=True,
#             reply_markup=lesson_only_keyboard(lesson),
#         )
#
#     await callback.message.answer(
#         "📚 <b>Навігація</b>",
#         parse_mode="HTML",
#         reply_markup=navigation_keyboard(lesson.course_id),
#     )
#

async def send_lesson(
    callback: CallbackQuery,
    lesson,
):
    if callback.message is None:
        return

    description = (
        lesson.description.strip()
        if lesson.description
        else ""
    )

    if description:
        topics = [
            line.strip().rstrip(".")
            for line in description.splitlines()
            if line.strip()
        ]

        topics_text = "\n".join(
            f"• {html.escape(topic)}"
            for topic in topics
        )
    else:
        topics_text = (
            "• Опис уроку ще не додано"
        )

    caption = (
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎥 УРОК {lesson.position}\n\n"
        f"📖 <b>{html.escape(lesson.title)}</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 <b>У цьому уроці ви дізнаєтесь:</b>\n\n"
        f"{topics_text}\n\n"
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
                lesson
            ),
        )
    else:
        await callback.message.answer(
            caption
            + "\n\n⚠️ Відео ще не завантажено.",
            parse_mode="HTML",
            protect_content=True,
            reply_markup=lesson_only_keyboard(
                lesson
            ),
        )

    if lesson.pdf_file_id:
        await callback.message.answer_document(
            document=lesson.pdf_file_id,
            caption=(
                "📄 <b>PDF-МАТЕРІАЛИ ДО УРОКУ</b>\n\n"
                f"Урок {lesson.position}. "
                f"{html.escape(lesson.title)}"
            ),
            parse_mode="HTML",
            protect_content=True,
        )

    await callback.message.answer(
        "📚 <b>Навігація</b>",
        parse_mode="HTML",
        reply_markup=navigation_keyboard(
            lesson.course_id
        ),
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
                user.id,
                [c for c in get_all_courses() if c.is_active and c.is_visible],
                user.is_admin,
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

    await callback.message.answer(
        "Оберіть подальшу дію:",
        reply_markup=profile_courses_keyboard(
            user.id,
            [c for c in get_all_courses() if c.is_active and c.is_visible],
            user.is_admin,
        ),
    )

    await callback.answer()



@dp.callback_query(F.data.startswith("start_learning:"))
async def start_learning(callback: CallbackQuery):
    if callback.data is None:
        return
    course_id = int(callback.data.split(":")[1])
    user = await check_course_access(callback, course_id)
    if user is None:
        return
    lesson = get_next_available_lesson(user.id, course_id)
    if lesson is None:
        await callback.answer("🎉 Ви вже пройшли весь курс!", show_alert=True)
        return
    await send_lesson(callback, lesson)


@dp.callback_query(F.data.startswith("lessons:"))
async def show_lessons(callback: CallbackQuery):
    if callback.data is None:
        return
    course_id = int(callback.data.split(":")[1])
    user = await check_course_access(callback, course_id)
    if user is None:
        return
    course = get_course_by_id(course_id)
    course_lessons = sorted(
        [l for l in lessons if l.course_id == course_id and l.is_active],
        key=lambda l: (l.position, l.id),
    )
    completed_ids = get_completed_lesson_ids(user.id, course_id)
    next_lesson = get_next_available_lesson(user.id, course_id)
    progress = get_course_progress(user.id, course_id)
    await safe_edit(
        callback,
        "━━━━━━━━━━━━━━━━━━━━━━\n\n📚 <b>ПРОГРАМА КУРСУ</b>\n\n"
        f"<b>{html.escape(course.title)}</b>\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Прогрес: {progress['percent']}%\nЗавершено: {progress['completed']} із {progress['total']} уроків\n\n"
        "✅ — завершено\n▶️ — доступно зараз\n🔒 — ще закрито\n\nОберіть потрібний урок:",
        parse_mode="HTML",
        reply_markup=lessons_list_keyboard(course_lessons, completed_ids, next_lesson.id if next_lesson else None),
    )

@dp.callback_query(

    F.data == "admin_student_all_courses_access"

)

async def admin_student_all_courses_access(

    callback: CallbackQuery,

):

    await callback.answer(

        "Користувач уже має доступ до всіх курсів.",

        show_alert=True,

    )


@dp.callback_query(F.data.startswith("open_lesson:"))
async def open_lesson(callback: CallbackQuery):
    if callback.data is None:
        return
    lesson = get_lesson_by_id(int(callback.data.split(":")[1]))
    if lesson is None:
        await callback.answer("Урок не знайдено.", show_alert=True)
        return
    user = await check_course_access(callback, lesson.course_id)
    if user is None:
        return
    if not is_lesson_available(user.id, lesson.id) and not is_lesson_completed(user.id, lesson.id):
        await callback.answer("🔒 Спочатку пройдіть попередній урок.", show_alert=True)
        return
    await send_lesson(callback, lesson)


@dp.callback_query(F.data.startswith("locked_lesson:"))
async def locked_lesson(callback: CallbackQuery):
    await callback.answer("🔒 Цей урок поки що закритий. Спочатку завершіть попередній урок.", show_alert=True)


@dp.callback_query(F.data.startswith("complete:"))
async def complete_lesson(callback: CallbackQuery):
    if callback.data is None or callback.message is None:
        return
    lesson = get_lesson_by_id(int(callback.data.split(":")[1]))
    if lesson is None:
        await callback.answer("Урок не знайдено.", show_alert=True)
        return
    user = await check_course_access(callback, lesson.course_id)
    if user is None:
        return
    if is_lesson_completed(user.id, lesson.id):
        await callback.answer("✅ Цей урок уже пройдено.", show_alert=True)
        return
    if not is_lesson_available(user.id, lesson.id):
        await callback.answer("🔒 Спочатку пройдіть попередній урок.", show_alert=True)
        return
    if not mark_lesson_completed(user.id, lesson.id):
        await callback.answer("Не вдалося зберегти прогрес.", show_alert=True)
        return

    course = get_course_by_id(lesson.course_id)
    next_lesson = get_next_available_lesson(user.id, lesson.course_id)
    if next_lesson is None:
        await callback.message.answer(
            "━━━━━━━━━━━━━━━━━━━━━━\n\n🏆 <b>Курс завершено!</b>\n\n"
            f"Вітаємо! Ви успішно завершили курс\n\n<b>{html.escape(course.title)}</b>\n\n━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML",
        )
        if get_user_review(user.id, lesson.course_id) is None:
            await callback.message.answer(
                "⭐ <b>Будемо вдячні за вашу оцінку</b>\n\nВи можете оцінити курс зараз або пізніше.",
                parse_mode="HTML",
                reply_markup=review_after_course_keyboard(lesson.course_id),
            )
        else:
            await callback.message.answer("❤️ Дякуємо за проходження курсу!", reply_markup=None)
        return

    await callback.message.answer(
        "━━━━━━━━━━━━━━━━━━━━━━\n\n🎉 <b>Вітаємо!</b>\n\nУрок успішно завершено.\n\n"
        f"🔓 Відкрито новий урок\n\n📖 <b>{html.escape(next_lesson.title)}</b>\n\n━━━━━━━━━━━━━━━━━━━━━━",
        parse_mode="HTML",
        reply_markup=lesson_keyboard(next_lesson),
    )


@dp.callback_query(F.data.startswith("profile_review:"))
async def profile_review(callback: CallbackQuery):
    if callback.data is None:
        return

    course_id = int(callback.data.split(":")[1])
    user = await check_course_access(callback, course_id)
    if user is None:
        return
    course = get_course_by_id(course_id)

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
                f"📦 <b>{html.escape(course.title)}</b>\n\n"
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
            f"📦 <b>{html.escape(course.title)}</b>\n\n"
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

    course_id = int(callback.data.split(":")[1])
    user = await check_course_access(callback, course_id)
    if user is None:
        return
    course = get_course_by_id(course_id)

    await safe_edit(
        callback,
        (
            "⭐ <b>ОЦІНІТЬ КУРС</b>\n\n"
            f"📦 {html.escape(course.title)}\n\n"
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

    _, course_id_raw, rating_raw = callback.data.split(":")
    course_id = int(course_id_raw)
    rating = int(rating_raw)
    user = await check_course_access(callback, course_id)
    if user is None:
        return

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

    course_id = int(callback.data.split(":")[1])
    user = await check_course_access(callback, course_id)
    if user is None:
        return
    course = get_course_by_id(course_id)

    await safe_edit(
        callback,
        (
            "⭐ <b>ЗМІНА ОЦІНКИ</b>\n\n"
            f"📦 {html.escape(course.title)}\n\n"
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

    course_id = int(callback.data.split(":")[1])
    user = await check_course_access(callback, course_id)
    if user is None:
        return
    course = get_course_by_id(course_id)

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

@dp.callback_query(F.data.startswith("user_review_delete:"))
async def user_review_delete(callback: CallbackQuery):
    if callback.data is None:
        return
    _, course_id_raw, review_id_raw = callback.data.split(":")
    course_id = int(course_id_raw)
    review_id = int(review_id_raw)
    user = await check_course_access(callback, course_id)
    if user is None:
        return
    review = get_user_review(user.id, course_id)
    if review is None or review.id != review_id:
        await callback.answer("Відгук не знайдено.", show_alert=True)
        return
    if not delete_review(review_id):
        await callback.answer("Не вдалося видалити відгук.", show_alert=True)
        return
    await safe_edit(
        callback,
        "🗑 <b>Відгук видалено</b>\n\nВи зможете залишити нову оцінку в будь-який момент.",
        parse_mode="HTML",
        reply_markup=user_review_empty_keyboard(course_id),
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

    course_id_raw = data.get("review_course_id")
    if course_id_raw is None:
        await state.clear()
        await message.answer("Не вдалося визначити курс.")
        return
    course_id = int(course_id_raw)

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
    user = get_user_from_telegram(callback.from_user)
    await safe_edit(
        callback,
        "❤️ Дякуємо!\n\nВи можете залишити або змінити відгук у будь-який момент через особистий кабінет.",
        reply_markup=profile_courses_keyboard(
            user.id,
            [c for c in get_all_courses() if c.is_active and c.is_visible],
            user.is_admin,
        ),
    )


@dp.callback_query(F.data.startswith("buy_course:"))
async def buy_course(callback: CallbackQuery):
    if callback.data is None:
        return
    course_id = int(callback.data.split(":")[1])
    course = get_course_by_id(course_id)
    if course is None or not course.is_active or not course.is_visible:
        await callback.answer("Курс не знайдено.", show_alert=True)
        return
    course_lessons = [l for l in lessons if l.course_id == course_id and l.is_active]
    description = html.escape(course.description) if course.description else "Практичний навчальний курс з довічним доступом до матеріалів."
    price = "Безкоштовно" if course.is_free or course.price == 0 else f"{course.price} грн"
    await safe_edit(
        callback,
        "🎓 <b>ПРИДБАННЯ КУРСУ</b>\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 <b>{html.escape(course.title)}</b>\n\n{description}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n📚 <b>ЩО ВХОДИТЬ У КУРС</b>\n\n"
        f"🎥 {len(course_lessons)} відеоуроків\n📄 PDF-матеріали до уроків\n♾ Довічний доступ\n🔄 Повторний перегляд\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n💳 Вартість курсу: <b>{price}</b>",
        parse_mode="HTML",
        reply_markup=buy_course_keyboard(course),
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

@dp.callback_query(F.data == "admin_course_create")
async def admin_course_create(
    callback: CallbackQuery,
    state: FSMContext,
):
    user = await check_admin(callback)

    if user is None or callback.message is None:
        return

    await state.clear()

    await state.set_state(
        AdminCourseCreate.waiting_for_title
    )

    await callback.message.answer(
        "🎓 <b>СОЗДАНИЕ НОВОГО КУРСА</b>\n\n"
        "Введите название курса одним сообщением.\n\n"
        "Например:\n"
        "<i>Теоретичний курс по Монтажу гіпсокартону з нуля</i>",
        parse_mode="HTML",
        reply_markup=(
            admin_course_create_cancel_keyboard()
        ),
    )

    await callback.answer()

@dp.message(
    AdminCourseCreate.waiting_for_title,
    F.text,
)
async def admin_course_create_title(
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

    title = message.text.strip()

    if len(title) < 3:
        await message.answer(
            "Название слишком короткое.\n\n"
            "Введите не менее 3 символов."
        )
        return

    if len(title) > 255:
        await message.answer(
            "Название слишком длинное.\n\n"
            "Максимум — 255 символов."
        )
        return

    await state.update_data(
        course_title=title
    )

    await state.set_state(
        AdminCourseCreate.waiting_for_lessons_count
    )

    await message.answer(
        "📖 Теперь укажите количество уроков.\n\n"
        "Отправьте только число.\n\n"
        "Например: <b>7</b>",
        parse_mode="HTML",
        reply_markup=(
            admin_course_create_cancel_keyboard()
        ),
    )

@dp.message(
    AdminCourseCreate.waiting_for_title
)
async def admin_course_create_wrong_title(
    message: Message,
):
    await message.answer(
        "Отправьте название курса "
        "обычным текстовым сообщением."
    )

@dp.message(
    AdminCourseCreate.waiting_for_lessons_count,
    F.text,
)
async def admin_course_create_lessons_count(
    message: Message,
    state: FSMContext,
):
    if message.text is None:
        return

    raw_count = message.text.strip()

    if not raw_count.isdigit():
        await message.answer(
            "Введите количество уроков числом.\n\n"
            "Например: <b>7</b>",
            parse_mode="HTML",
        )
        return

    lessons_count = int(raw_count)

    if lessons_count < 1 or lessons_count > 100:
        await message.answer(
            "Количество уроков должно быть "
            "от 1 до 100."
        )
        return

    await state.update_data(
        lessons_count=lessons_count,
        lesson_titles=[],
        current_lesson_number=1,
    )

    await state.set_state(
        AdminCourseCreate.waiting_for_lesson_title
    )

    await message.answer(
        (
            f"📖 Введите название урока "
            f"<b>1 из {lessons_count}</b>."
        ),
        parse_mode="HTML",
        reply_markup=(
            admin_course_create_cancel_keyboard()
        ),
    )

@dp.message(
    AdminCourseCreate.waiting_for_lesson_title,
    F.text,
)
async def admin_course_create_lesson_title(
    message: Message,
    state: FSMContext,
):
    if message.text is None:
        return

    lesson_title = message.text.strip()

    if len(lesson_title) < 2:
        await message.answer(
            "Название урока слишком короткое."
        )
        return

    if len(lesson_title) > 255:
        await message.answer(
            "Название урока слишком длинное.\n\n"
            "Максимум — 255 символов."
        )
        return

    data = await state.get_data()

    lessons_count = int(
        data.get("lessons_count", 0)
    )

    current_lesson_number = int(
        data.get("current_lesson_number", 1)
    )

    lesson_titles = list(
        data.get("lesson_titles", [])
    )

    lesson_titles.append(lesson_title)

    next_lesson_number = (
        current_lesson_number + 1
    )

    await state.update_data(
        lesson_titles=lesson_titles,
        current_lesson_number=next_lesson_number,
    )

    if next_lesson_number <= lessons_count:
        await message.answer(
            (
                f"✅ Название урока "
                f"{current_lesson_number} сохранено.\n\n"
                f"Введите название урока "
                f"<b>{next_lesson_number} "
                f"из {lessons_count}</b>."
            ),
            parse_mode="HTML",
            reply_markup=(
                admin_course_create_cancel_keyboard()
            ),
        )
        return

    await state.set_state(
        AdminCourseCreate.waiting_for_price
    )

    await message.answer(
        "💰 Теперь укажите цену курса "
        "в гривнах.\n\n"
        "Введите только число.\n\n"
        "Например: <b>1450</b>",
        parse_mode="HTML",
        reply_markup=(
            admin_course_create_cancel_keyboard()
        ),
    )
@dp.message(
    AdminCourseCreate.waiting_for_price,
    F.text,
)
async def admin_course_create_price(
    message: Message,
    state: FSMContext,
):
    if message.text is None:
        return

    raw_price = (
        message.text
        .strip()
        .replace(" ", "")
    )

    if not raw_price.isdigit():
        await message.answer(
            "Введите цену только числом.\n\n"
            "Например: <b>1450</b>",
            parse_mode="HTML",
        )
        return

    price = int(raw_price)

    if price < 1:
        await message.answer(
            "Цена должна быть больше нуля."
        )
        return

    if price > 10_000_000:
        await message.answer(
            "Указана слишком большая цена."
        )
        return

    await state.update_data(
        course_price=price
    )

    data = await state.get_data()

    course_title = str(
        data.get("course_title", "")
    )

    lesson_titles = list(
        data.get("lesson_titles", [])
    )

    lessons_text = "\n".join(
        (
            f"{position}. "
            f"{html.escape(title)}"
        )
        for position, title in enumerate(
            lesson_titles,
            start=1,
        )
    )

    await state.set_state(
        AdminCourseCreate.waiting_for_confirmation
    )

    await message.answer(
        (
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎓 <b>НОВЫЙ КУРС</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Название:\n"
            f"<b>{html.escape(course_title)}</b>\n\n"
            f"Количество уроков: "
            f"<b>{len(lesson_titles)}</b>\n\n"
            f"Цена: <b>{price} грн</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📖 <b>УРОКИ</b>\n\n"
            f"{lessons_text}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Создать этот курс?"
        ),
        parse_mode="HTML",
        reply_markup=(
            admin_course_create_confirmation_keyboard()
        ),
    )

@dp.callback_query(
    F.data == "admin_course_create_confirm"
)
async def admin_course_create_confirm(
    callback: CallbackQuery,
    state: FSMContext,
):
    user = await check_admin(callback)

    if user is None:
        return

    current_state = await state.get_state()

    expected_state = (
        AdminCourseCreate
        .waiting_for_confirmation
        .state
    )

    if current_state != expected_state:
        await callback.answer(
            "Данные создания курса устарели.",
            show_alert=True,
        )
        return

    data = await state.get_data()

    course_title = str(
        data.get("course_title", "")
    ).strip()

    course_price = int(
        data.get("course_price", 0)
    )

    lesson_titles = list(
        data.get("lesson_titles", [])
    )

    if (
        not course_title
        or course_price < 1
        or not lesson_titles
    ):
        await callback.answer(
            "Не удалось получить данные курса.",
            show_alert=True,
        )

        await state.clear()
        return

    course = create_course_with_lessons(
        title=course_title,
        price=course_price,
        lesson_titles=lesson_titles,
    )

    if course is None:
        await callback.answer(
            "Не удалось создать курс.",
            show_alert=True,
        )
        return

    await state.clear()

    refresh_lessons()

    if callback.message is not None:
        await callback.message.answer(
            (
                "✅ <b>КУРС СОЗДАН</b>\n\n"
                f"Название: "
                f"<b>{html.escape(course.title)}</b>\n"
                f"Цена: <b>{course.price} грн</b>\n"
                f"Уроков: "
                f"<b>{len(lesson_titles)}</b>\n\n"
                "Теперь можно открыть редактор "
                "уроков и добавить видео, "
                "описания и PDF."
            ),
            parse_mode="HTML",
            reply_markup=admin_course_keyboard(
                course.id
            ),
        )

    await callback.answer(
        "Курс успешно создан."
    )

@dp.callback_query(
    F.data == "admin_course_create_cancel"
)
async def admin_course_create_cancel(
    callback: CallbackQuery,
    state: FSMContext,
):
    user = await check_admin(callback)

    if user is None:
        return

    await state.clear()

    courses = get_all_courses()

    await safe_edit(
        callback,
        "❌ Создание курса отменено.",
        reply_markup=admin_courses_keyboard(
            courses
        ),
    )


@dp.callback_query(F.data == "admin_courses")
async def admin_courses(callback: CallbackQuery):
    user = await check_admin(callback)

    if user is None:
        return

    courses = get_all_courses()

    text = (
        "📚 <b>УПРАВЛЕНИЕ КУРСАМИ</b>\n\n"
        "Выберите существующий курс "
        "или создайте новый."
    )

    if not courses:
        text = (
            "📚 <b>УПРАВЛЕНИЕ КУРСАМИ</b>\n\n"
            "Курсов пока нет.\n\n"
            "Нажмите «Добавить курс»."
        )

    await safe_edit(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=admin_courses_keyboard(
            courses
        ),
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

    user = get_user_from_telegram(callback.from_user)
    course_id = int(callback.data.split(":")[1])
    course = get_course_by_id(course_id)

    if course is None or not course.is_active or not course.is_visible:
        await callback.answer("Курс не знайдено.", show_alert=True)
        return

    if user_has_active_course(user.id, course_id):
        await callback.answer("У вас уже є доступ до цього курсу.", show_alert=True)
        return

    if course.is_free or course.price == 0:
        grant_course_access(user.id, course_id)
        await send_purchase_success(user.telegram_id, course.title)
        await callback.answer("Доступ відкрито.")
        return

    await safe_edit(
        callback,
        (
            "💳 <b>ОПЛАТА КУРСУ</b>\n\n"
            f"📚 <b>{html.escape(course.title)}</b>\n\n"
            f"Сума до оплати: <b>{course.price} грн</b>\n\n"
            "Оберіть зручний спосіб оплати:"
        ),
        parse_mode="HTML",
        reply_markup=payment_method_keyboard(course.id),
    )

@dp.callback_query(F.data.startswith("payment_method:"))
async def payment_method(callback: CallbackQuery):
    if callback.data is None:
        return

    try:
        _, course_id_raw, method = callback.data.split(":")
        course_id = int(course_id_raw)
    except (ValueError, IndexError):
        await callback.answer(
            "Некоректні дані оплати.",
            show_alert=True,
        )
        return

    user = get_user_from_telegram(callback.from_user)
    course = get_course_by_id(course_id)

    if (
        course is None
        or not course.is_active
        or not course.is_visible
    ):
        await callback.answer(
            "Курс не знайдено.",
            show_alert=True,
        )
        return

    if user_has_active_course(user.id, course.id):
        await callback.answer(
            "У вас уже є доступ до цього курсу.",
            show_alert=True,
        )
        return

    if method not in {"card", "iban"}:
        await callback.answer(
            "Некоректний спосіб оплати.",
            show_alert=True,
        )
        return

    # Сначала создаём заявку, чтобы получить её уникальный ID
    request = create_payment_request(
        user_id=user.id,
        course_id=course.id,
        amount=int(course.price),
        payment_method=method,
    )

    if request is None:
        await callback.answer(
            "Не вдалося створити заявку на оплату.",
            show_alert=True,
        )
        return

    # Уникальный код конкретной заявки
    payment_code = f"PAY-{request.id:06d}"

    # Назначение платежа
    payment_purpose = (

        f"Переказ власних коштів. Код платежу {payment_code}"

    )

    if method == "card":
        if (
            not PAYMENT_CARD_NUMBER
            or not PAYMENT_CARD_HOLDER
        ):
            await callback.answer(
                "Реквізити картки ще не налаштовані.",
                show_alert=True,
            )
            return

        details = (
            "💳 <b>ОПЛАТА НА КАРТКУ</b>\n\n"
            f"Сума: <b>{course.price} грн</b>\n\n"
            "Номер картки:\n"
            f"<code>{html.escape(PAYMENT_CARD_NUMBER)}</code>\n\n"
            "Отримувач:\n"
            f"<b>{html.escape(PAYMENT_CARD_HOLDER)}</b>\n\n"
            "Код платежу:\n"
            f"<code>{payment_code}</code>\n\n"
            "Призначення платежу:\n"
            f"<code>{html.escape(payment_purpose)}</code>"
        )

    else:
        if (
            not PAYMENT_IBAN
            or not PAYMENT_RECIPIENT
            or not PAYMENT_EDRPOU
        ):
            await callback.answer(
                "Реквізити IBAN ще не налаштовані.",
                show_alert=True,
            )
            return

        details = (
            "🏦 <b>ОПЛАТА ЗА РЕКВІЗИТАМИ IBAN</b>\n\n"
            f"Сума: <b>{course.price} грн</b>\n\n"
            "Отримувач:\n"
            f"<b>{html.escape(PAYMENT_RECIPIENT)}</b>\n\n"
            "Код отримувача (ЄДРПОУ):\n"
            f"<code>{html.escape(PAYMENT_EDRPOU)}</code>\n\n"
            "IBAN:\n"
            f"<code>{html.escape(PAYMENT_IBAN)}</code>\n\n"
            "Код платежу:\n"
            f"<code>{payment_code}</code>\n\n"
            "Призначення платежу:\n"
            f"<code>{html.escape(payment_purpose)}</code>"
        )

    await safe_edit(
        callback,
        (
            f"{details}\n\n"
            "⚠️ <b>Важливо:</b> скопіюйте призначення платежу "
            "без змін і вкажіть його під час оплати.\n\n"
            "Після переказу натисніть кнопку "
            "<b>«Я оплатив»</b> та надішліть квитанцію "
            "у вигляді фото або PDF.\n\n"
            "ℹ️ Заявка вже прив’язана до вашого "
            "Telegram-профілю та обраного курсу."
        ),
        parse_mode="HTML",
        reply_markup=payment_details_keyboard(request.id),
    )


# @dp.callback_query(F.data.startswith("payment_method:"))
# async def payment_method(callback: CallbackQuery):
#     if callback.data is None:
#         return
#
#     _, course_id_raw, method = callback.data.split(":")
#     course_id = int(course_id_raw)
#     user = get_user_from_telegram(callback.from_user)
#     course = get_course_by_id(course_id)
#
#     if course is None or not course.is_active or not course.is_visible:
#         await callback.answer("Курс не знайдено.", show_alert=True)
#         return
#
#     if method == "card":
#         if not PAYMENT_CARD_NUMBER or not PAYMENT_CARD_HOLDER:
#             await callback.answer("Реквізити картки ще не налаштовані.", show_alert=True)
#             return
#         details = (
#             "💳 <b>ОПЛАТА НА КАРТКУ</b>\n\n"
#             f"Сума: <b>{course.price} грн</b>\n\n"
#             f"Номер картки:\n<code>{html.escape(PAYMENT_CARD_NUMBER)}</code>\n\n"
#             f"Отримувач:\n<b>{html.escape(PAYMENT_CARD_HOLDER)}</b>"
#         )
#     elif method == "iban":
#
#         if (
#
#                 not PAYMENT_IBAN
#
#                 or not PAYMENT_RECIPIENT
#
#                 or not PAYMENT_EDRPOU
#
#         ):
#             await callback.answer(
#
#                 "Реквізити IBAN ще не налаштовані.",
#
#                 show_alert=True,
#
#             )
#
#             return
#
#         details = (
#
#             "🏦 <b>ОПЛАТА ЗА РЕКВІЗИТАМИ</b>\n\n"
#
#             f"Сума: <b>{course.price} грн</b>\n\n"
#
#             f"Отримувач:\n"
#
#             f"<b>{html.escape(PAYMENT_RECIPIENT)}</b>\n\n"
#
#             f"Код отримувача (ЄДРПОУ):\n"
#
#             f"<code>{html.escape(PAYMENT_EDRPOU)}</code>\n\n"
#
#             f"IBAN:\n"
#
#             f"<code>{html.escape(PAYMENT_IBAN)}</code>"
#
#         )
#
#
#     else:
#         await callback.answer("Некоректний спосіб оплати.", show_alert=True)
#         return
#
#     request = create_payment_request(user.id, course.id, int(course.price), method)
#     if request is None:
#         await callback.answer("Не вдалося створити заявку на оплату.", show_alert=True)
#         return
#
#     await safe_edit(
#         callback,
#         (
#             f"{details}\n\n"
#             "Після переказу натисніть кнопку <b>«Я оплатив»</b> та надішліть квитанцію "
#             "у вигляді фото або PDF.\n\n"
#             "ℹ️ Заявка вже прив’язана до вашого Telegram-профілю та обраного курсу."
#         ),
#         parse_mode="HTML",
#         reply_markup=payment_details_keyboard(request.id),
#     )


@dp.callback_query(F.data.startswith("payment_paid:"))
async def payment_paid(callback: CallbackQuery, state: FSMContext):
    if callback.data is None or callback.message is None:
        return

    request_id = int(callback.data.split(":")[1])
    request = get_payment_request(request_id)
    user = get_user_from_telegram(callback.from_user)

    if request is None or request.user_id != user.id:
        await callback.answer("Заявку не знайдено.", show_alert=True)
        return

    await state.update_data(payment_request_id=request.id)
    await state.set_state(ManualPaymentReceipt.waiting_for_receipt)
    await callback.message.answer(
        "📎 <b>НАДІШЛІТЬ КВИТАНЦІЮ</b>\n\n"
        "Надішліть одним повідомленням фотографію, скриншот або PDF-файл квитанції.\n\n"
        "Після надсилання заявка потрапить адміністратору на перевірку.",
        parse_mode="HTML",
    )
    await callback.answer()


@dp.message(ManualPaymentReceipt.waiting_for_receipt)
async def payment_receipt_received(message: Message, state: FSMContext):
    if message.from_user is None:
        return

    file_id = None
    file_type = None
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif message.document:
        file_name = (message.document.file_name or "").lower()
        if message.document.mime_type != "application/pdf" and not file_name.endswith(".pdf"):
            await message.answer("Надішліть квитанцію як фотографію або PDF-файл.")
            return
        file_id = message.document.file_id
        file_type = "document"
    else:
        await message.answer("Надішліть квитанцію як фотографію або PDF-файл.")
        return

    data = await state.get_data()
    request_id = data.get("payment_request_id")
    if request_id is None:
        await state.clear()
        await message.answer("Не вдалося визначити заявку. Розпочніть оплату ще раз.")
        return

    request = get_payment_request(int(request_id))
    user = get_user_from_telegram(message.from_user)
    if request is None or request.user_id != user.id:
        await state.clear()
        await message.answer("Заявку не знайдено.")
        return

    submitted = submit_receipt(int(request_id), file_id, file_type)
    await state.clear()
    if submitted is None:
        await message.answer("Не вдалося зберегти квитанцію. Спробуйте ще раз.")
        return

    course = get_course_by_id(submitted.course_id)
    await message.answer(
        "✅ <b>КВИТАНЦІЮ ОТРИМАНО</b>\n\n"
        f"Курс: <b>{html.escape(course.title if course else 'Курс')}</b>\n"
        f"Сума: <b>{submitted.amount} грн</b>\n\n"
        "Оплата передана адміністратору на перевірку. Після підтвердження доступ відкриється автоматично.",
        parse_mode="HTML",
        reply_markup=main_menu(user.is_admin),
    )

    # for admin_user in [item for item in get_all_users(limit=1000, offset=0) if item.is_admin]:
    #     try:
    #         await bot.send_message(
    #             admin_user.telegram_id,
    #             f"💳 Нова квитанція на перевірку\n\nЗаявка #{submitted.id}\nСума: {submitted.amount} грн",
    #             reply_markup=admin_payment_actions_keyboard(submitted.id),
    #         )
    #     except Exception:
    #         pass
    #
    #

    for admin_user in [
        item
        for item in get_all_users(limit=1000, offset=0)
        if item.is_admin
    ]:
        try:
            payment_code = f"PAY-{submitted.id:06d}"

            admin_caption = (

                "💳 <b>НОВА КВИТАНЦІЯ НА ПЕРЕВІРКУ</b>\n\n"

                f"Заявка: <b>#{submitted.id}</b>\n"

                f"Код платежу: <code>{payment_code}</code>\n"

                f"Сума: <b>{submitted.amount} грн</b>\n\n"

                "🔍 Перевірте, щоб код у квитанції збігався "

                "з кодом заявки.\n\n"

                "Натисніть кнопку нижче, щоб підтвердити "

                "або відхилити оплату."

            )

            if submitted.receipt_file_type == "photo":
                await bot.send_photo(
                    chat_id=admin_user.telegram_id,
                    photo=submitted.receipt_file_id,
                    caption=admin_caption,
                    parse_mode="HTML",
                    reply_markup=admin_payment_actions_keyboard(
                        submitted.id
                    ),
                )

            elif submitted.receipt_file_type == "document":
                await bot.send_document(
                    chat_id=admin_user.telegram_id,
                    document=submitted.receipt_file_id,
                    caption=admin_caption,
                    parse_mode="HTML",
                    reply_markup=admin_payment_actions_keyboard(
                        submitted.id
                    ),
                )

            else:
                await bot.send_message(
                    chat_id=admin_user.telegram_id,
                    text=admin_caption,
                    parse_mode="HTML",
                    reply_markup=admin_payment_actions_keyboard(
                        submitted.id
                    ),
                )

        except Exception:
            pass



# @dp.callback_query(F.data.startswith("admin_course:"))
# async def admin_course(callback: CallbackQuery):
#     user = await check_admin(callback)
#     if user is None or callback.data is None:
#         return
#     course_id = int(callback.data.split(":")[1])
#     course_lessons = [lesson for lesson in lessons if lesson.course_id == course_id]
#     await safe_edit(
#         callback,
#         f"🎓 {COURSE_TITLE}\n\nЦена: {COURSE_PRICE} грн\nСтатус: активен\nУроков: {len(course_lessons)}",
#         reply_markup=admin_course_keyboard(course_id),
#     )

@dp.callback_query(
    F.data.startswith("admin_course:")
)
async def admin_course(
    callback: CallbackQuery,
):
    user = await check_admin(callback)

    if (
        user is None
        or callback.data is None
    ):
        return

    try:
        course_id = int(
            callback.data.split(":", 1)[1]
        )
    except (IndexError, ValueError):
        await callback.answer(
            "Некорректный идентификатор курса.",
            show_alert=True,
        )
        return

    course = get_course_by_id(
        course_id
    )

    if course is None:
        await callback.answer(
            "Курс не найден.",
            show_alert=True,
        )
        return

    course_lessons = [
        lesson
        for lesson in lessons
        if lesson.course_id == course_id
    ]

    active_status = (
        "активен"
        if course.is_active
        else "отключён"
    )

    visible_status = (
        "виден ученикам"
        if course.is_visible
        else "скрыт от учеников"
    )

    await safe_edit(
        callback,
        (
            f"🎓 <b>{html.escape(course.title)}</b>\n\n"
            f"💰 Цена: <b>{course.price} грн</b>\n"
            f"📖 Уроков: <b>{len(course_lessons)}</b>\n"
            f"⚙️ Статус: <b>{active_status}</b>\n"
            f"👁 Отображение: <b>{visible_status}</b>"
        ),
        parse_mode="HTML",
        reply_markup=admin_course_keyboard(
            course_id
        ),
    )
@dp.callback_query(
    F.data.startswith("admin_course_price:")
)
async def admin_course_price(
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

    try:
        course_id = int(
            callback.data.split(":", 1)[1]
        )
    except (IndexError, ValueError):
        await callback.answer(
            "Не удалось определить курс.",
            show_alert=True,
        )
        return

    course = get_course_by_id(
        course_id
    )

    if course is None:
        await callback.answer(
            "Курс не найден.",
            show_alert=True,
        )
        return

    await state.clear()

    await state.update_data(
        editing_course_id=course_id
    )

    await state.set_state(
        AdminCourseEdit.waiting_for_price
    )

    await callback.message.answer(
        (
            "💰 <b>ИЗМЕНЕНИЕ ЦЕНЫ</b>\n\n"
            f"Курс:\n"
            f"<b>{html.escape(course.title)}</b>\n\n"
            f"Текущая цена: "
            f"<b>{course.price} грн</b>\n\n"
            "Введите новую цену только числом.\n\n"
            "Например: <b>2000</b>"
        ),
        parse_mode="HTML",
    )

    await callback.answer()

@dp.message(
    AdminCourseEdit.waiting_for_price,
    F.text,
)
async def save_admin_course_price(
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
        await message.answer(
            "⛔ Нет доступа."
        )
        await state.clear()
        return

    raw_price = (
        message.text
        .strip()
        .replace(" ", "")
    )

    if not raw_price.isdigit():
        await message.answer(
            "Введите цену только числом.\n\n"
            "Например: <b>2000</b>",
            parse_mode="HTML",
        )
        return

    new_price = int(raw_price)

    if new_price < 1:
        await message.answer(
            "Цена должна быть больше нуля."
        )
        return

    data = await state.get_data()

    course_id = data.get(
        "editing_course_id"
    )

    if course_id is None:
        await message.answer(
            "Не удалось определить курс."
        )
        await state.clear()
        return

    updated = update_course_price(
        course_id=int(course_id),
        price=new_price,
    )

    if not updated:
        await message.answer(
            "Не удалось изменить цену."
        )
        await state.clear()
        return

    course = get_course_by_id(
        int(course_id)
    )

    await state.clear()

    await message.answer(
        (
            "✅ <b>ЦЕНА ОБНОВЛЕНА</b>\n\n"
            f"Курс:\n"
            f"<b>{html.escape(course.title)}</b>\n\n"
            f"Новая цена: "
            f"<b>{course.price} грн</b>"
        ),
        parse_mode="HTML",
        reply_markup=admin_course_keyboard(
            int(course_id)
        ),
    )
@dp.message(
    AdminCourseEdit.waiting_for_price
)
async def wrong_admin_course_price(
    message: Message,
):
    await message.answer(
        "Отправьте новую цену "
        "обычным текстовым сообщением."
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

@dp.callback_query(
    F.data.startswith("admin_lesson_delete:")
)
async def admin_lesson_delete_request(
    callback: CallbackQuery,
):
    user = await check_admin(callback)

    if (
        user is None
        or callback.data is None
    ):
        return

    try:
        lesson_id = int(
            callback.data.split(":", 1)[1]
        )
    except (IndexError, ValueError):
        await callback.answer(
            "Не удалось определить урок.",
            show_alert=True,
        )
        return

    lesson = get_lesson_by_id(
        lesson_id
    )

    if lesson is None:
        await callback.answer(
            "Урок не найден.",
            show_alert=True,
        )
        return

    await safe_edit(
        callback,
        (
            "⚠️ <b>УДАЛЕНИЕ УРОКА</b>\n\n"
            f"Курс ID: <b>{lesson.course_id}</b>\n\n"
            f"Урок:\n"
            f"<b>{lesson.position}. "
            f"{html.escape(lesson.title)}</b>\n\n"
            "Будут также удалены записи прогресса "
            "учеников по этому уроку.\n\n"
            "После удаления остальные уроки будут "
            "автоматически перенумерованы.\n\n"
            "Это действие нельзя отменить."
        ),
        parse_mode="HTML",
        reply_markup=(
            admin_lesson_delete_confirmation_keyboard(
                lesson_id=lesson.id,
                course_id=lesson.course_id,
            )
        ),
    )

@dp.callback_query(
    F.data.startswith(
        "admin_lesson_delete_confirm:"
    )
)
async def admin_lesson_delete_confirm(
    callback: CallbackQuery,
):
    user = await check_admin(callback)

    if (
        user is None
        or callback.data is None
    ):
        return

    try:
        lesson_id = int(
            callback.data.split(":", 1)[1]
        )
    except (IndexError, ValueError):
        await callback.answer(
            "Не удалось определить урок.",
            show_alert=True,
        )
        return

    lesson = get_lesson_by_id(
        lesson_id
    )

    if lesson is None:
        await callback.answer(
            "Урок уже удалён или не найден.",
            show_alert=True,
        )
        return

    lesson_title = lesson.title

    deleted, course_id = delete_lesson(
        lesson_id
    )

    if not deleted or course_id is None:
        await callback.answer(
            "Не удалось удалить урок.",
            show_alert=True,
        )
        return

    refresh_lessons()

    course_lessons = [
        item
        for item in lessons
        if item.course_id == course_id
    ]

    await safe_edit(
        callback,
        (
            "✅ <b>УРОК УДАЛЁН</b>\n\n"
            f"<b>{html.escape(lesson_title)}</b>\n\n"
            "Оставшиеся уроки перенумерованы."
        ),
        parse_mode="HTML",
        reply_markup=admin_lessons_keyboard(
            course_lessons=course_lessons,
            course_id=course_id,
        ),
    )

    await callback.answer(
        "Урок удалён."
    )



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

@dp.callback_query(
    F.data.startswith("admin_course_delete:")
)
async def admin_course_delete_request(
    callback: CallbackQuery,
):
    user = await check_admin(callback)

    if (
        user is None
        or callback.data is None
    ):
        return

    try:
        course_id = int(
            callback.data.split(":", 1)[1]
        )
    except (IndexError, ValueError):
        await callback.answer(
            "Не удалось определить курс.",
            show_alert=True,
        )
        return

    if course_id == COURSE_ID:
        await callback.answer(

            "Основной курс пока нельзя удалить, "

            "поскольку пользовательская часть платформы "

            "ещё привязана к нему.",

            show_alert=True,

        )

        return

    course = get_course_by_id(
        course_id
    )



    if course is None:
        await callback.answer(
            "Курс не найден.",
            show_alert=True,
        )
        return

    course_lessons = [
        lesson
        for lesson in lessons
        if lesson.course_id == course_id
    ]

    await safe_edit(
        callback,
        (
            "⚠️ <b>УДАЛЕНИЕ КУРСА</b>\n\n"
            f"Курс:\n"
            f"<b>{html.escape(course.title)}</b>\n\n"
            f"Уроков: <b>{len(course_lessons)}</b>\n"
            f"Цена: <b>{course.price} грн</b>\n\n"
            "При полном удалении будут удалены:\n\n"
            "• сам курс;\n"
            "• все его уроки;\n"
            "• прогресс учеников;\n"
            "• покупки и выданные доступы;\n"
            "• платежи;\n"
            "• отзывы.\n\n"
            "⚠️ Это действие нельзя отменить."
        ),
        parse_mode="HTML",
        reply_markup=(
            admin_course_delete_confirmation_keyboard(
                course.id
            )
        ),
    )

@dp.callback_query(
    F.data.startswith(
        "admin_course_delete_confirm:"
    )
)
async def admin_course_delete_confirm(
    callback: CallbackQuery,
):
    user = await check_admin(callback)

    if (
        user is None
        or callback.data is None
    ):
        return

    try:
        course_id = int(
            callback.data.split(":", 1)[1]
        )
    except (IndexError, ValueError):
        await callback.answer(
            "Не удалось определить курс.",
            show_alert=True,
        )
        return

    course = get_course_by_id(
        course_id
    )

    if course is None:
        await callback.answer(
            "Курс уже удалён или не найден.",
            show_alert=True,
        )
        return

    course_title = course.title

    deleted = delete_course(
        course_id
    )

    if not deleted:
        await callback.answer(
            "Не удалось удалить курс.",
            show_alert=True,
        )
        return

    refresh_lessons()

    courses = get_all_courses()

    await safe_edit(
        callback,
        (
            "✅ <b>КУРС УДАЛЁН</b>\n\n"
            f"<b>{html.escape(course_title)}</b>\n\n"
            "Все связанные данные удалены."
        ),
        parse_mode="HTML",
        reply_markup=admin_courses_keyboard(
            courses
        ),
    )

    await callback.answer(
        "Курс удалён."
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

    try:
        student_id = int(parts[1])

        page = (
            int(parts[2])
            if len(parts) > 2
            else 1
        )
    except (IndexError, ValueError):
        await callback.answer(
            "Не вдалося визначити користувача.",
            show_alert=True,
        )
        return

    student = get_user_by_id(
        student_id
    )

    if student is None:
        await callback.answer(
            "Користувача не знайдено.",
            show_alert=True,
        )
        return

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
        f"🔗 Username: "
        f"@{html.escape(student.username)}"
        if student.username
        else "🔗 Username: не вказано"
    )

    role_line = (
        "👨‍💼 Роль: адміністратор"
        if student.is_admin
        else "👤 Роль: учень"
    )

    courses = [
        course
        for course in get_all_courses()
        if course.is_active
    ]

    course_blocks: list[str] = []

    for course in courses:
        has_access = user_has_active_course(
            user_id=student.id,
            course_id=course.id,
        )

        course_title = html.escape(
            course.title
        )

        if has_access:
            progress = get_course_progress(
                user_id=student.id,
                course_id=course.id,
            )

            progress_bar = build_progress_bar(
                progress["completed"],
                progress["total"],
            )

            if (
                progress["total"] > 0
                and progress["completed"]
                >= progress["total"]
            ):
                course_status = (
                    "🏆 Курс завершено"
                )

            elif progress["completed"] > 0:
                course_status = (
                    "🎓 Навчання розпочато"
                )

            else:
                course_status = (
                    "⏳ Навчання ще не розпочато"
                )

            review = get_user_review(
                student.id,
                course.id,
            )

            if review is None:
                review_line = (
                    "⭐ Оцінка: не залишена"
                )
            else:
                review_line = (
                    f"⭐ Оцінка: "
                    f"{'⭐' * review.rating}"
                )

            course_block = (
                f"📦 <b>{course_title}</b>\n\n"
                "✅ Доступ: <b>активний</b>\n\n"
                f"{progress_bar}\n"
                f"📈 Прогрес: "
                f"<b>{progress['percent']}%</b>\n"
                f"✅ Завершено уроків: "
                f"<b>{progress['completed']} "
                f"із {progress['total']}</b>\n"
                f"{course_status}\n"
                f"{review_line}"
            )

        else:
            price_text = (
                "Безкоштовно"
                if course.is_free
                or course.price == 0
                else f"{course.price} грн"
            )

            course_block = (
                f"📦 <b>{course_title}</b>\n\n"
                "❌ Доступ: <b>відсутній</b>\n"
                f"💳 Вартість: "
                f"<b>{price_text}</b>\n\n"
                "Користувач ще не придбав "
                "цей курс."
            )

        course_blocks.append(
            course_block
        )

    if course_blocks:
        courses_block = (
            "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
            "\n\n"
        ).join(course_blocks)

    else:
        courses_block = (
            "📚 Активних курсів поки немає."
        )

    await safe_edit(
        callback,
        (
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 <b>КАРТКА УЧНЯ</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Ім’я: "
            f"<b>{html.escape(full_name)}</b>\n"
            f"{username_line}\n"
            f"🆔 Telegram ID: "
            f"<code>{student.telegram_id}</code>\n"
            f"🗄 ID у базі: "
            f"<code>{student.id}</code>\n"
            f"{role_line}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{courses_block}"
        ),
        parse_mode="HTML",
        reply_markup=admin_student_keyboard(
            student_id=student.id,
            courses=courses,
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

    try:
        student_id = int(parts[1])
        course_id = int(parts[2])

        page = (
            int(parts[3])
            if len(parts) > 3
            else 1
        )

    except (IndexError, ValueError):
        await callback.answer(
            "Не вдалося визначити "
            "користувача або курс.",
            show_alert=True,
        )
        return

    student = get_user_by_id(
        student_id
    )

    if student is None:
        await callback.answer(
            "Користувача не знайдено.",
            show_alert=True,
        )
        return

    course = get_course_by_id(
        course_id
    )

    if course is None:
        await callback.answer(
            "Курс не знайдено.",
            show_alert=True,
        )
        return

    if not course.is_active:
        await callback.answer(
            "Цей курс зараз неактивний.",
            show_alert=True,
        )
        return

    if user_has_active_course(
        user_id=student.id,
        course_id=course.id,
    ):
        await callback.answer(
            "У користувача вже є доступ "
            "до цього курсу.",
            show_alert=True,
        )
        return

    purchase = grant_course_access(
        user_id=student.id,
        course_id=course.id,
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
            course_title=course.title,
        )

        notification_text = (
            "Доступ видано. Користувачу "
            "надіслано повідомлення."
        )

    except Exception:
        notification_text = (
            "Доступ видано, але повідомлення "
            "користувачу не вдалося доставити."
        )

    await callback.answer(
        notification_text,
        show_alert=True,
    )

    callback.data = (
        f"admin_student:"
        f"{student.id}:"
        f"{page}"
    )

    await admin_student(
        callback
    )


# @dp.callback_query(F.data == "admin_payments")
# async def admin_payments(callback: CallbackQuery):
#     user = await check_admin(callback)
#     if user is None:
#         return
#     requests = get_payment_requests(status="submitted", limit=50)
#     text = (
#         "💳 <b>ОПЛАТИ</b>\n\n"
#         f"Очікують перевірки: <b>{len(requests)}</b>\n\nОберіть заявку:"
#         if requests
#         else "💳 <b>ОПЛАТИ</b>\n\nНових квитанцій для перевірки немає."
#     )
#     await safe_edit(callback, text, parse_mode="HTML", reply_markup=admin_payments_keyboard(requests))
@dp.callback_query(F.data == "admin_payments")
async def admin_payments(callback: CallbackQuery):
    user = await check_admin(callback)

    if user is None or callback.message is None:
        return

    requests = get_payment_requests(
        status="submitted",
        limit=50,
    )

    if requests:
        text = (
            "💳 <b>ОПЛАТИ</b>\n\n"
            f"Очікують перевірки: "
            f"<b>{len(requests)}</b>\n\n"
            "Оберіть заявку:"
        )
    else:
        text = (
            "💳 <b>ОПЛАТИ</b>\n\n"
            "Нових квитанцій для перевірки немає."
        )

    keyboard = admin_payments_keyboard(requests)

    # Если кнопка нажата под обычным текстовым сообщением
    if callback.message.text is not None:
        await safe_edit(
            callback,
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    # Если кнопка нажата под фото, PDF или другим медиасообщением
    else:
        try:
            # Убираем старые кнопки под квитанцией
            await callback.message.edit_reply_markup(
                reply_markup=None
            )
        except TelegramBadRequest:
            pass

        # Отправляем список оплат отдельным текстовым сообщением
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        await callback.answer()


@dp.callback_query(F.data.startswith("admin_payment:"))
async def admin_payment(callback: CallbackQuery):
    user = await check_admin(callback)
    if user is None or callback.data is None or callback.message is None:
        return
    request_id = int(callback.data.split(":")[1])
    request = get_payment_request(request_id)
    if request is None:
        await callback.answer("Заявку не знайдено.", show_alert=True)
        return
    student = get_user_by_id(request.user_id)
    course = get_course_by_id(request.course_id)
    if student is None or course is None:
        await callback.answer("Дані заявки пошкоджено.", show_alert=True)
        return
    full_name = " ".join(part for part in [student.first_name, student.last_name] if part) or "Користувач"
    username = f"@{student.username}" if student.username else "не вказано"
    method = "Картка" if request.payment_method == "card" else "IBAN"
    payment_code = f"PAY-{request.id:06d}"

    payment_purpose = (

        f"Переказ власних коштів. Код платежу {payment_code}"

    )
    caption = (

        "💳 <b>ЗАЯВКА НА ОПЛАТУ</b>\n\n"

        f"Заявка: <b>#{request.id}</b>\n"

        f"Код платежу: <code>{payment_code}</code>\n\n"

        f"👤 Учень: <b>{html.escape(full_name)}</b>\n"

        f"Username: {html.escape(username)}\n"

        f"Telegram ID: <code>{student.telegram_id}</code>\n\n"

        f"📚 Курс: <b>{html.escape(course.title)}</b>\n"

        f"💰 Сума: <b>{request.amount} грн</b>\n"

        f"💳 Спосіб: <b>{method}</b>\n\n"

        "📝 <b>Очікуване призначення платежу:</b>\n"

        f"<code>{html.escape(payment_purpose)}</code>\n\n"

        "🔍 Звірте код із кодом, зазначеним у квитанції."

    )
    if request.receipt_file_type == "photo":
        await callback.message.answer_photo(request.receipt_file_id, caption=caption, parse_mode="HTML", reply_markup=admin_payment_actions_keyboard(request.id))
    else:
        await callback.message.answer_document(request.receipt_file_id, caption=caption, parse_mode="HTML", reply_markup=admin_payment_actions_keyboard(request.id))
    await callback.answer()


@dp.callback_query(F.data.startswith("admin_payment_confirm:"))
async def admin_payment_confirm(callback: CallbackQuery):
    admin = await check_admin(callback)
    if admin is None or callback.data is None:
        return
    request_id = int(callback.data.split(":")[1])
    confirmed = confirm_payment_request(request_id, admin.id)
    if confirmed is None:
        await callback.answer("Заявка вже оброблена або не знайдена.", show_alert=True)
        return
    grant_course_access(confirmed.user_id, confirmed.course_id)
    student = get_user_by_id(confirmed.user_id)
    course = get_course_by_id(confirmed.course_id)
    if student is not None and course is not None:
        try:
            await send_purchase_success(student.telegram_id, course.title)
        except Exception:
            pass
    await callback.answer("Оплату підтверджено. Доступ відкрито.", show_alert=True)
    await admin_payments(callback)


@dp.callback_query(F.data.startswith("admin_payment_reject:"))
async def admin_payment_reject(callback: CallbackQuery):
    admin = await check_admin(callback)
    if admin is None or callback.data is None:
        return
    request_id = int(callback.data.split(":")[1])
    rejected = reject_payment_request(request_id, admin.id)
    if rejected is None:
        await callback.answer("Заявка вже оброблена або не знайдена.", show_alert=True)
        return
    student = get_user_by_id(rejected.user_id)
    course = get_course_by_id(rejected.course_id)
    if student is not None:
        try:
            await bot.send_message(
                student.telegram_id,
                "❌ <b>ОПЛАТУ НЕ ПІДТВЕРДЖЕНО</b>\n\n"
                f"Курс: <b>{html.escape(course.title if course else 'Курс')}</b>\n\n"
                "Перевірте переказ і надішліть нову квитанцію або зверніться до адміністратора.",
                parse_mode="HTML",
                reply_markup=main_menu(student.is_admin),
            )
        except Exception:
            pass
    await callback.answer("Заявку відхилено.", show_alert=True)
    await admin_payments(callback)


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
        f"🔓 Відкрито доступів: <b>{stats['active_purchases']}</b>\n"
        f"💳 Підтверджених продажів: <b>{stats['paid_sales']}</b>\n"
        f"🟠 Оплат на перевірці: <b>{stats['payments_to_review']}</b>\n"
        f"💰 Підтверджений дохід: <b>{stats['income']} грн</b>\n\n"
        f"🎓 Розпочали курс: <b>{stats['started']}</b>\n"
        f"🏆 Завершили курс: <b>{stats['completed']}</b>\n"
        f"📈 Середній прогрес: <b>{stats['average_progress']}%</b>\n\n"
        f"⭐ Середня оцінка: <b>{stats['average_rating']}</b>\n"
        f"📝 Відгуків: <b>{stats['review_total']}</b>\n"
        f"🔔 Нових відгуків: <b>{stats['unread_reviews']}</b>\n\n"
        "ℹ️ Ручна видача доступу не враховується як продаж. Дохід рахується лише за підтвердженими оплатами.",
        parse_mode="HTML",
        reply_markup=admin_menu(),
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
