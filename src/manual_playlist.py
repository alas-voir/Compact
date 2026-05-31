from pathlib import Path

from .library_scanner import load_music_track
from .models import LocalMusicTrack, PlaylistEntry, STATUS_PENDING


def create_manual_playlist(playlists_dir: str, playlist_name: str) -> PlaylistEntry:
    name = playlist_name.strip()
    if not name:
        raise ValueError("Название плейлиста не может быть пустым.")

    root = Path(playlists_dir)
    root.mkdir(parents=True, exist_ok=True)
    file_path = root / f"{_sanitize_playlist_filename(name)}.m3u8"
    if file_path.exists():
        raise FileExistsError("Плейлист с таким именем уже существует.")

    file_path.write_text("#EXTM3U\n", encoding="utf-8")
    return PlaylistEntry(
        name=name,
        source="manual",
        source_url=str(file_path),
        tracks=[],
        note="Плейлист пуст",
    )


def load_manual_playlists(playlists_dir: str, music_library_dir: str) -> list[PlaylistEntry]:
    root = Path(playlists_dir)
    if not root.exists():
        return []

    playlists: list[PlaylistEntry] = []
    for file_path in sorted(root.glob("*.m3u8")):
        playlists.append(load_manual_playlist(str(file_path), music_library_dir))
    return playlists


def load_manual_playlist(playlist_path: str, music_library_dir: str) -> PlaylistEntry:
    path = Path(playlist_path)
    tracks = _parse_m3u8_tracks(path, Path(music_library_dir))
    note = "" if tracks else "Плейлист пуст"
    return PlaylistEntry(
        name=path.stem,
        source="manual",
        source_url=str(path),
        tracks=tracks,
        note=note,
    )


def remove_track_from_manual_playlist(playlist_path: str, track_file_path: str, music_library_dir: str) -> PlaylistEntry:
    path = Path(playlist_path)
    music_root = Path(music_library_dir)
    target_track = Path(track_file_path).resolve()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return load_manual_playlist(playlist_path, music_library_dir)

    result_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            result_lines.append(raw_line)
            continue
        resolved_path = _resolve_track_path(line, path.parent, music_root).resolve()
        if resolved_path == target_track:
            continue
        result_lines.append(raw_line)

    if not result_lines or result_lines[0].strip() != "#EXTM3U":
        result_lines.insert(0, "#EXTM3U")
    path.write_text("\n".join(result_lines).rstrip() + "\n", encoding="utf-8")
    return load_manual_playlist(playlist_path, music_library_dir)


def _parse_m3u8_tracks(playlist_path: Path, music_library_dir: Path) -> list[LocalMusicTrack]:
    try:
        lines = playlist_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    tracks: list[LocalMusicTrack] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        resolved_path = _resolve_track_path(line, playlist_path.parent, music_library_dir)
        tracks.append(load_music_track(str(resolved_path), missing_status=STATUS_PENDING))
    return tracks


def _resolve_track_path(entry: str, playlist_dir: Path, music_library_dir: Path) -> Path:
    path = Path(entry).expanduser()
    if path.is_absolute():
        return path

    candidate = (playlist_dir / path).resolve()
    if candidate.exists():
        return candidate

    candidate = (music_library_dir / path).resolve()
    if candidate.exists():
        return candidate

    return (playlist_dir / path).resolve()


def _sanitize_playlist_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    sanitized = "".join("_" if char in invalid_chars else char for char in name).strip()
    sanitized = sanitized.rstrip(".")
    return sanitized or "playlist"
