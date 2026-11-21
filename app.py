from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ChatMemberUpdated, Message, TelegramObject

from config import Settings
from utils.logging_config import setup_logging
from routers.admin import router as admin_router
from routers.callbacks import router as callbacks_router
from routers.commands import router as commands_router
from routers.intake import router as intake_router
from routers.thumbnails import router as thumbnails_router
from services.cooldown import CooldownManager
from services.inbox_store import InboxStore
from services.request_store import RequestStore
from services.thumbnail_store import ThumbnailStore


class InboxLoggingMiddleware(BaseMiddleware):
    def __init__(self, inbox_store: InboxStore) -> None:
        self.inbox_store = inbox_store

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            chat = event.chat
            user = event.from_user
            if user and user.is_bot:
                return await handler(event, data)

            chat_type = chat.type or "private"
            if chat_type == "private":
                chat_title = (
                    f"{user.first_name or ''} {user.last_name or ''}".strip()
                    if user
                    else "Foydalanuvchi"
                )
            else:
                chat_title = chat.title or f"Chat {chat.id}"

            full_name = (
                f"{user.first_name or ''} {user.last_name or ''}".strip()
                if user
                else "Noma'lum"
            )
            content = event.text or event.caption or ""
            if not content and event.sticker:
                content = f"[Sticker {event.sticker.emoji or ''}]".strip()
            elif not content and event.photo:
                content = "[Rasm]"
            elif not content and event.video:
                content = "[Video]"
            elif not content and event.document:
                content = f"[Fayl: {event.document.file_name or 'document'}]"

            reply_id = event.reply_to_message.message_id if event.reply_to_message else None

            self.inbox_store.record_incoming(
                chat_id=chat.id,
                chat_type=chat_type,
                chat_title=chat_title,
                chat_username=chat.username or (user.username if user else ""),
                user_id=user.id if user else None,
                full_name=full_name,
                user_username=user.username if user else "",
                text=content,
                tg_message_id=event.message_id,
                reply_to_tg_id=reply_id,
                save_contact=(chat_type == "private"),
            )

        return await handler(event, data)


def _build_chat_member_router(inbox_store: InboxStore) -> Router:
    member_router = Router(name="inbox_members")

    @member_router.my_chat_member()
    async def on_my_chat_member(update: ChatMemberUpdated, bot: Bot) -> None:
        chat = update.chat
        actor = update.from_user
        chat_type = chat.type or "group"
        title = chat.title or f"Chat {chat.id}"
        status_text = f"[Bot holati: {update.new_chat_member.status}]"
        member_cnt: int | None = None
        if chat_type != "private":
            try:
                c = await bot.get_chat_member_count(chat.id)
                if isinstance(c, int) and c > 0:
                    member_cnt = c
            except Exception:
                member_cnt = None

        inbox_store.record_incoming(
            chat_id=chat.id,
            chat_type=chat_type,
            chat_title=title,
            chat_username=chat.username,
            user_id=actor.id if actor else None,
            full_name=f"{actor.first_name or ''} {actor.last_name or ''}".strip() if actor else "Admin",
            user_username=actor.username if actor else "",
            text=status_text,
            save_contact=False,
            member_count=member_cnt,
        )

    return member_router


def create_dispatcher(settings: Settings, inbox_store: InboxStore | None = None) -> Dispatcher:
    store = inbox_store or InboxStore(settings.download_location / "inbox.sqlite3")
    dispatcher = Dispatcher()
    dispatcher.message.middleware(InboxLoggingMiddleware(store))
    dispatcher.include_router(_build_chat_member_router(store))
    dispatcher.include_router(admin_router)
    dispatcher.include_router(commands_router)
    dispatcher.include_router(thumbnails_router)
    dispatcher.include_router(intake_router)
    dispatcher.include_router(callbacks_router)
    dispatcher.workflow_data.update(
        settings=settings,
        inbox_store=store,
        cooldown=CooldownManager(timeout_seconds=settings.process_max_timeout),
        request_store=RequestStore(settings.requests_dir, settings.work_dir),
        thumbnail_store=ThumbnailStore(settings.thumbnails_dir),
    )
    return dispatcher


async def run() -> None:
    setup_logging()
    log = logging.getLogger(__name__)
    settings = Settings.from_env()
    settings.ensure_directories()
    inbox_store = InboxStore(settings.download_location / "inbox.sqlite3")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = create_dispatcher(settings, inbox_store=inbox_store)

    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
            log.info("Bot polling started")
            await dispatcher.start_polling(bot)
            break
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("Polling error, retrying in 3s: %s", exc)
            await asyncio.sleep(3)
