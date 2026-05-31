from pathlib import Path

from mutagen.id3 import APIC, ID3, ID3NoHeaderError

from .models import LocalMusicTrack, STATUS_DONE, STATUS_PENDING


def load_music_track(file_path: str, missing_status: str = STATUS_PENDING) -> LocalMusicTrack:
    path = Path(file_path)
    title = path.stem
    artists = ""
    album = ""
    thumbnail_data = None
    added_at = 0.0
    status = STATUS_DONE if path.exists() else missing_status
    error = ""

    if path.exists():
        stat = path.stat()
        added_at = getattr(stat, "st_birthtime", stat.st_ctime)
    else:
        error = "Файл не найден"

    try:
        tags = ID3(path)
        title_frame = tags.get("TIT2")
        artist_frame = tags.get("TPE1")
        album_frame = tags.get("TALB")
        if title_frame and getattr(title_frame, "text", None):
            title = str(title_frame.text[0]).strip() or title
        if artist_frame and getattr(artist_frame, "text", None):
            artists = str(artist_frame.text[0]).strip()
        if album_frame and getattr(album_frame, "text", None):
            album = str(album_frame.text[0]).strip()
        cover_frame = next((frame for frame in tags.values() if isinstance(frame, APIC)), None)
        if cover_frame is not None:
            thumbnail_data = cover_frame.data
    except ID3NoHeaderError:
        pass
    except Exception:
        if not path.exists():
            error = "Файл не найден"

    return LocalMusicTrack(
        title=title,
        artists=artists or "Неизвестный автор",
        album=album,
        file_path=str(path),
        added_at=added_at,
        thumbnail_data=thumbnail_data,
        status=status,
        progress=100.0 if status == STATUS_DONE else 0.0,
        error=error,
    )


def scan_music_directory(directory: str) -> list[LocalMusicTrack]:
    root = Path(directory)
    if not root.exists():
        return []

    tracks: list[LocalMusicTrack] = []
    for file_path in sorted(root.rglob("*.mp3")):
        tracks.append(load_music_track(str(file_path), missing_status=STATUS_PENDING))
    return tracks
