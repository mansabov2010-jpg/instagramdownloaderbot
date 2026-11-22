from __future__ import annotations

import asyncio
import base64
import json
import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from config import Settings
from services.progress import humanbytes
from utils.logging_config import redact_command, safe_url_label
from utils.models import DownloadArtifact, DownloadOption, ParsedInput


VIDEO_EXTENSIONS = {"mp4", "mkv", "webm", "mov"}
AUDIO_EXTENSIONS = {"mp3", "m4a", "aac", "wav", "flac", "opus", "weba"}
logger = logging.getLogger(__name__)
_COOKIE_FILE_PATH: Path | None = None

_MAX_PARALLEL_DOWNLOADS = 2
_DOWNLOAD_SEM: asyncio.Semaphore | None = None


def _download_sem() -> asyncio.Semaphore:
    global _DOWNLOAD_SEM
    if _DOWNLOAD_SEM is None:
        _DOWNLOAD_SEM = asyncio.Semaphore(_MAX_PARALLEL_DOWNLOADS)
    return _DOWNLOAD_SEM


def _is_youtube_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "youtu.be" or host.endswith(".youtube.com") or host == "youtube.com"


def _get_cookies_file(settings: Settings) -> Path | None:
    global _COOKIE_FILE_PATH
    raw_b64 = (settings.ytdlp_cookies_b64 or "").strip()
    if not raw_b64:
        return None

    if _COOKIE_FILE_PATH and _COOKIE_FILE_PATH.exists():
        return _COOKIE_FILE_PATH

    cleaned_b64 = "".join(raw_b64.split())
    decoded_bytes = base64.b64decode(cleaned_b64, validate=False)
    decoded_text = decoded_bytes.decode("utf-8", errors="ignore").lstrip()
    if decoded_text.startswith("[") or decoded_text.startswith("{"):
        logger.warning("YTDLP_COOKIES_B64 is JSON instead of Netscape format; skipping cookies")
        return None

    tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False)
    tmp.write(decoded_bytes)
    tmp.flush()
    tmp.close()
    _COOKIE_FILE_PATH = Path(tmp.name)
    return _COOKIE_FILE_PATH


def _command_base(parsed_input: ParsedInput, settings: Settings) -> list[str]:
    command = [
        "yt-dlp",
        "--no-warnings",
        "--no-playlist",
        "--socket-timeout", "20",
        "--retries", "3",
        "--fragment-retries", "3",
        "--extractor-retries", "2",
        "--concurrent-fragments", "4",
        "--no-mtime",
    ]
    if _is_youtube_url(parsed_input.source_url):
        command.extend(["--extractor-args", "youtube:player_client=tv_embedded,mweb,web"])
    cookies_file = _get_cookies_file(settings)
    if cookies_file:
        command.extend(["--cookies", str(cookies_file)])
    if settings.http_proxy:
        command.extend(["--proxy", settings.http_proxy])
    if parsed_input.username:
        command.extend(["--username", parsed_input.username])
    if parsed_input.password:
        command.extend(["--password", parsed_input.password])
    return command


async def _run_command(command: list[str], cwd: Path | None = None) -> tuple[str, str]:
    logger.info("Running yt-dlp | cwd=%s cmd=%s", cwd, redact_command(command))
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await process.communicate()
    except asyncio.CancelledError:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        try:
            await process.wait()
        except Exception:
            pass
        raise
    if process.returncode != 0:
        error_text = stderr.decode(errors="ignore").strip() or stdout.decode(errors="ignore").strip() or "yt-dlp failed"
        first_line = error_text.splitlines()[0]
        logger.warning("yt-dlp failed | err=%s", first_line)
        raise RuntimeError(first_line)
    return stdout.decode(errors="ignore").strip(), stderr.decode(errors="ignore").strip()


def _is_audio_only(format_data: dict) -> bool:
    format_note = (format_data.get("format_note") or "").lower()
    vcodec = (format_data.get("vcodec") or "").lower()
    acodec = (format_data.get("acodec") or "").lower()
    if "audio only" in format_note:
        return True
    if vcodec == "none" and acodec != "none":
        return True
    return False


