import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

import yt_dlp
from PyQt6.QtCore import QObject, pyqtSignal

from .music_paths import build_music_output_template
from .models import PlaylistEntry, RemoteTrack, STATUS_DONE, STATUS_ERROR, STATUS_SKIPPED
from .paths import resource_path


def is_working_ffmpeg_dir(directory: str) -> bool:
    ffmpeg_cmd = os.path.join(directory, "ffmpeg")
    ffprobe_cmd = os.path.join(directory, "ffprobe")
    if not (
        os.path.isfile(ffmpeg_cmd)
        and os.path.isfile(ffprobe_cmd)
        and os.access(ffmpeg_cmd, os.X_OK)
        and os.access(ffprobe_cmd, os.X_OK)
    ):
        return False

    env = os.environ.copy()
    path = env.get("PATH", "")
    env["PATH"] = f"{directory}:{path}" if path else directory
    ffmpeg_check = subprocess.run([ffmpeg_cmd, "-version"], capture_output=True, text=True, check=False, env=env)
    ffprobe_check = subprocess.run([ffprobe_cmd, "-version"], capture_output=True, text=True, check=False, env=env)
    return ffmpeg_check.returncode == 0 and ffprobe_check.returncode == 0


def resolve_ffmpeg_directory(explicit_path: str = "") -> str:
    bundled_dir = resource_path("bin")
    if is_working_ffmpeg_dir(bundled_dir):
        return bundled_dir

    explicit_path = explicit_path.strip()
    if explicit_path:
        if os.path.isdir(explicit_path):
            if is_working_ffmpeg_dir(explicit_path):
                return explicit_path
        else:
            explicit_dir = os.path.dirname(explicit_path)
            if is_working_ffmpeg_dir(explicit_dir):
                return explicit_dir

    for candidate_dir in ["/opt/homebrew/bin", "/opt/local/bin"]:
        if is_working_ffmpeg_dir(candidate_dir):
            return candidate_dir

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path and is_working_ffmpeg_dir(os.path.dirname(ffmpeg_path)):
        return os.path.dirname(ffmpeg_path)

    for candidate_dir in ["/usr/local/bin", "/usr/bin"]:
        if is_working_ffmpeg_dir(candidate_dir):
            return candidate_dir
    return ""


def resolve_ffmpeg_binary(ffmpeg_dir: str) -> str:
    if ffmpeg_dir:
        candidate = os.path.join(ffmpeg_dir, "ffmpeg")
        if os.path.exists(candidate):
            return candidate
    ffmpeg_path = shutil.which("ffmpeg")
    return ffmpeg_path or "ffmpeg"


class MetadataWorker(QObject):
    metadata_ready = pyqtSignal(int, str, str, object, str, object)
    finished = pyqtSignal()

    def __init__(self, index_url_pairs: list[tuple[int, str]]) -> None:
        super().__init__()
        self.index_url_pairs = index_url_pairs
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            for index, url in self.index_url_pairs:
                if self._cancelled:
                    break
                title = url
                channel = "Неизвестный канал"
                thumbnail_data = None
                error_text = ""
                extracted_meta = {
                    "title": "",
                    "author": "",
                    "group": "",
                    "album": "",
                }
                try:
                    info = ydl.extract_info(url, download=False)
                    title = info.get("title") or title
                    channel = (
                        info.get("channel")
                        or info.get("uploader")
                        or info.get("uploader_id")
                        or channel
                    )
                    thumbnail_url = info.get("thumbnail")
                    if thumbnail_url:
                        with urllib.request.urlopen(thumbnail_url, timeout=15) as response:
                            thumbnail_data = response.read()
                    extracted_meta = {
                        "title": (info.get("track") or info.get("title") or "").strip(),
                        "author": (
                            info.get("artist")
                            or info.get("uploader")
                            or info.get("channel")
                            or ""
                        ).strip(),
                        "group": (info.get("album_artist") or "").strip(),
                        "album": (info.get("album") or "").strip(),
                    }
                except Exception as exc:
                    error_text = str(exc)
                    channel = "Метаданные недоступны"
                self.metadata_ready.emit(
                    index,
                    title,
                    channel,
                    thumbnail_data,
                    error_text,
                    extracted_meta,
                )
        self.finished.emit()


