import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import yt_dlp
from PyQt6.QtCore import QObject, pyqtSignal
from yt_dlp.utils import DownloadError

from .logger import get_logger
from .music_paths import build_music_output_template
from .models import PlaylistEntry, RemoteTrack, STATUS_DONE, STATUS_ERROR, STATUS_SKIPPED
from .paths import resource_path
from .time_utils import format_duration_mmss
from .youtube_urls import normalize_youtube_track_url

logger = get_logger("elenveil.workers")


class WorkerCancelledError(Exception):
    pass


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
        logger.info("Resolved FFmpeg directory from bundled bin: %s", bundled_dir)
        return bundled_dir

    explicit_path = explicit_path.strip()
    if explicit_path:
        if os.path.isdir(explicit_path):
            if is_working_ffmpeg_dir(explicit_path):
                logger.info("Resolved FFmpeg directory from explicit directory: %s", explicit_path)
                return explicit_path
        else:
            explicit_dir = os.path.dirname(explicit_path)
            if is_working_ffmpeg_dir(explicit_dir):
                logger.info("Resolved FFmpeg directory from explicit file path: %s", explicit_dir)
                return explicit_dir

    for candidate_dir in ["/opt/homebrew/bin", "/opt/local/bin"]:
        if is_working_ffmpeg_dir(candidate_dir):
            logger.info("Resolved FFmpeg directory from default macOS path: %s", candidate_dir)
            return candidate_dir

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path and is_working_ffmpeg_dir(os.path.dirname(ffmpeg_path)):
        logger.info("Resolved FFmpeg directory from PATH: %s", os.path.dirname(ffmpeg_path))
        return os.path.dirname(ffmpeg_path)

    for candidate_dir in ["/usr/local/bin", "/usr/bin"]:
        if is_working_ffmpeg_dir(candidate_dir):
            logger.info("Resolved FFmpeg directory from fallback path: %s", candidate_dir)
            return candidate_dir
    logger.warning("Failed to resolve working FFmpeg directory | explicit_path=%s", explicit_path)
    return ""


def resolve_ffmpeg_binary(ffmpeg_dir: str) -> str:
    if ffmpeg_dir:
        candidate = os.path.join(ffmpeg_dir, "ffmpeg")
        if os.path.exists(candidate):
            return candidate
    ffmpeg_path = shutil.which("ffmpeg")
    return ffmpeg_path or "ffmpeg"


def build_app_ytdlp_options(**overrides) -> dict:
    options = {
        "ignoreconfig": True,
        "quiet": True,
        "no_warnings": True,
    }
    options.update(overrides)
    return options


def sanitize_ytdlp_options(options: dict) -> dict:
    sanitized: dict[str, object] = {}
    for key, value in options.items():
        lowered = key.lower()
        if "cookie" in lowered:
            if key == "cookiesfrombrowser":
                sanitized[key] = value
            elif value:
                sanitized[key] = "<set>"
            else:
                sanitized[key] = value
        elif key == "progress_hooks":
            sanitized[key] = f"<{len(value)} hooks>" if isinstance(value, list) else "<hooks>"
        elif key == "postprocessors":
            if isinstance(value, list):
                sanitized[key] = [item.get("key", "<unknown>") for item in value if isinstance(item, dict)]
            else:
                sanitized[key] = "<postprocessors>"
        else:
            sanitized[key] = value
    return sanitized


