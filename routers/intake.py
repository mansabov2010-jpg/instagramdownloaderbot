from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import re
import time

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message

from config import Settings
from services.telegram_uploads import upload_artifact
from services.ytdlp import download_selected_format
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
        raise SkipHandler

    url = _extract_url(raw)
    if not url:
        raise SkipHandler

    status_msg = await message.reply("⏳ Video yuklanmoqda...")
    started_at = datetime.now()
    parsed = ParsedInput(source_url=url)

    try:
        # Alohida probe_url yo'q: u yt-dlp ni ikki marta ishga tushirib, vaqtni ikki baravar oshirardi.
        info: dict = {}

        chosen = DownloadOption(
            option_id="best_video",
            label="Video",
            send_type="video",
            mode="ytdlp_format",
            # 720p gacha bitta mp4 fayl: hajmi kichik, yuklash va Telegramga yuborish tez
            format_id="best[ext=mp4][height<=720]/best[ext=mp4]/best",
            file_ext="mp4",
        )
        work_dir = settings.work_dir / f"dl_{message.chat.id}_{message.message_id}"
        t0 = time.monotonic()
        try:
            artifact = await asyncio.wait_for(
                download_selected_format(
                    parsed_input=parsed,
                    option=chosen,
                    info=info,
                    settings=settings,
                    work_dir=work_dir,
                ),
                timeout=240,
            )
        except asyncio.TimeoutError:
            logger.error("Download timeout (240s) for %s", url)
            await status_msg.edit_text("❌ Yuklash juda uzoq davom etdi (4 daqiqa). Keyinroq qayta urinib ko'ring.")
            return
        t1 = time.monotonic()
        logger.info("TIMING download=%.1fs url=%s", t1 - t0, url)
        await upload_artifact(
            bot=bot,
            status_message=status_msg,
            source_message=message,
            artifact=artifact,
            thumbnail_path=None,
            started_at=started_at,
        )
        logger.info("TIMING upload=%.1fs url=%s", time.monotonic() - t1, url)
    except Exception as exc:
        logger.exception("Intake error for %s", url)
        await status_msg.edit_text(f"❌ Xato: {exc}")
