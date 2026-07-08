from pathlib import Path


def sanitize_music_path_part(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    for char in '<>:"/\\|?*':
        text = text.replace(char, "_")
    text = " ".join(text.split()).strip()
    return text.rstrip(".")


def normalize_music_author(value: str) -> str:
    normalized = sanitize_music_path_part(value)
    if normalized in {"Неизвестный автор", "Unknown Artist"}:
        return ""
    return normalized


def build_music_target_directory(
    music_root: str,
    artist: str = "",
    album: str = "",
) -> str:
    root = Path(music_root)
    normalized_artist = normalize_music_author(artist)
    normalized_album = sanitize_music_path_part(album)

    if normalized_artist and normalized_album:
        return str(root / normalized_artist / normalized_album)
    if normalized_artist:
        return str(root / normalized_artist)
    if normalized_album:
        return str(root / normalized_album)
    return str(root)


def build_music_output_template(
    music_root: str,
    title: str = "",
    artist: str = "",
    album: str = "",
    separator: str = " - ",
) -> str:
    target_dir = Path(build_music_target_directory(music_root, artist, album))
    target_dir.mkdir(parents=True, exist_ok=True)

    normalized_title = sanitize_music_path_part(title) or "Без названия"
    file_name = f"{normalized_title}.%(ext)s"

    return str(target_dir / file_name)


def build_music_file_path(
    music_root: str,
    title: str = "",
    artist: str = "",
    album: str = "",
    extension: str = ".mp3",
    separator: str = " - ",
) -> str:
    output_template = build_music_output_template(
        music_root,
        title=title,
        artist=artist,
        album=album,
        separator=separator,
    )
    return output_template.replace(".%(ext)s", extension)


def ensure_unique_music_file_path(target_path: str) -> str:
    path = Path(target_path)
    if not path.exists():
        return str(path)

    counter = 2
    while True:
        candidate = path.with_name(f"{path.stem} ({counter}){path.suffix}")
        if not candidate.exists():
            return str(candidate)
        counter += 1
