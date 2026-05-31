from pathlib import Path

from mutagen.id3 import APIC, ID3, ID3NoHeaderError, TALB, TIT2, TPE1, TPE2


def apply_mp3_metadata(
    file_path: str,
    *,
    title: str,
    author: str,
    group: str,
    album: str,
    cover_mode: str,
    cover_path: str,
) -> None:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    _set_text_frame(tags, TIT2, "TIT2", title)
    _set_text_frame(tags, TPE1, "TPE1", author)
    _set_text_frame(tags, TPE2, "TPE2", group)
    _set_text_frame(tags, TALB, "TALB", album)

    if cover_mode == "clear":
        tags.delall("APIC")
    elif cover_mode == "custom":
        cover_bytes = Path(cover_path).read_bytes()
        mime = _detect_mime(cover_path)
        tags.delall("APIC")
        tags.add(
            APIC(
                encoding=3,
                mime=mime,
                type=3,
                desc="Cover",
                data=cover_bytes,
            )
        )

    tags.save(path)


def _set_text_frame(tags: ID3, frame_type, frame_id: str, value: str) -> None:
    normalized = value.strip()
    if normalized:
        tags.setall(frame_id, [frame_type(encoding=3, text=[normalized])])
    else:
        tags.delall(frame_id)


def _detect_mime(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".bmp":
        return "image/bmp"
    return "image/jpeg"
