from aiogram.exceptions import TelegramBadRequest


async def safe_edit_message(message, text: str, reply_markup=None):
    """
    Безопасно редактирует сообщение.
    Если текст не изменился — просто игнорирует ошибку.
    """
    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise