from __future__ import annotations

from datetime import datetime
import logging
import re

from aiogram import Bot, F, Router
from aiogram.types import Message

from config import Settings
from services.telegram_uploads import upload_artifact
from services.ytdlp import download_selected_format, probe_url
from utils.models import DownloadOption, ParsedInput

router = Router(name="intake")
logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_HOST_RE = re.compile(
    r"(instagram\.com|instagr\.am|tiktok\.com|youtube\.com|youtu\.be)",
    re.IGNORECASE,
)


def _extract_url(raw: str) -> str | None:
    m = _URL_RE.search(raw or "")
    if not m:
        return None
    u = m.group(0).rstrip(").,]>\"'")
    return u if _HOST_RE.search(u) else None


@router.message(F.text)
async def intake_message(
    message: Message,
    bot: Bot,
    settings: Settings,
) -> None:
    raw = (message.text or "").strip()
    if not raw or raw.startswith("/"):
        return

    url = _extract_url(raw)
    if not url:
        return

    status_msg = await message.reply("⏳ Video yuklanmoqda...")
    started_at = datetime.now()
    parsed = ParsedInput(source_url=url)

    try:
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
        logger.exception("Intake error for %s", url)
        await status_msg.edit_text(f"❌ Xato: {exc}")
