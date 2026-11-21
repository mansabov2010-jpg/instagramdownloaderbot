from __future__ import annotations

from datetime import datetime
import logging
import re

from aiogram import Bot, F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Settings
from services.cooldown import CooldownManager
from services.inbox_store import InboxStore
from services.request_store import RequestStore
from services.telegram_uploads import upload_artifact
from services.ytdlp import download_selected_format, probe_url
from utils.logging_config import safe_url_label
from utils.models import DownloadOption, ParsedInput

router = Router(name="intake")
logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MEDIA_HOST_RE = re.compile(
    r"(https?://)?(www\.|vm\.|vt\.|m\.)?(instagram\.com|instagr\.am|tiktok\.com|youtube\.com|youtu\.be)/\S+",
    re.IGNORECASE,
)


def _extract_media_url(raw_text: str) -> str | None:
    m = _URL_RE.search(raw_text or "")
    if m:
        url = m.group(0).rstrip(").,]>\"'")
        if _MEDIA_HOST_RE.search(url):
            return url
    m2 = _MEDIA_HOST_RE.search(raw_text or "")
    if m2:
        url = m2.group(0).rstrip(").,]>\"'")
        return url if url.startswith("http") else f"https://{url}"
    return None


async def _check_force_subscriptions(bot: Bot, inbox_store: InboxStore, user_id: int) -> list[dict]:
    subs = inbox_store.list_force_subs()
    if not subs:
        return []
    missing: list[dict] = []
    for item in subs:
        target = item["target"]
        try:
            member = await bot.get_chat_member(chat_id=target, user_id=user_id)
            status = getattr(member, "status", "")
            if status in ("left", "kicked"):
                missing.append(item)
        except Exception:
            missing.append(item)
    return missing


@router.message(F.text)
async def intake_message(
    message: Message,
    bot: Bot,
    settings: Settings,
    cooldown: CooldownManager,
    request_store: RequestStore,
    inbox_store: InboxStore,
) -> None:
    raw_text = (message.text or "").strip()
    if not raw_text or raw_text.startswith("/") or not message.from_user:
        return

    url = _extract_media_url(raw_text)
    if not url:
        return

    is_admin = message.from_user.id in set(settings.auth_users or ())
    if not is_admin:
        missing_subs = await _check_force_subscriptions(bot, inbox_store, message.from_user.id)
        if missing_subs:
            rows = []
            for idx, sub in enumerate(missing_subs, start=1):
                label = sub.get("title") or f"Kanal / Guruh #{idx}"
                rows.append([InlineKeyboardButton(text=f"✨ {label} ga a'zo bo'lish", url=sub["invite_url"])])
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
            await message.reply(
                "✨ <b>Botdan foydalanish uchun quyidagi kanal yoki guruhga obuna bo‘ling!</b>\n\n"
                "Obuna bo‘lganingizdan so‘ng havolani qayta yuboring — men darhol ishlayman.",
                reply_markup=kb,
            )
            return

    blocked_seconds = cooldown.check(message.from_user.id, settings.auth_users)
    if blocked_seconds:
        minutes = max(1, round(blocked_seconds / 60))
        await message.answer(f"⏳ Iltimos, {minutes} daqiqa kuting.")
        return

    logger.info(
        "Media link received | user=%s chat=%s source=%s",
        message.from_user.id,
        message.chat.id,
        safe_url_label(url),
    )

    started_at = datetime.now()
    status_msg = await message.reply("⏳ Video yuklanmoqda...")

    parsed = ParsedInput(source_url=url)
    try:
        info = await probe_url(parsed, settings)
    except Exception:
        info = {}

    chosen = DownloadOption(
        option_id="best_video",
        label="Video",
        send_type="video",
        mode="ytdlp_format",
        format_id="best[ext=mp4]/best",
        file_ext="mp4",
    )
    work_dir = settings.work_dir / f"dl_{message.chat.id}_{message.message_id}"

    try:
        artifact = await download_selected_format(
            parsed_input=parsed,
            option=chosen,
            info=info or {},
            settings=settings,
            work_dir=work_dir,
        )
        await upload_artifact(
            bot=bot,
            status_message=status_msg,
            source_message=message,
            artifact=artifact,
            thumbnail_path=None,
            started_at=started_at,
        )
    except Exception as exc:
        logger.warning("Download/upload failed (%s): %s", safe_url_label(url), exc)
        await status_msg.edit_text(f"❌ Yuklab bo‘lmadi: {exc}")