def _label_for_format(format_data: dict, index: int) -> str:
    height = format_data.get("height")
    format_note = (
        (f"{height}p" if height else None)
        or format_data.get("format_note")
        or format_data.get("format")
        or f"Format {index + 1}"
    )
    size = format_data.get("filesize") or format_data.get("filesize_approx") or 0
    ext = format_data.get("ext") or "mp4"
    return f"Video {format_note} {ext} {humanbytes(size)}".strip()


def _ext_from_url(url: str) -> str | None:
    suffix = Path(urlparse(url).path).suffix
    return suffix.lstrip(".") if suffix else None


def _option_id(prefix: str, index: int) -> str:
    return f"{prefix}{index}"


async def probe_url(parsed_input: ParsedInput, settings: Settings) -> dict:
    command = _command_base(parsed_input, settings)
    command.extend(["--allow-dynamic-mpd", "--dump-single-json", parsed_input.source_url])
    logger.info("Probing source with yt-dlp | source=%s", safe_url_label(parsed_input.source_url))
    stdout, _ = await _run_command(command)
    if "\n" in stdout:
        stdout = stdout.splitlines()[0]
    return json.loads(stdout)


def build_quick_youtube_options() -> list[DownloadOption]:
    return [
        DownloadOption(
            option_id="quick_audio",
            label="Audio",
            send_type="audio",
            mode="youtube_quick",
        ),
        DownloadOption(
            option_id="quick_video",
            label="Video",
            send_type="video",
            mode="youtube_quick",
        ),
    ]


def build_ytdlp_options(info: dict) -> list[DownloadOption]:
    options: list[DownloadOption] = []
    formats = info.get("formats") or []
    seen_labels: set[str] = set()

    for index, format_data in enumerate(formats):
        if _is_audio_only(format_data):
            continue
        format_id = format_data.get("format_id")
        if not format_id:
            continue
        ext = (format_data.get("ext") or "mp4").lower()
        if ext in {"mhtml", "html", "json"}:
            continue
        label = _label_for_format(format_data, index)
        if label in seen_labels:
            continue
        seen_labels.add(label)
        options.append(
            DownloadOption(
                option_id=_option_id("fmt", len(options)),
                label=label,
                send_type="video",
                mode="ytdlp_format",
                format_id=str(format_id),
                file_ext=ext,
            )
        )

    if info.get("duration"):
        for quality in ("64k", "128k", "320k"):
            options.append(
                DownloadOption(
                    option_id=_option_id("audio", len(options)),
                    label=f"MP3 ({quality})",
                    send_type="audio",
                    mode="ytdlp_audio",
                    file_ext="mp3",
                    audio_quality=quality,
                )
            )
    return options


def build_direct_options(
    parsed_input: ParsedInput, info: dict | None = None
) -> list[DownloadOption]:
    ext = None
    source_url = parsed_input.source_url
    if info:
        ext = info.get("ext")
    if not ext:
        ext = _ext_from_url(source_url)

    send_type = (
        "video"
        if (ext and ext.lower() in VIDEO_EXTENSIONS)
        else "audio"
        if (ext and ext.lower() in AUDIO_EXTENSIONS)
        else "document"
    )

    options = [
        DownloadOption(
            option_id="direct_primary",
            label="Media sifatida yuborish" if send_type != "document" else "Hujjat sifatida yuborish",
            send_type=send_type,
            mode="direct",
            file_ext=ext,
        )
    ]
    if send_type != "document":
        options.append(
            DownloadOption(
                option_id="direct_document",
                label="Hujjat sifatida yuborish",
                send_type="document",
                mode="direct",
                file_ext=ext,
            )
        )
    return options


def _pick_downloaded_file(work_dir: Path) -> Path:
    ignored_suffixes = {
        ".json",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".html",
        ".htm",
    }
    files = [
        path
        for path in work_dir.rglob("*")
        if path.is_file()
        and not path.name.endswith(".part")
        and path.suffix.lower() not in ignored_suffixes
    ]
    if not files:
        raise RuntimeError("Yuklangan media fayl topilmadi")
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0]


def _caption_from_info(info: dict, fallback: str) -> str:
    title = info.get("title")
    webpage = info.get("webpage_url")
    if title and webpage:
        return f'<b><a href="{webpage}">{title}</a></b>'
    return title or fallback


