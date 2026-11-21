from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from config import Settings
from utils import text

router = Router(name="commands")

_DEFAULT_HELP = (
    "<b>Yordam</b>\n\n"
    "Havola yuboring — men uni yuklab beraman.\n"
    "• /start — botni ishga tushirish\n"
    "• /help — yordam"
)


def _start_template() -> str:
    for attr in ("START_MESSAGE", "START_TEXT", "WELCOME_MESSAGE", "WELCOME_TEXT"):
        val = getattr(text, attr, None)
        if isinstance(val, str) and val.strip():
            return val
    return (
        "Salom, <b>{name}</b>!\n\n"
        "Media yoki fayl havolasini yuboring — men uni yuklab yuboraman."
    )


def _help_template() -> str:
    for attr in ("HELP_MESSAGE", "HELP_TEXT"):
        val = getattr(text, attr, None)
        if isinstance(val, str) and val.strip():
            return val
    return _DEFAULT_HELP


@router.callback_query(F.data.startswith("ui:"))
async def handle_ui_callback(callback: CallbackQuery) -> None:
    action = (callback.data or "").split(":", 1)[-1]
    if action == "help":
        if callback.message:
            await callback.message.answer(_help_template())
    elif action == "close":
        if callback.message:
            try:
                await callback.message.delete()
            except Exception:
                pass
    await callback.answer()


@router.message(CommandStart())
async def cmd_start(message: Message, settings: Settings) -> None:
    user = message.from_user
    name = html.escape(user.full_name if user else "Foydalanuvchi")
    is_admin = bool(user and user.id in set(settings.auth_users or ()))

    tpl = _start_template()
    try:
        body = tpl.format(name=name)
    except Exception:
        body = tpl

    extra_admin = (
        "\n\n🛠 <b>Admin buyrug‘i:</b> <code>/admin</code> (A’zolar, Guruhlar, Barchaga xabar, Majburiy obuna)"
        if is_admin
        else ""
    )
    await message.answer(f"{body}{extra_admin}")


@router.message(Command("help"))
async def cmd_help(message: Message, settings: Settings) -> None:
    user = message.from_user
    is_admin = bool(user and user.id in set(settings.auth_users or ()))
    extra_admin = "\n\n🛠 <b>Admin:</b> <code>/admin</code>" if is_admin else ""
    await message.answer(f"{_help_template()}{extra_admin}")
