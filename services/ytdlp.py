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
        discovered = sorted(
            str(path.relative_to(work_dir))
            for path in work_dir.rglob("*")
            if path.is_file()
        )
        logger.warning(
            "No downloaded media file found | work_dir=%s files=%s",
            work_dir,
            discovered,
        )
        raise RuntimeError("No file was downloaded")
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0]