def _read_info_json(work_dir: Path) -> dict:
    for path in work_dir.rglob("*.info.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        return {"title": data.get("title"), "webpage_url": data.get("webpage_url")}
    return {}


def _build_video_selector(raw_format: str | None) -> str:
    fmt = (raw_format or "").strip()
    if not fmt:
        return "bestvideo*+bestaudio/best[ext=mp4]/best"
    if "+" in fmt:
        return f"{fmt}/bestvideo*+bestaudio/best[ext=mp4]/best"
    return f"{fmt}+bestaudio/{fmt}/bestvideo*+bestaudio/best[ext=mp4]/best"


async def _run_video_with_audio_fallback(
    parsed_input: ParsedInput,
    settings: Settings,
    work_dir: Path,
    format_selector: str,
    output_template: str,
    write_info_json: bool = False,
) -> None:
    cmd_aac = _command_base(parsed_input, settings)
    cmd_aac.extend(
        [
            "-f",
            format_selector,
            "--merge-output-format",
            "mp4",
            "--postprocessor-args",
            "ffmpeg:-c:v copy -c:a aac",
        ]
    )
    if write_info_json:
        cmd_aac.append("--write-info-json")
    cmd_aac.extend(["-o", output_template, parsed_input.source_url])

    try:
        await _run_command(cmd_aac, cwd=work_dir)
        return
    except Exception as exc:
        logger.info("AAC postprocess retry without custom args | reason=%s", exc)

    cmd_merge = _command_base(parsed_input, settings)
    cmd_merge.extend(
        [
            "-f",
            format_selector,
            "--merge-output-format",
            "mp4",
        ]
    )
    if write_info_json:
        cmd_merge.append("--write-info-json")
    cmd_merge.extend(["-o", output_template, parsed_input.source_url])
    await _run_command(cmd_merge, cwd=work_dir)


async def download_quick_youtube(
    parsed_input: ParsedInput,
    option: DownloadOption,
    settings: Settings,
    work_dir: Path,
) -> DownloadArtifact:
    info = await probe_url(parsed_input, settings)
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(work_dir / "%(title)s [%(id)s].%(ext)s")

    async with _download_sem():
        if option.option_id == "quick_audio":
            command = _command_base(parsed_input, settings)
            command.extend(
                [
                    "-f",
                    "bestaudio/best",
                    "--extract-audio",
                    "--audio-format",
                    "mp3",
                    "-o",
                    output_template,
                    parsed_input.source_url,
                ]
            )
            await _run_command(command, cwd=work_dir)
            send_type = "audio"
        else:
            selector = "bestvideo*+bestaudio/best[ext=mp4]/best"
            await _run_video_with_audio_fallback(
                parsed_input=parsed_input,
                settings=settings,
                work_dir=work_dir,
                format_selector=selector,
                output_template=output_template,
                write_info_json=False,
            )
            send_type = "video"

    file_path = _pick_downloaded_file(work_dir)
    return DownloadArtifact(
        path=file_path,
        file_name=file_path.name,
        send_type=send_type,
        caption=_caption_from_info(info, file_path.stem),
    )


async def download_selected_format(
    parsed_input: ParsedInput,
    option: DownloadOption,
    info: dict,
    settings: Settings,
    work_dir: Path,
) -> DownloadArtifact:
    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(work_dir / "%(title)s [%(id)s].%(ext)s")

    async with _download_sem():
        if option.mode == "ytdlp_audio":
            command = _command_base(parsed_input, settings)
            command.extend(
                [
                    "--extract-audio",
                    "--audio-format",
                    option.file_ext or "mp3",
                    "--audio-quality",
                    option.audio_quality or "128k",
                    "-o",
                    output_template,
                    parsed_input.source_url,
                ]
            )
            await _run_command(command, cwd=work_dir)
            send_type = "audio"
        else:
            selector = _build_video_selector(option.format_id)
            await _run_video_with_audio_fallback(
                parsed_input=parsed_input,
                settings=settings,
                work_dir=work_dir,
                format_selector=selector,
                output_template=output_template,
                write_info_json=not bool(info),
            )
            send_type = "video"

    file_path = _pick_downloaded_file(work_dir)
    caption_info = info or _read_info_json(work_dir)
    return DownloadArtifact(
        path=file_path,
        file_name=file_path.name,
        send_type=send_type,
        caption=_caption_from_info(caption_info, file_path.stem),
    )