class MetadataWorker(QObject):
    metadata_ready = pyqtSignal(int, str, str, object, str, object)
    finished = pyqtSignal()

    def __init__(
        self,
        index_url_pairs: list[tuple[int, str]],
        ytdlp_options: dict | None = None,
    ) -> None:
        super().__init__()
        self.index_url_pairs = index_url_pairs
        self.ytdlp_options = dict(ytdlp_options or {})
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        options = build_app_ytdlp_options(
            skip_download=True,
            noplaylist=True,
        )
        options.update(self.ytdlp_options)
        logger.info(
            "MetadataWorker started | items=%s | options=%s",
            len(self.index_url_pairs),
            sanitize_ytdlp_options(options),
        )
        with yt_dlp.YoutubeDL(options) as ydl:
            for index, url in self.index_url_pairs:
                if self._cancelled:
                    logger.info("MetadataWorker cancelled")
                    break
                normalized_url = normalize_youtube_track_url(url)
                if normalized_url != url:
                    logger.info(
                        "MetadataWorker normalized URL | index=%s | from=%s | to=%s",
                        index,
                        url,
                        normalized_url,
                    )
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
                    logger.info("MetadataWorker extract_info start | index=%s | url=%s", index, normalized_url)
                    info = ydl.extract_info(normalized_url, download=False, process=False)
                    logger.info(
                        "MetadataWorker extract_info success | index=%s | title=%s | channel=%s",
                        index,
                        info.get("title"),
                        info.get("channel") or info.get("uploader"),
                    )
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
                    logger.exception(
                        "MetadataWorker extract_info failed | index=%s | url=%s",
                        index,
                        normalized_url,
                    )
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

    def __init__(self, playlist_url: str, ytdlp_options: dict | None = None) -> None:
        super().__init__()
        self.playlist_url = playlist_url
        self.ytdlp_options = dict(ytdlp_options or {})

    def run(self) -> None:
        try:
            options = build_app_ytdlp_options(
                skip_download=True,
                extract_flat="in_playlist",
            )
            options.update(self.ytdlp_options)
            logger.info(
                "YouTubePlaylistWorker started | url=%s | options=%s",
                self.playlist_url,
                sanitize_ytdlp_options(options),
            )
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
                track_url = normalize_youtube_track_url(track_url)
                thumbnail_url = (entry.get("thumbnail") or "").strip()
                if not thumbnail_url:
                    thumbnails = entry.get("thumbnails") or []
                    if isinstance(thumbnails, list) and thumbnails:
                        thumbnail_url = str((thumbnails[-1] or {}).get("url") or "").strip()
                thumbnail_data = self._load_thumbnail(thumbnail_url)
                duration_text = format_duration_mmss(
                    entry.get("duration_string") or entry.get("duration")
                )
                tracks.append(
                    RemoteTrack(
                        title=title,
                        artists=artists,
                        album=album,
                        source_url=track_url,
                        duration_text=duration_text,
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
            logger.info(
                "YouTubePlaylistWorker success | url=%s | playlist=%s | tracks=%s",
                self.playlist_url,
                playlist.name,
                len(tracks),
            )
            self.playlist_ready.emit(playlist)
        except Exception as exc:
            logger.exception("YouTubePlaylistWorker failed | url=%s", self.playlist_url)
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
    progress_changed = pyqtSignal(int, float)
    track_finished = pyqtSignal(int, str, str, str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        track_payloads: list[tuple[int, str, str, str, str]],
        output_dir: str,
        ffmpeg_location: str = "",
        ytdlp_options: dict | None = None,
    ) -> None:
        super().__init__()
        self.track_payloads = track_payloads
        self.output_dir = output_dir
        self.ffmpeg_location = ffmpeg_location
        self.ytdlp_options = dict(ytdlp_options or {})
        self._cancel_requested = False
        self._active_download_worker: DownloadWorker | None = None

    def cancel(self) -> None:
        self._cancel_requested = True
        if self._active_download_worker is not None:
            self._active_download_worker.cancel()

    def run(self) -> None:
        try:
            logger.info(
                "YouTubePlaylistDownloadWorker started | tracks=%s | output_dir=%s",
                len(self.track_payloads),
                self.output_dir,
            )
            for index, track_url, title, artists_text, album_name in self.track_payloads:
                if self._cancel_requested:
                    logger.info("YouTubePlaylistDownloadWorker cancelled before next track")
                    break
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
                    ytdlp_options=self.ytdlp_options,
                )
                result: dict[str, object] = {"success": False, "error": ""}

                def capture_finished(_index: int, success: bool, error_text: str) -> None:
                    result["success"] = success
                    result["error"] = error_text

                worker.finished.connect(capture_finished)
                worker.progress_changed.connect(self.progress_changed.emit)
                self._active_download_worker = worker
                try:
                    worker.run()
                finally:
                    self._active_download_worker = None

                if worker.was_cancelled():
                    logger.info(
                        "YouTubePlaylistDownloadWorker track cancelled | index=%s | url=%s",
                        index,
                        track_url,
                    )
                    self.track_finished.emit(
                        index,
                        STATUS_SKIPPED,
                        "",
                        "Загрузка отменена пользователем.",
                    )
                    break

                if bool(result["success"]):
                    local_file_path = output_template.replace("%(ext)s", "mp3")
                    logger.info(
                        "YouTubePlaylistDownloadWorker track finished | index=%s | path=%s",
                        index,
                        local_file_path,
                    )
                    self.track_finished.emit(index, STATUS_DONE, local_file_path, "")
                else:
                    logger.warning(
                        "YouTubePlaylistDownloadWorker track failed | index=%s | url=%s | error=%s",
                        index,
                        track_url,
                        result["error"],
                    )
                    self.track_finished.emit(
                        index,
                        STATUS_ERROR,
                        "",
                        str(result["error"] or "Не удалось загрузить трек YouTube."),
                    )
        except Exception as exc:
            logger.exception("YouTubePlaylistDownloadWorker failed")
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
        ytdlp_options: dict | None = None,
    ) -> None:
        super().__init__()
        self.index = index
        self.url = url
        self.output_dir = output_dir
        self.metadata_overrides = metadata_overrides
        self.cover_path = cover_path
        self.ffmpeg_location = ffmpeg_location
        self.output_template = output_template
        self.ytdlp_options = dict(ytdlp_options or {})
        self._cancel_requested = False
        self._was_cancelled = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def was_cancelled(self) -> bool:
        return self._was_cancelled

    def _progress_hook(self, event: dict) -> None:
        if self._cancel_requested:
            raise WorkerCancelledError("Загрузка отменена пользователем.")
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
        normalized_url = normalize_youtube_track_url(self.url)
        if normalized_url != self.url:
            logger.info(
                "DownloadWorker normalized URL | index=%s | from=%s | to=%s",
                self.index,
                self.url,
                normalized_url,
            )
        self.url = normalized_url
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
        options = build_app_ytdlp_options(
            format="bestaudio/best",
            outtmpl=output_template,
            noplaylist=True,
            writethumbnail=True,
            progress_hooks=[self._progress_hook],
            postprocessors=[
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
        )
        options.update(self.ytdlp_options)
        if ffmpeg_location:
            options["ffmpeg_location"] = ffmpeg_location
        logger.info(
            "DownloadWorker started | index=%s | url=%s | ffmpeg_dir=%s | output_template=%s | options=%s",
            self.index,
            normalized_url,
            ffmpeg_dir,
            output_template,
            sanitize_ytdlp_options(options),
        )
        original_path = os.environ.get("PATH", "")
        if ffmpeg_dir:
            os.environ["PATH"] = f"{ffmpeg_dir}:{original_path}" if original_path else ffmpeg_dir
        try:
            if self._cancel_requested:
                raise WorkerCancelledError("Загрузка отменена пользователем.")
            self._verify_ffmpeg_tools(ffmpeg_dir)
            info, output_path = self._download_with_fallback(options, ffmpeg_binary)
            code = 0 if info else 1
            logger.info(
                "DownloadWorker finished | index=%s | success=%s | output_path=%s",
                self.index,
                code == 0,
                output_path if 'output_path' in locals() else "",
            )
            self.finished.emit(self.index, code == 0, "" if code == 0 else "yt-dlp returned error")
        except WorkerCancelledError as exc:
            self._was_cancelled = True
            logger.info(
                "DownloadWorker cancelled | index=%s | url=%s",
                self.index,
                self.url,
            )
            self.finished.emit(self.index, False, str(exc))
        except Exception as exc:
            logger.exception(
                "DownloadWorker failed | index=%s | url=%s",
                self.index,
                self.url,
            )
            self.finished.emit(self.index, False, str(exc))
        finally:
            if ffmpeg_dir:
                os.environ["PATH"] = original_path

    def _download_with_fallback(self, options: dict, ffmpeg_binary: str) -> tuple[dict | None, str]:
        variants = self._build_download_option_variants(options)
        last_error: Exception | None = None
        for attempt_index, variant in enumerate(variants, start=1):
            if self._cancel_requested:
                raise WorkerCancelledError("Загрузка отменена пользователем.")
            logger.info(
                "DownloadWorker attempt | index=%s | attempt=%s/%s | options=%s",
                self.index,
                attempt_index,
                len(variants),
                sanitize_ytdlp_options(variant),
            )
            try:
                with yt_dlp.YoutubeDL(variant) as ydl:
                    info = ydl.extract_info(self.url, download=True)
                    output_path = self._resolve_output_path(ydl, info)
                    if info and output_path:
                        effective_metadata = self._build_effective_metadata(info)
                        self._apply_custom_metadata(
                            output_path,
                            effective_metadata,
                            ffmpeg_binary,
                        )
                    return info, output_path
            except DownloadError as exc:
                last_error = exc
                message = str(exc)
                logger.warning(
                    "DownloadWorker attempt failed | index=%s | attempt=%s | error=%s",
                    self.index,
                    attempt_index,
                    message,
                )
                if "Requested format is not available" not in message:
                    raise
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "DownloadWorker attempt failed with unexpected error | index=%s | attempt=%s | error=%s",
                    self.index,
                    attempt_index,
                    exc,
                )
                raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("Не удалось запустить загрузку yt-dlp.")

    def _build_download_option_variants(self, base_options: dict) -> list[dict]:
        variants: list[dict] = []

        def add_variant(format_selector: str, include_auth: bool) -> None:
            variant = dict(base_options)
            variant["format"] = format_selector
            if not include_auth:
                variant.pop("cookiesfrombrowser", None)
                variant.pop("cookiefile", None)
                variant.pop("cookies", None)
            if all(variant != existing for existing in variants):
                variants.append(variant)

        add_variant(str(base_options.get("format") or "bestaudio/best"), True)
        add_variant("bestaudio", True)
        add_variant("bestaudio*", True)
        add_variant(str(base_options.get("format") or "bestaudio/best"), False)
        add_variant("bestaudio", False)
        add_variant("bestaudio*", False)
        add_variant("best", False)
        return variants

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
        logger.info(
            "FFmpeg tools verified | ffmpeg=%s | ffprobe=%s",
            ffmpeg_cmd,
            ffprobe_cmd,
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


class SlicedTrackDownloadWorker(QObject):
    finished = pyqtSignal(bool, str)

    def __init__(
        self,
        url: str,
        output_dir: str,
        segments: list[dict[str, object]],
        thumbnail_data: bytes | None = None,
        ffmpeg_location: str = "",
        ytdlp_options: dict | None = None,
    ) -> None:
        super().__init__()
        self.url = url
        self.output_dir = output_dir
        self.segments = segments
        self.thumbnail_data = thumbnail_data
        self.ffmpeg_location = ffmpeg_location
        self.ytdlp_options = dict(ytdlp_options or {})

    def run(self) -> None:
        ffmpeg_dir = resolve_ffmpeg_directory(self.ffmpeg_location)
        ffmpeg_binary = resolve_ffmpeg_binary(ffmpeg_dir)
        normalized_url = normalize_youtube_track_url(self.url)
        if normalized_url != self.url:
            logger.info(
                "SlicedTrackDownloadWorker normalized URL | from=%s | to=%s",
                self.url,
                normalized_url,
            )
        self.url = normalized_url
        logger.info(
            "SlicedTrackDownloadWorker started | url=%s | segments=%s | ffmpeg_dir=%s",
            self.url,
            len(self.segments),
            ffmpeg_dir,
        )
        original_path = os.environ.get("PATH", "")
        if ffmpeg_dir:
            os.environ["PATH"] = f"{ffmpeg_dir}:{original_path}" if original_path else ffmpeg_dir

        try:
            verifier = DownloadWorker(
                0,
                self.url,
                self.output_dir,
                {},
                "",
                self.ffmpeg_location,
                ytdlp_options=self.ytdlp_options,
            )
            verifier._verify_ffmpeg_tools(ffmpeg_dir)

            with tempfile.TemporaryDirectory(prefix="elenveil-slice-") as temp_dir:
                source_path = self._download_source_media(temp_dir)
                default_cover_path = self._write_default_cover(temp_dir)
                for segment in self.segments:
                    self._export_segment(
                        source_path,
                        default_cover_path,
                        ffmpeg_binary,
                        segment,
                    )
            self.finished.emit(True, "")
        except Exception as exc:
            logger.exception("SlicedTrackDownloadWorker failed | url=%s", self.url)
            self.finished.emit(False, str(exc))
        finally:
            if ffmpeg_dir:
                os.environ["PATH"] = original_path

    def _download_source_media(self, temp_dir: str) -> str:
        outtmpl = os.path.join(temp_dir, "source.%(ext)s")
        options = build_app_ytdlp_options(
            format="best",
            outtmpl=outtmpl,
            noplaylist=True,
        )
        options.update(self.ytdlp_options)
        if self.ffmpeg_location:
            options["ffmpeg_location"] = self.ffmpeg_location
        logger.info(
            "SlicedTrackDownloadWorker source download | url=%s | options=%s",
            self.url,
            sanitize_ytdlp_options(options),
        )

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(self.url, download=True)
            requested = info.get("requested_downloads")
            if isinstance(requested, list) and requested:
                first = requested[0]
                if isinstance(first, dict):
                    filepath = first.get("filepath")
                    if isinstance(filepath, str) and filepath and os.path.exists(filepath):
                        return filepath
            prepared = ydl.prepare_filename(info)
            if os.path.exists(prepared):
                return prepared
        raise RuntimeError("Не удалось определить путь к исходному файлу для нарезки.")

    def _write_default_cover(self, temp_dir: str) -> str:
        if not self.thumbnail_data:
            return ""
        cover_path = os.path.join(temp_dir, "cover.jpg")
        with open(cover_path, "wb") as cover_file:
            cover_file.write(self.thumbnail_data)
        return cover_path

    def _export_segment(
        self,
        source_path: str,
        default_cover_path: str,
        ffmpeg_binary: str,
        segment: dict[str, object],
    ) -> None:
        title = str(segment.get("title") or "").strip()
        artist = str(segment.get("artist") or "").strip()
        album_artist = str(segment.get("group") or "").strip()
        album = str(segment.get("album") or "").strip()
        start = str(segment.get("start") or "").strip()
        end = str(segment.get("end") or "").strip()
        cover_mode = str(segment.get("cover_mode") or "keep").strip()
        custom_cover_path = str(segment.get("cover_path") or "").strip()

        output_template = build_music_output_template(
            self.output_dir,
            title=title,
            artist=artist,
            album=album,
            separator=" - ",
        )
        output_path = output_template.replace("%(ext)s", "mp3")

        duration = self._calculate_duration(start, end)
        ffmpeg_args = [
            ffmpeg_binary,
            "-y",
            "-ss",
            start,
            "-t",
            duration,
            "-i",
            source_path,
        ]

        cover_path = ""
        if cover_mode == "custom" and custom_cover_path and os.path.exists(custom_cover_path):
            cover_path = custom_cover_path
        elif cover_mode != "clear" and default_cover_path and os.path.exists(default_cover_path):
            cover_path = default_cover_path

        if cover_path:
            ffmpeg_args.extend(["-i", cover_path])

        ffmpeg_args.extend(["-map", "0:a:0"])
        if cover_path:
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

        ffmpeg_args.extend(["-c:a", "libmp3lame", "-q:a", "0", "-id3v2_version", "3"])

        metadata_values = {
            "title": title,
            "artist": artist,
            "album_artist": album_artist,
            "album": album,
        }
        for key, value in metadata_values.items():
            if value:
                ffmpeg_args.extend(["-metadata", f"{key}={value}"])

        if cover_path:
            ffmpeg_args.extend(
                [
                    "-metadata:s:v",
                    "title=Album cover",
                    "-metadata:s:v",
                    "comment=Cover (front)",
                ]
            )

        ffmpeg_args.append(output_path)
        process = subprocess.run(ffmpeg_args, capture_output=True, text=True, check=False)
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or f"Не удалось нарезать фрагмент '{title or start}'.")

    def _calculate_duration(self, start: str, end: str) -> str:
        start_seconds = self._timestamp_to_seconds(start)
        end_seconds = self._timestamp_to_seconds(end)
        if end_seconds <= start_seconds:
            raise RuntimeError(f"Некорректный интервал: {start} - {end}")
        return str(end_seconds - start_seconds)

    def _timestamp_to_seconds(self, value: str) -> float:
        parts = value.split(":")
        if not parts:
            raise RuntimeError(f"Некорректное время: {value}")
        try:
            if len(parts) == 1:
                return float(parts[0])
            if len(parts) == 2:
                minutes, seconds = parts
                return int(minutes) * 60 + float(seconds)
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except ValueError as exc:
            raise RuntimeError(f"Некорректное время: {value}") from exc
        raise RuntimeError(f"Некорректное время: {value}")
