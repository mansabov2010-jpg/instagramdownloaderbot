from __future__ import annotations

import html
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from config import Settings
from utils import text

router = Router(name="commands")


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
