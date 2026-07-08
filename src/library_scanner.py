from pathlib import Path

from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.mp3 import MP3

from .models import LocalMusicTrack, STATUS_DONE, STATUS_PENDING
from .time_utils import format_duration_mmss


def load_music_track(file_path: str, missing_status: str = STATUS_PENDING) -> LocalMusicTrack:
    path = Path(file_path)
    title = path.stem
    artists = ""
    album = ""
    group = ""
    track_number = 0
    thumbnail_data = None
    added_at = 0.0
    duration_text = ""
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
        group_frame = tags.get("TPE2")
        album_frame = tags.get("TALB")
        track_frame = tags.get("TRCK")
        if title_frame and getattr(title_frame, "text", None):
            title = str(title_frame.text[0]).strip() or title
        if artist_frame and getattr(artist_frame, "text", None):
            artists = str(artist_frame.text[0]).strip()
        if group_frame and getattr(group_frame, "text", None):
            group = str(group_frame.text[0]).strip()
        if album_frame and getattr(album_frame, "text", None):
            album = str(album_frame.text[0]).strip()
        if track_frame and getattr(track_frame, "text", None):
            raw_track_number = str(track_frame.text[0]).strip()
            raw_track_number = raw_track_number.split("/", 1)[0].strip()
            if raw_track_number.isdigit():
                track_number = int(raw_track_number)
        cover_frame = next((frame for frame in tags.values() if isinstance(frame, APIC)), None)
        if cover_frame is not None:
            thumbnail_data = cover_frame.data
    except ID3NoHeaderError:
        pass
    except Exception:
        if not path.exists():
            error = "Файл не найден"

    if path.exists():
        try:
            audio = MP3(path)
            duration_text = format_duration_mmss(getattr(audio.info, "length", None))
        except Exception:
            duration_text = ""

    return LocalMusicTrack(
        title=title,
        artists=artists or "Неизвестный автор",
        album=album,
        file_path=str(path),
        added_at=added_at,
        duration_text=duration_text,
        group=group,
        track_number=track_number,
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
