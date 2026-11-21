from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from config import Settings
from utils import text

router = Router(name="commands")


@router.callback_query(F.data.startswith("ui:"))
async def handle_ui_callback(callback: CallbackQuery) -> None:
    action = (callback.data or "").split(":", 1)[-1]
    if action == "help":
        if callback.message:
            await callback.message.answer(text.HELP_MESSAGE)
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

    extra_admin = (
        "\n\n🛠 <b>Admin buyrug‘i:</b> <code>/admin</code> (A’zolar, Guruhlar, Barchaga xabar, Majburiy obuna)"
        if is_admin
        else ""
    )
    await message.answer(f"{text.START_MESSAGE.format(name=name)}{extra_admin}")


@router.message(Command("help"))
async def cmd_help(message: Message, settings: Settings) -> None:
    user = message.from_user
    is_admin = bool(user and user.id in set(settings.auth_users or ()))
    extra_admin = "\n\n🛠 <b>Admin:</b> <code>/admin</code>" if is_admin else ""
    await message.answer(f"{text.HELP_MESSAGE}{extra_admin}")
