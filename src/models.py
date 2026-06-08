from dataclasses import dataclass, field

STATUS_META_LOADING = "meta_loading"
STATUS_PENDING = "pending"
STATUS_DOWNLOADING = "downloading"
STATUS_DONE = "done"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"


@dataclass
class DownloadTask:
    url: str
    title: str = "Загрузка метаданных..."
    channel: str = ""
    status: str = STATUS_META_LOADING
    progress: float = 0.0
    error: str = ""
    thumbnail_data: bytes | None = None
    meta_title: str = ""
    meta_author: str = ""
    meta_group: str = ""
    meta_album: str = ""
    meta_cover_path: str = ""


@dataclass
class RemoteTrack:
    title: str
    artists: str
    album: str
    source_url: str
    thumbnail_data: bytes | None = None
    status: str = STATUS_PENDING
    progress: float = 0.0
    error: str = ""
    local_file_path: str = ""


@dataclass
class LocalMusicTrack:
    title: str
    artists: str
    album: str
    file_path: str
    added_at: float
    thumbnail_data: bytes | None = None
    status: str = STATUS_DONE
    progress: float = 100.0
    error: str = ""


@dataclass
class PlaylistEntry:
    name: str
    source: str
    source_url: str
    tracks: list[RemoteTrack | LocalMusicTrack] = field(default_factory=list)
    is_loading: bool = False
    note: str = ""
    is_downloading: bool = False
    loading_current: int = 0
    loading_total: int = 0