class YouTubePlaylistWorker(QObject):
    playlist_ready = pyqtSignal(object)
    playlist_progress = pyqtSignal(int, int)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, playlist_url: str) -> None:
        super().__init__()
        self.playlist_url = playlist_url

    def run(self) -> None:
        try:
            options = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": "in_playlist",
            }
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(self.playlist_url, download=False)

            entries = info.get("entries") or []
            if not entries and isinstance(info, dict):
                entries = [info]
            tracks: list[RemoteTrack] = []
            total_tracks = len(entries)
            if total_tracks > 0:
                self.playlist_progress.emit(0, total_tracks)
            for index, entry in enumerate(entries, start=1):
                if not isinstance(entry, dict):
                    if total_tracks > 0:
                        self.playlist_progress.emit(index, total_tracks)
                    continue
                title = (entry.get("track") or entry.get("title") or "Без названия").strip()
                artists = (
                    entry.get("artist")
                    or entry.get("uploader")
                    or entry.get("channel")
                    or entry.get("creator")
                    or "Неизвестный автор"
                ).strip()
                album = (entry.get("album") or "").strip()
                track_url = (
                    entry.get("webpage_url")
                    or entry.get("url")
                    or ""
                ).strip()
                if track_url and not track_url.startswith("http"):
                    track_url = f"https://www.youtube.com/watch?v={track_url}"
                thumbnail_url = (entry.get("thumbnail") or "").strip()
                if not thumbnail_url:
                    thumbnails = entry.get("thumbnails") or []
                    if isinstance(thumbnails, list) and thumbnails:
                        thumbnail_url = str((thumbnails[-1] or {}).get("url") or "").strip()
                thumbnail_data = self._load_thumbnail(thumbnail_url)
                tracks.append(
                    RemoteTrack(
                        title=title,
                        artists=artists,
                        album=album,
                        source_url=track_url,
                        thumbnail_data=thumbnail_data,
                    )
                )
                if total_tracks > 0:
                    self.playlist_progress.emit(index, total_tracks)

            playlist = PlaylistEntry(
                name=(info.get("title") or "YouTube Playlist").strip(),
                source="youtube",
                source_url=self.playlist_url.strip(),
                tracks=tracks,
                note="" if tracks else "YouTube не вернул треки для этого плейлиста.",
            )
            self.playlist_ready.emit(playlist)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

    def _load_thumbnail(self, thumbnail_url: str) -> bytes | None:
        if not thumbnail_url:
            return None
        try:
            with urllib.request.urlopen(thumbnail_url, timeout=15) as response:
                return response.read()
        except Exception:
            return None


