import base64
import hashlib
import json
from pathlib import Path

from .models import (
    PlaylistEntry,
    RemoteTrack,
    STATUS_DOWNLOADING,
    STATUS_META_LOADING,
    STATUS_PENDING,
)


def playlist_storage_name(playlist: PlaylistEntry) -> str:
    source = (playlist.source or "playlist").strip().lower()
    key = f"{source}|{playlist.source_url.strip()}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return f"{source}_{digest}.json"


def save_playlist(playlist: PlaylistEntry, playlists_dir: str) -> str:
    root = Path(playlists_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / playlist_storage_name(playlist)
    payload = {
        "name": playlist.name,
        "source": playlist.source,
        "source_url": playlist.source_url,
        "note": playlist.note,
        "tracks": [_track_to_dict(track) for track in playlist.tracks],
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(target)


def delete_playlist(playlist: PlaylistEntry, playlists_dir: str) -> None:
    target = Path(playlists_dir) / playlist_storage_name(playlist)
    if target.exists():
        target.unlink()


def load_playlists(playlists_dir: str) -> list[PlaylistEntry]:
    root = Path(playlists_dir)
    if not root.exists():
        return []

    playlists: list[PlaylistEntry] = []
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        playlist = _playlist_from_dict(data)
        if playlist is not None:
            playlists.append(playlist)
    return playlists


def _playlist_from_dict(data: dict) -> PlaylistEntry | None:
    if not isinstance(data, dict):
        return None

    tracks_data = data.get("tracks")
    if not isinstance(tracks_data, list):
        tracks_data = []

    tracks = [_track_from_dict(track_data) for track_data in tracks_data]
    return PlaylistEntry(
        name=str(data.get("name") or "Playlist").strip(),
        source=str(data.get("source") or "").strip(),
        source_url=str(data.get("source_url") or "").strip(),
        tracks=[track for track in tracks if track is not None],
        is_loading=False,
        note=str(data.get("note") or "").strip(),
        is_downloading=False,
    )


def _track_to_dict(track: RemoteTrack) -> dict:
    thumbnail = ""
    if track.thumbnail_data:
        thumbnail = base64.b64encode(track.thumbnail_data).decode("ascii")
    return {
        "title": track.title,
        "artists": track.artists,
        "album": track.album,
        "source_url": track.source_url,
        "duration_text": track.duration_text,
        "thumbnail_data": thumbnail,
        "status": track.status,
        "progress": track.progress,
        "error": track.error,
        "local_file_path": track.local_file_path,
    }


def _track_from_dict(data: dict) -> RemoteTrack | None:
    if not isinstance(data, dict):
        return None

    thumbnail_data = None
    thumbnail_encoded = str(data.get("thumbnail_data") or "").strip()
    if thumbnail_encoded:
        try:
            thumbnail_data = base64.b64decode(thumbnail_encoded)
        except Exception:
            thumbnail_data = None

    status = str(data.get("status") or STATUS_PENDING).strip()
    if status in (STATUS_DOWNLOADING, STATUS_META_LOADING):
        status = STATUS_PENDING

    return RemoteTrack(
        title=str(data.get("title") or "Без названия").strip(),
        artists=str(data.get("artists") or "Неизвестный автор").strip(),
        album=str(data.get("album") or "").strip(),
        source_url=str(data.get("source_url") or "").strip(),
        duration_text=str(data.get("duration_text") or "").strip(),
        thumbnail_data=thumbnail_data,
        status=status,
        progress=float(data.get("progress") or 0.0),
        error=str(data.get("error") or "").strip(),
        local_file_path=str(data.get("local_file_path") or "").strip(),
    )
