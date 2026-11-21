from __future__ import annotations

from datetime import datetime
import logging
import re

from aiogram import Bot, F, Router
from aiogram.types import Message

from config import Settings
from services.cooldown import CooldownManager
from services.parsing import extract_link_text, is_probable_youtube_url, parse_user_input
from services.request_store import RequestStore
from services.telegram_uploads import upload_artifact
from services.ytdlp import (
    build_direct_options,
    build_quick_youtube_options,
    build_ytdlp_options,
    download_selected_format,
    probe_url,
)
from utils import text
from utils.keyboards import format_keyboard
from utils.logging_config import safe_url_label
from utils.models import DownloadOption, StoredRequest

router = Router(name="intake")
logger = logging.getLogger(__name__)

_INSTAGRAM_RE = re.compile(r"(https?://)?(www\.)?(instagram\.com|instagr\.am)/\S+", re.IGNORECASE)


def _is_instagram_url(url: str) -> bool:
    return bool(_INSTAGRAM_RE.search(url or ""))


def _pick_group_video_option(options: list[DownloadOption]) -> DownloadOption:
    for opt in options:
        if opt.send_type == "video":
            return opt
    return DownloadOption(
        option_id="group_ig_video",
        label="Video",
        send_type="video",
        mode="ytdlp_format",
        format_id="best",
        file_ext="mp4",
    )


@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text)
async def intake_message(
    message: Message,
    bot: Bot,
    settings: Settings,
    cooldown: CooldownManager,
    request_store: RequestStore,
) -> None:
    raw_text = message.text or ""
    if not extract_link_text(raw_text, message.entities):
        return

    if not message.from_user:
        return

    parsed = parse_user_input(raw_text, message.entities)
    is_group = message.chat.type in ("group", "supergroup")

    if is_group and not _is_instagram_url(parsed.source_url):
        return

    logger.info(
        "Incoming link | user=%s chat=%s type=%s source=%s",
        message.from_user.id,
        message.chat.id,
        message.chat.type,
        safe_url_label(parsed.source_url),
    )

    blocked_seconds = cooldown.check(message.from_user.id, settings.auth_users)
    if blocked_seconds:
        minutes = max(1, round(blocked_seconds / 60))
        await message.answer(text.RATE_LIMIT.format(minutes=minutes))
        return

    started_at = datetime.now()
    status_message = await message.reply(text.PROCESSING)

    if is_group and _is_instagram_url(parsed.source_url):
        try:
            info = await probe_url(parsed, settings)
        except RuntimeError:
            info = {}

        options = build_ytdlp_options(info) if info else []
        chosen = _pick_group_video_option(options)
        work_dir = settings.work_dir / f"grp_{message.chat.id}_{message.message_id}"

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
                status_message=status_message,
                source_message=message,
                artifact=artifact,
                thumbnail_path=None,
                started_at=started_at,
            )
        except Exception as exc:
            logger.warning("Group Instagram download failed | chat=%s err=%s", message.chat.id, exc)
            await status_message.edit_text(f"Video yuklanmadi: {exc}")
        return

    if is_probable_youtube_url(parsed.source_url):
        token = request_store.create_token()
        stored = StoredRequest(
            token=token,
            request_type="youtube_quick",
            parsed_input=parsed,
            options=build_quick_youtube_options(),
        )
        request_store.save(stored)
        await status_message.edit_text(
            text.QUICK_CHOICE,
            reply_markup=format_keyboard(token, stored.options),
        )
        return

    try:
        info = await probe_url(parsed, settings)
    except RuntimeError:
        info = None

    token = request_store.create_token()
    if info:
        options = build_ytdlp_options(info)
        request_type = "ytdlp_selection"
        if not options:
            options = build_direct_options(parsed, info=info)
            request_type = "direct_download"
    else:
        options = build_direct_options(parsed, info=None)
        request_type = "direct_download"

    stored = StoredRequest(
        token=token,
        request_type=request_type,
        parsed_input=parsed,
        options=options,
        info=info or {},
    )
    request_store.save(stored)
    await status_message.edit_text(
        text.FORMAT_SELECTION,
        reply_markup=format_keyboard(token, options),
    )