class YouTubePlaylistDownloadWorker(QObject):
    track_started = pyqtSignal(int)
    track_finished = pyqtSignal(int, str, str, str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        track_payloads: list[tuple[int, str, str, str, str]],
        output_dir: str,
        ffmpeg_location: str = "",
    ) -> None:
        super().__init__()
        self.track_payloads = track_payloads
        self.output_dir = output_dir
        self.ffmpeg_location = ffmpeg_location

    def run(self) -> None:
        try:
            for index, track_url, title, artists_text, album_name in self.track_payloads:
                self.track_started.emit(index)
                if not track_url.strip():
                    self.track_finished.emit(index, STATUS_SKIPPED, "", "Пустая ссылка YouTube.")
                    continue

                output_template = build_music_output_template(
                    self.output_dir,
                    title=title,
                    artist=artists_text,
                    album=album_name,
                    separator=" - ",
                )
                worker = DownloadWorker(
                    index,
                    track_url,
                    self.output_dir,
                    {
                        "title": title,
                        "artist": artists_text,
                        "album_artist": "",
                        "album": album_name,
                    },
                    "",
                    self.ffmpeg_location,
                    output_template=output_template,
                )
                result: dict[str, object] = {"success": False, "error": ""}

                def capture_finished(_index: int, success: bool, error_text: str) -> None:
                    result["success"] = success
                    result["error"] = error_text

                worker.finished.connect(capture_finished)
                worker.run()

                if bool(result["success"]):
                    local_file_path = output_template.replace("%(ext)s", "mp3")
                    self.track_finished.emit(index, STATUS_DONE, local_file_path, "")
                else:
                    self.track_finished.emit(
                        index,
                        STATUS_ERROR,
                        "",
                        str(result["error"] or "Не удалось загрузить трек YouTube."),
                    )
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class DownloadWorker(QObject):
    started = pyqtSignal(int)
    progress_changed = pyqtSignal(int, float)
    finished = pyqtSignal(int, bool, str)

    def __init__(
        self,
        index: int,
        url: str,
        output_dir: str,
        metadata_overrides: dict[str, str],
        cover_path: str,
        ffmpeg_location: str = "",
        output_template: str = "",
    ) -> None:
        super().__init__()
        self.index = index
        self.url = url
        self.output_dir = output_dir
        self.metadata_overrides = metadata_overrides
        self.cover_path = cover_path
        self.ffmpeg_location = ffmpeg_location
        self.output_template = output_template

    def _progress_hook(self, event: dict) -> None:
        status = event.get("status")
        if status == "downloading":
            total_bytes = event.get("total_bytes") or event.get("total_bytes_estimate")
            downloaded_bytes = event.get("downloaded_bytes", 0)
            if total_bytes:
                percent = max(0.0, min(100.0, downloaded_bytes * 100.0 / total_bytes))
                self.progress_changed.emit(self.index, percent)
        elif status == "finished":
            self.progress_changed.emit(self.index, 100.0)

    def run(self) -> None:
        self.started.emit(self.index)
        output_template = self.output_template or build_music_output_template(
            self.output_dir,
            title=self.metadata_overrides.get("title") or "%(title)s",
            artist=self.metadata_overrides.get("artist", ""),
            album=self.metadata_overrides.get("album", ""),
            separator=" - ",
        )
        output_dirname = os.path.dirname(output_template)
        if output_dirname:
            os.makedirs(output_dirname, exist_ok=True)
        ffmpeg_dir = self._resolve_ffmpeg_directory()
        ffmpeg_location = ffmpeg_dir
        ffmpeg_binary = self._resolve_ffmpeg_binary(ffmpeg_dir)
        options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "writethumbnail": True,
            "progress_hooks": [self._progress_hook],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                },
                {
                    "key": "FFmpegMetadata",
                },
                {
                    "key": "FFmpegThumbnailsConvertor",
                    "format": "jpg",
                },
                {
                    "key": "EmbedThumbnail",
                },
            ],
        }
        if ffmpeg_location:
            options["ffmpeg_location"] = ffmpeg_location
        original_path = os.environ.get("PATH", "")
        if ffmpeg_dir:
            os.environ["PATH"] = f"{ffmpeg_dir}:{original_path}" if original_path else ffmpeg_dir
        try:
            self._verify_ffmpeg_tools(ffmpeg_dir)
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(self.url, download=True)
                code = 0 if info else 1

                output_path = self._resolve_output_path(ydl, info)
                if code == 0 and output_path:
                    effective_metadata = self._build_effective_metadata(info)
                    self._apply_custom_metadata(
                        output_path,
                        effective_metadata,
                        ffmpeg_binary,
                    )
            self.finished.emit(self.index, code == 0, "" if code == 0 else "yt-dlp returned error")
        except Exception as exc:
            self.finished.emit(self.index, False, str(exc))
        finally:
            if ffmpeg_dir:
                os.environ["PATH"] = original_path

    def _resolve_ffmpeg_directory(self) -> str:
        return resolve_ffmpeg_directory(self.ffmpeg_location)

    def _resolve_ffmpeg_binary(self, ffmpeg_dir: str) -> str:
        return resolve_ffmpeg_binary(ffmpeg_dir)

    def _verify_ffmpeg_tools(self, ffmpeg_dir: str) -> None:
        ffmpeg_cmd = os.path.join(ffmpeg_dir, "ffmpeg") if ffmpeg_dir else "ffmpeg"
        ffprobe_cmd = os.path.join(ffmpeg_dir, "ffprobe") if ffmpeg_dir else "ffprobe"
        env = os.environ.copy()
        if ffmpeg_dir:
            path = env.get("PATH", "")
            env["PATH"] = f"{ffmpeg_dir}:{path}" if path else ffmpeg_dir
        ffmpeg_check = subprocess.run(
            [ffmpeg_cmd, "-version"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        ffprobe_check = subprocess.run(
            [ffprobe_cmd, "-version"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if ffmpeg_check.returncode != 0 or ffprobe_check.returncode != 0:
            ffmpeg_err = (ffmpeg_check.stderr or ffmpeg_check.stdout or "").strip()
            ffprobe_err = (ffprobe_check.stderr or ffprobe_check.stdout or "").strip()
            raise RuntimeError(
                "FFmpeg/FFprobe недоступны. "
                f"ffmpeg={ffmpeg_cmd} rc={ffmpeg_check.returncode}, "
                f"ffprobe={ffprobe_cmd} rc={ffprobe_check.returncode}. "
                f"ffmpeg_out={ffmpeg_err[-220:] if ffmpeg_err else 'none'}; "
                f"ffprobe_out={ffprobe_err[-220:] if ffprobe_err else 'none'}"
            )

    def _is_working_ffmpeg_dir(self, directory: str) -> bool:
        return is_working_ffmpeg_dir(directory)

    def _resolve_output_path(self, ydl: yt_dlp.YoutubeDL, info: dict | None) -> str:
        if not isinstance(info, dict):
            return ""

        requested = info.get("requested_downloads")
        if isinstance(requested, list) and requested:
            first = requested[0]
            if isinstance(first, dict):
                filepath = first.get("filepath")
                if isinstance(filepath, str) and filepath:
                    root, _ = os.path.splitext(filepath)
                    return f"{root}.mp3"

        filename = info.get("_filename")
        if isinstance(filename, str) and filename:
            root, _ = os.path.splitext(filename)
            return f"{root}.mp3"

        prepared = ydl.prepare_filename(info)
        root, _ = os.path.splitext(prepared)
        return f"{root}.mp3"

    def _build_effective_metadata(self, info: dict | None) -> dict[str, str]:
        info = info if isinstance(info, dict) else {}
        return {
            "title": (
                self.metadata_overrides.get("title")
                or info.get("track")
                or info.get("title")
                or ""
            ).strip(),
            "artist": (
                self.metadata_overrides.get("artist")
                or info.get("artist")
                or info.get("uploader")
                or info.get("channel")
                or ""
            ).strip(),
            "album_artist": (
                self.metadata_overrides.get("album_artist")
                or info.get("album_artist")
                or ""
            ).strip(),
            "album": (
                self.metadata_overrides.get("album")
                or info.get("album")
                or ""
            ).strip(),
        }

    def _apply_custom_metadata(
        self,
        output_path: str,
        effective_metadata: dict[str, str],
        ffmpeg_binary: str,
    ) -> None:
        if not os.path.exists(output_path):
            return
        if not any(effective_metadata.values()) and not (
            self.cover_path and os.path.exists(self.cover_path)
        ):
            return

        ffmpeg_args = [ffmpeg_binary, "-y", "-i", output_path]
        use_cover = bool(self.cover_path and os.path.exists(self.cover_path))
        if use_cover:
            ffmpeg_args.extend(["-i", self.cover_path])

        ffmpeg_args.extend(["-map", "0:a:0"])
        if use_cover:
            ffmpeg_args.extend(
                [
                    "-map",
                    "1:v:0",
                    "-c:v",
                    "mjpeg",
                    "-disposition:v:0",
                    "attached_pic",
                ]
            )
        else:
            ffmpeg_args.extend(
                [
                    "-map",
                    "0:v?",
                    "-c:v",
                    "copy",
                ]
            )

        ffmpeg_args.extend(["-c:a", "copy", "-id3v2_version", "3"])

        for key, value in effective_metadata.items():
            if value:
                ffmpeg_args.extend(["-metadata", f"{key}={value}"])

        if use_cover:
            ffmpeg_args.extend(
                [
                    "-metadata:s:v",
                    "title=Album cover",
                    "-metadata:s:v",
                    "comment=Cover (front)",
                ]
            )

        temp_path = f"{output_path}.tmp.mp3"
        ffmpeg_args.append(temp_path)
        process = subprocess.run(
            ffmpeg_args,
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise RuntimeError(process.stderr.strip() or "FFmpeg metadata update failed")

        os.replace(temp_path, output_path)
