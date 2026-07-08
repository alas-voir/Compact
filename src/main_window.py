import os
import shutil
import subprocess
import sys
import urllib.request

import yt_dlp
from PyQt6.QtCore import QEvent, QRectF, QSize, Qt, QThread, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPalette, QPixmap

try:
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    QSvgRenderer = None
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .dialogs import (
    ExperimentalImportDialog,
    MetadataDialog,
    SettingsDialog,
    SliceSegmentsDialog,
    dialog_theme_colors,
)
from .library_scanner import load_music_track, scan_music_directory
from .manual_playlist import (
    append_tracks_to_manual_playlist,
    create_manual_playlist,
    export_playlist_m3u8,
    load_manual_playlist,
    load_manual_playlists,
    remove_track_from_manual_playlist,
    rewrite_track_references_in_playlists,
    sanitize_playlist_filename,
)
from .metadata_editor import apply_mp3_metadata
from .models import (
    STATUS_DONE,
    STATUS_DOWNLOADING,
    STATUS_ERROR,
    STATUS_META_LOADING,
    STATUS_PENDING,
    STATUS_SKIPPED,
    DownloadTask,
    LocalMusicTrack,
    PlaylistEntry,
    RemoteTrack,
)
from .music_paths import (
    build_music_file_path,
    build_music_output_template,
    ensure_unique_music_file_path,
)
from .paths import resource_path
from .playlist_storage import (
    delete_playlist,
    load_playlists,
    playlist_storage_name,
    save_playlist,
)
from .settings import (
    load_elenveil_root_dir,
    load_theme_mode,
    load_youtube_auth_settings,
    save_elenveil_root_dir,
    save_theme_mode,
    save_youtube_auth_settings,
)
from .widgets import (
    AddCard,
    BackChevronButton,
    DownloadCard,
    DownloadQueueCard,
    HomeAuthorCard,
    HoverCoverLabel,
    PlaylistListItemWidget,
    RemoteTrackCard,
    SearchAlbumCard,
    SearchAuthorCard,
    SearchPlaylistCard,
)
from .workers import (
    DownloadWorker,
    MetadataWorker,
    SlicedTrackDownloadWorker,
    YouTubePlaylistDownloadWorker,
    YouTubePlaylistWorker,
)
from .ytdlp_auth import build_ytdlp_auth_options


class MainWindow(QMainWindow):
    PROJECT_VERSION = "0.5"
    PROJECT_GITHUB_URL = "https://github.com/ZERv3/Elenveil"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Elenveil")
        self.resize(1180, 720)
        self.startup_root_dir_warning = ""
        loaded_theme_mode = load_theme_mode()
        self.theme_mode = loaded_theme_mode or (
            "dark" if self._palette_is_dark(self.palette()) else "light"
        )
        self.apply_theme_mode(self.theme_mode, persist=False, update_ui=False)

        self.tasks: list[DownloadTask] = []
        self.cards: list[DownloadCard] = []
        self.download_queue_cards: list[DownloadQueueCard] = []
        self.download_queue_card_keys: list[str] = []
        self.playlists: list[PlaylistEntry] = []
        self.local_music_tracks: list[LocalMusicTrack] = []
        self.remote_track_cards: list[RemoteTrackCard] = []
        self.playlist_item_widgets: list[PlaylistListItemWidget] = []
        self.output_dir = ""
        self.ffmpeg_location = ""
        self.ffmpeg_auto_found = False
        youtube_auth = load_youtube_auth_settings()
        self.youtube_cookies_browser = youtube_auth.get("cookies_browser", "")
        self.youtube_cookies_file = youtube_auth.get("cookies_file", "")
        self.metadata_icon = QIcon()
        self.cover_pick_icon = QIcon()
        self.cover_reset_icon = QIcon()
        self.select_root_icon = QIcon()
        self.open_folder_icon = QIcon()
        self.reveal_icon = QIcon()
        self.gear_icon = QIcon()
        self.add_playlist_icon = QIcon()
        self.add_track_icon = QIcon()
        self.add_list_icon = QIcon()
        self.library_playlist_icon = QIcon()
        self.library_author_icon = QIcon()
        self.library_album_icon = QIcon()
        self.back_icon = QIcon()
        self.new_track_icon = QIcon()
        self.import_icon = QIcon()
        self.start_icon = QIcon()
        self.home_icon = QIcon()
        self.delete_icon = QIcon()
        self.settings_icon = QIcon()
        self.choose_folder_icon = QIcon()
        self.sort_date_icon = QIcon()
        self.sort_title_icon = QIcon()
        self.status_icons: dict[str, QIcon] = {}
        self.reload_theme_icons()

        self.metadata_thread: QThread | None = None
        self.metadata_worker: MetadataWorker | None = None
        self.download_thread: QThread | None = None
        self.download_worker: DownloadWorker | None = None
        self.youtube_thread: QThread | None = None
        self.youtube_worker: YouTubePlaylistWorker | None = None
        self.youtube_download_thread: QThread | None = None
        self.youtube_download_worker: YouTubePlaylistDownloadWorker | None = None
        self.pending_playlist_index: int | None = None
        self.active_remote_playlist_index: int | None = None
        self.active_youtube_download_queue: list[int] = []
        self.active_download_index: int | None = None
        self.single_download_task: DownloadTask | None = None
        self.downloads_popup: QDialog | None = None
        self.downloads_popup_frame: QFrame | None = None
        self.downloads_popup_layout: QVBoxLayout | None = None
        self.selected_task_index: int | None = None
        self.selected_experimental_track_index: int | None = None
        self.selected_experimental_track_indexes: set[int] = set()
        self.experimental_selection_anchor_index: int | None = None
        self.selected_playlist_index: int | None = None
        self.experimental_source_mode = "none"
        self.search_author_focus: str | None = None
        self.search_album_tracks: list[LocalMusicTrack] = []
        self.search_results_active = False
        self.last_search_query = ""
        self.library_view_mode = "playlists"
        self.selected_author_name: str | None = None
        self.selected_album_name: str | None = None
        self.author_sidebar_transition_guard = False
        self.current_collection_label = "—"
        self.sidebar_items: list[dict[str, object]] = []
        self.current_displayed_tracks: list[RemoteTrack | LocalMusicTrack] = []
        self.home_album_tracks_by_key: dict[tuple[str, str], list[LocalMusicTrack]] = {}
        self.sort_field = "date"
        self.sort_ascending = False
        self.animation_phase = False
        default_elenveil_root_dir = self.default_elenveil_root_dir()
        self.elenveil_root_dir = ""
        self.music_library_dir = ""
        self.playlists_dir = ""
        self.initialize_elenveil_root_dir(
            load_elenveil_root_dir() or default_elenveil_root_dir,
            default_elenveil_root_dir,
        )

        root = QWidget()
        root.setObjectName("appRoot")
        self.root_widget = root
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.select_elenveil_root_button = QPushButton()
        self.select_elenveil_root_button.setToolTip("Выбрать папку Elenveil")
        self.select_elenveil_root_button.setAccessibleName("Выбрать папку Elenveil")
        self.select_elenveil_root_button.setFixedSize(36, 36)
        self.select_elenveil_root_button.setStyleSheet(
            "QPushButton { background:#2e3136; border:1px solid #3b3f46; border-radius:8px; }"
            "QPushButton:hover { background:#373b43; }"
            "QPushButton:disabled { background:#2a2d33; border-color:#353941; }"
        )
        self.select_elenveil_root_button.clicked.connect(
            self.choose_elenveil_root_directory
        )
        self.open_music_folder_button = QPushButton()
        self.open_music_folder_button.setToolTip("Открыть папку Elenveil")
        self.open_music_folder_button.setAccessibleName("Открыть папку Elenveil")
        self.open_music_folder_button.setFixedSize(36, 36)
        self.open_music_folder_button.setStyleSheet(
            "QPushButton { background:#2e3136; border:1px solid #3b3f46; border-radius:8px; }"
            "QPushButton:hover { background:#373b43; }"
            "QPushButton:disabled { background:#2a2d33; border-color:#353941; }"
        )
        self.open_music_folder_button.clicked.connect(self.open_elenveil_music_folder)
        self.create_playlist_button = QPushButton("Добавить")
        self.create_playlist_button.setToolTip("Добавить")
        self.create_playlist_button.setAccessibleName("Добавить")
        self.create_playlist_button.setFixedHeight(36)
        self.create_playlist_button.setMinimumWidth(110)
        self.create_playlist_button.setMenu(self.build_add_menu())

        self.import_button = QPushButton()
        self.import_button.setToolTip("Импорт")
        self.import_button.setAccessibleName("Импорт")
        self.import_button.setFixedSize(36, 36)
        self.import_button.setStyleSheet(
            "QPushButton { background:#2e3136; border:1px solid #3b3f46; border-radius:8px; }"
            "QPushButton:hover { background:#373b43; }"
            "QPushButton:disabled { background:#2a2d33; border-color:#353941; }"
        )
        self.import_button.clicked.connect(self.import_links)
        self.new_track_button = QPushButton()
        self.new_track_button.setToolTip("Новый трек")
        self.new_track_button.setAccessibleName("Новый трек")
        self.new_track_button.setFixedSize(36, 36)
        self.new_track_button.setStyleSheet(
            "QPushButton { background:#2e3136; border:1px solid #3b3f46; border-radius:8px; }"
            "QPushButton:hover { background:#373b43; }"
            "QPushButton:disabled { background:#2a2d33; border-color:#353941; }"
        )
        self.new_track_button.clicked.connect(self.add_new_track_for_experimental_mode)
        self.start_button = QPushButton()
        self.start_button.setToolTip("Старт")
        self.start_button.setAccessibleName("Старт")
        self.start_button.setFixedSize(36, 36)
        self.start_button.setStyleSheet(
            "QPushButton { background:#2e3136; border:1px solid #3b3f46; border-radius:8px; }"
            "QPushButton:hover { background:#373b43; }"
            "QPushButton:disabled { background:#2a2d33; border-color:#353941; }"
        )
        self.start_button.clicked.connect(self.start_downloads)
        self.start_button.setEnabled(False)
        self.reload_theme_icons()

        self.ffmpeg_status_label = QLabel("FFmpeg: проверка...")
        self.ffmpeg_status_label.setStyleSheet("color:#b4bcc9; font-size:12px;")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards_layout.setContentsMargins(4, 4, 4, 4)
        self.cards_layout.setSpacing(8)
        self.add_card = AddCard()
        self.add_card.clicked.connect(self.add_link_from_dialog)
        self.cards_layout.addWidget(self.add_card)
        self.scroll_area.setWidget(self.cards_container)

        self.experimental_page = QWidget()
        experimental_page_layout = QVBoxLayout(self.experimental_page)
        experimental_page_layout.setContentsMargins(0, 0, 0, 0)
        experimental_page_layout.setSpacing(8)
        self.experimental_footer_widget = QWidget()
        self.experimental_footer_widget.setFixedHeight(44)
        self.experimental_footer_widget.setVisible(True)
        self.experimental_footer_layout = QHBoxLayout()
        self.experimental_footer_layout.setContentsMargins(0, 0, 0, 0)
        self.experimental_footer_layout.setSpacing(8)
        self.experimental_footer_widget.setLayout(self.experimental_footer_layout)

        self.settings_button = QPushButton()
        self.settings_button.setToolTip("Настройки")
        self.settings_button.setAccessibleName("Настройки")
        self.settings_button.setFixedSize(32, 32)
        self.settings_button.clicked.connect(self.show_settings_dialog)
        self.downloads_button = QPushButton("Загрузки")
        self.downloads_button.setFixedHeight(32)
        self.downloads_button.clicked.connect(self.show_downloads_menu)

        self.footer_left_section = QWidget()
        self.footer_left_layout = QHBoxLayout(self.footer_left_section)
        self.footer_left_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_left_layout.setSpacing(0)
        self.footer_left_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.footer_left_layout.addWidget(
            self.settings_button,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.footer_left_layout.addStretch(1)

        self.footer_center_section = QWidget()
        self.footer_center_layout = QHBoxLayout(self.footer_center_section)
        self.footer_center_layout.setContentsMargins(12, 6, 12, 6)
        self.footer_center_layout.setSpacing(8)
        self.footer_center_layout.addStretch(1)

        self.footer_right_section = QWidget()
        self.footer_right_layout = QHBoxLayout(self.footer_right_section)
        self.footer_right_layout.setContentsMargins(12, 6, 12, 6)
        self.footer_right_layout.setSpacing(8)
        self.footer_right_layout.addStretch(1)

        self.sort_date_button = self.create_text_header_button("")
        self.sort_title_button = self.create_text_header_button("")
        self.sort_date_button.clicked.connect(lambda: self.on_sort_requested("date"))
        self.sort_title_button.clicked.connect(lambda: self.on_sort_requested("title"))
        self.update_sort_button_labels()
        self.sort_date_button.setIcon(self.sort_date_icon)
        self.sort_date_button.setIconSize(QSize(18, 18))
        self.sort_title_button.setIcon(self.sort_title_icon)
        self.sort_title_button.setIconSize(QSize(18, 18))
        self.home_button = QPushButton()
        self.home_button.setFixedSize(36, 36)
        self.home_button.setToolTip("Домашняя страница")
        self.home_button.setAccessibleName("Домашняя страница")
        self.home_button.clicked.connect(self.show_home_page)
        self.track_search_scope = "tracks"
        self.track_search_edit = QLineEdit()
        self.track_search_edit.setPlaceholderText("Поиск по трекам")
        self.track_search_edit.setClearButtonEnabled(False)
        self.track_search_edit.setFixedHeight(36)
        self.track_search_edit.textChanged.connect(self.on_track_search_changed)
        self.track_search_edit.installEventFilter(self)
        self.track_search_icon_label = QLabel(self.track_search_edit)
        self.track_search_icon_label.setFixedSize(16, 16)
        self.track_search_icon_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.track_search_icon_label.setStyleSheet(
            "background:transparent; border:none;"
        )
        self.track_search_filter_button = QPushButton()
        self.track_search_filter_button.setFixedHeight(36)
        self.track_search_filter_button.setMinimumWidth(110)
        self.track_search_filter_button.setMenu(self.build_track_search_filter_menu())
        self.update_track_search_filter_button()
        self.delete_files_checkbox = QCheckBox("Удалять файлы")
        self.delete_files_checkbox.setChecked(False)
        self.delete_files_checkbox.setVisible(False)
        self.delete_files_checkbox.setStyleSheet(
            "QCheckBox { color:#b4bcc9; font-size:12px; spacing:6px; background:transparent; }"
            "QCheckBox::indicator { width:14px; height:14px; }"
            "QCheckBox::indicator:unchecked { border:1px solid #4a515c; background:#2e3136; border-radius:3px; }"
            "QCheckBox::indicator:checked { border:1px solid #5f9ee6; background:#5f9ee6; border-radius:3px; }"
        )

        self.experimental_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.experimental_splitter.setChildrenCollapsible(False)

        self.library_view_button = QPushButton()
        self.library_view_button.setProperty("icon_header_button", True)
        self.library_view_button.setMenu(self.build_library_view_menu())
        self.library_view_button.setToolTip("Режим библиотеки")
        self.library_view_button.setAccessibleName("Режим библиотеки")
        self.library_view_button.setFixedSize(40, 40)
        self.library_back_button = BackChevronButton()
        self.library_back_button.setToolTip("Назад")
        self.library_back_button.setAccessibleName("Назад")
        self.library_back_button.setVisible(False)
        self.library_back_button.clicked.connect(self.on_library_back_requested)
        self.reload_theme_icons()

        self.playlists_panel = QWidget()
        self.playlists_panel.setStyleSheet("background:transparent; border:none;")
        playlists_root_layout = QVBoxLayout(self.playlists_panel)
        playlists_root_layout.setContentsMargins(0, 0, 0, 0)
        playlists_root_layout.setSpacing(8)

        self.playlists_controls_panel, playlists_controls_layout = (
            self.create_section_panel(
                self.library_view_button,
                right_header_widgets=[
                    self.create_playlist_button,
                ],
            )
        )
        playlists_root_layout.addWidget(self.playlists_controls_panel)
        self.author_context_row = QWidget()
        self.author_context_row.setFixedHeight(30)
        self.author_context_row_layout = QHBoxLayout(self.author_context_row)
        self.author_context_row_layout.setContentsMargins(0, 0, 0, 0)
        self.author_context_row_layout.setSpacing(6)
        self.author_context_row_layout.addWidget(
            self.library_back_button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        self.author_context_label = QLabel("")
        self.author_context_label.setWordWrap(True)
        self.author_context_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.author_context_row_layout.addWidget(self.author_context_label, 1)
        self.author_context_right_spacer = QWidget()
        self.author_context_right_spacer.setFixedSize(30, 30)
        self.author_context_row_layout.addWidget(
            self.author_context_right_spacer,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        playlists_root_layout.addWidget(self.author_context_row)
        self.playlist_list_panel = QFrame()
        self.playlist_list_panel_layout = QVBoxLayout(self.playlist_list_panel)
        self.playlist_list_panel_layout.setContentsMargins(12, 12, 12, 12)
        self.playlist_list_panel_layout.setSpacing(10)
        self.playlist_list = QListWidget()
        self.playlist_list.setStyleSheet(
            "QListWidget { background:#20242a; border:none; padding:6px; }"
            "QListWidget::item { padding:0; margin:0 0 8px 0; border:none; }"
            "QListWidget::item:selected { background:transparent; }"
        )
        self.playlist_list_panel_layout.addWidget(self.playlist_list)
        playlists_root_layout.addWidget(self.playlist_list_panel, 1)

        self.tracks_panel = QWidget()
        self.tracks_panel.setStyleSheet("background:transparent; border:none;")
        tracks_layout = QVBoxLayout(self.tracks_panel)
        tracks_layout.setContentsMargins(0, 0, 0, 0)
        tracks_layout.setSpacing(8)

        self.tracks_search_panel = QFrame()
        self.tracks_search_panel.setFixedHeight(
            max(56, self.playlists_controls_panel.sizeHint().height())
        )
        tracks_search_layout = QHBoxLayout(self.tracks_search_panel)
        tracks_search_layout.setContentsMargins(12, 10, 12, 10)
        tracks_search_layout.setSpacing(8)
        tracks_search_layout.addWidget(self.home_button, 0)
        tracks_search_layout.addWidget(self.track_search_edit, 1)
        tracks_search_layout.addWidget(self.track_search_filter_button, 0)
        tracks_layout.addWidget(self.tracks_search_panel)

        self.tracks_toolbar_strip = QWidget()
        self.tracks_toolbar_strip.setFixedHeight(30)
        self.tracks_toolbar_layout = QHBoxLayout(self.tracks_toolbar_strip)
        self.tracks_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.tracks_toolbar_layout.setSpacing(8)
        self.tracks_toolbar_layout.addWidget(self.delete_files_checkbox, 0)
        self.tracks_toolbar_layout.addStretch(1)
        self.tracks_toolbar_layout.addWidget(self.start_button, 0)
        self.tracks_toolbar_layout.addWidget(self.sort_date_button, 0)
        self.tracks_toolbar_layout.addWidget(self.sort_title_button, 0)
        tracks_layout.addWidget(self.tracks_toolbar_strip)

        self.tracks_list_panel = QFrame()
        tracks_list_layout = QVBoxLayout(self.tracks_list_panel)
        tracks_list_layout.setContentsMargins(0, 0, 0, 0)
        tracks_list_layout.setSpacing(0)
        self.playlist_tracks_scroll = QScrollArea()
        self.playlist_tracks_scroll.setWidgetResizable(True)
        self.playlist_tracks_container = QWidget()
        self.playlist_tracks_layout = QVBoxLayout(self.playlist_tracks_container)
        self.playlist_tracks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.playlist_tracks_layout.setContentsMargins(4, 4, 4, 4)
        self.playlist_tracks_layout.setSpacing(8)
        self.playlist_tracks_empty = QLabel("Плейлист не выбран")
        self.playlist_tracks_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.playlist_tracks_empty.setStyleSheet(
            "font-size:14px; color:#8f98a6; padding:24px; background:transparent; border:none;"
        )
        self.playlist_tracks_layout.addWidget(self.playlist_tracks_empty)
        self.playlist_tracks_layout.addStretch(1)
        self.playlist_tracks_scroll.setWidget(self.playlist_tracks_container)
        tracks_list_layout.addWidget(self.playlist_tracks_scroll)
        tracks_layout.addWidget(self.tracks_list_panel, 1)

        self.metadata_panel, metadata_layout = self.create_section_panel("")
        self.metadata_panel_cover_path = ""
        self.metadata_panel_cover_mode = "keep"
        self.metadata_panel_dirty = False
        self.metadata_album_dirty = False
        self.metadata_track_dirty = False
        self.metadata_panel_updating = False
        self.metadata_panel_file_paths: list[str] = []
        self.metadata_panel_original_values: dict[str, str] = {}
        self.metadata_panel_mode = "generic"
        self.metadata_panel_current_track_path = ""
        self.metadata_panel_album_file_paths: list[str] = []

        self.metadata_album_section = QFrame()
        self.metadata_album_section.setObjectName("metadata_subsection")
        self.metadata_album_section_layout = QVBoxLayout(self.metadata_album_section)
        self.metadata_album_section_layout.setContentsMargins(10, 10, 10, 10)
        self.metadata_album_section_layout.setSpacing(10)
        metadata_layout.addWidget(self.metadata_album_section)

        self.metadata_cover_label = HoverCoverLabel("Нет\nобложки")
        self.metadata_cover_label.setFixedHeight(220)
        self.metadata_cover_label.pick_requested.connect(self.pick_metadata_panel_cover)
        self.metadata_cover_label.clear_requested.connect(
            self.clear_metadata_panel_cover
        )
        self.metadata_cover_label.set_overlay_icons(
            self.cover_pick_icon,
            self.cover_reset_icon,
        )
        self.metadata_album_section_layout.addWidget(self.metadata_cover_label)

        self.metadata_album_header = QLabel("Альбом", self.metadata_album_section)
        self.metadata_album_header.setVisible(False)
        self.metadata_pick_cover_button = self.metadata_cover_label.pick_button
        self.metadata_clear_cover_button = self.metadata_cover_label.clear_button

        self.metadata_album_form = QFormLayout()
        self.metadata_album_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.metadata_album_form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.metadata_album_form.setHorizontalSpacing(10)
        self.metadata_album_form.setVerticalSpacing(10)

        self.metadata_album_title_label = QLabel("Альбом")
        self.metadata_album_title_edit = QLineEdit()
        self.metadata_album_title_edit.textChanged.connect(
            self.on_metadata_panel_changed
        )
        self.metadata_album_title_clear_button = self.create_metadata_clear_button(
            "Очистить название альбома"
        )
        self.metadata_album_title_clear_button.clicked.connect(
            self.metadata_album_title_edit.clear
        )
        self.metadata_album_title_row = self.create_metadata_edit_row(
            self.metadata_album_title_edit,
            self.metadata_album_title_clear_button,
        )
        self.metadata_album_form.addRow(
            self.metadata_album_title_label, self.metadata_album_title_row
        )

        self.metadata_album_author_label = QLabel("Автор")
        self.metadata_album_author_edit = QLineEdit()
        self.metadata_album_author_edit.textChanged.connect(
            self.on_metadata_panel_changed
        )
        self.metadata_album_author_clear_button = self.create_metadata_clear_button(
            "Очистить автора альбома"
        )
        self.metadata_album_author_clear_button.clicked.connect(
            self.metadata_album_author_edit.clear
        )
        self.metadata_album_author_row = self.create_metadata_edit_row(
            self.metadata_album_author_edit,
            self.metadata_album_author_clear_button,
        )
        self.metadata_album_form.addRow(
            self.metadata_album_author_label, self.metadata_album_author_row
        )
        self.metadata_album_section_layout.addLayout(self.metadata_album_form)

        self.metadata_album_buttons = QHBoxLayout()
        self.metadata_album_buttons.setContentsMargins(0, 6, 0, 0)
        self.metadata_album_buttons.setSpacing(10)
        self.metadata_album_buttons.addStretch(1)
        self.metadata_album_cancel_button = self.create_square_icon_button("Отмена")
        self.metadata_album_cancel_button.clicked.connect(
            self.cancel_album_metadata_panel_changes
        )
        self.metadata_album_save_button = self.create_square_icon_button("Сохранить")
        self.metadata_album_save_button.clicked.connect(
            self.save_album_metadata_panel_changes
        )
        self.metadata_album_buttons.addWidget(self.metadata_album_cancel_button)
        self.metadata_album_buttons.addWidget(self.metadata_album_save_button)
        self.metadata_album_section_layout.addLayout(self.metadata_album_buttons)

        self.metadata_track_section = QFrame()
        self.metadata_track_section.setObjectName("metadata_subsection")
        self.metadata_track_section_layout = QVBoxLayout(self.metadata_track_section)
        self.metadata_track_section_layout.setContentsMargins(10, 10, 10, 10)
        self.metadata_track_section_layout.setSpacing(10)
        metadata_layout.addWidget(self.metadata_track_section)

        self.metadata_album_separator = QFrame(self.metadata_panel)
        self.metadata_album_separator.setFrameShape(QFrame.Shape.HLine)
        self.metadata_album_separator.setFrameShadow(QFrame.Shadow.Plain)
        self.metadata_album_separator.setVisible(False)

        self.metadata_track_header = QLabel("Трек", self.metadata_track_section)
        self.metadata_track_header.setVisible(False)

        self.metadata_track_form = QFormLayout()
        self.metadata_track_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.metadata_track_form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.metadata_track_form.setHorizontalSpacing(10)
        self.metadata_track_form.setVerticalSpacing(10)

        self.metadata_track_title_label = QLabel("Трек")
        self.metadata_track_title_edit = QLineEdit()
        self.metadata_track_title_edit.textChanged.connect(
            self.on_metadata_panel_changed
        )
        self.metadata_track_form.addRow(
            self.metadata_track_title_label, self.metadata_track_title_edit
        )

        self.metadata_track_number_label = QLabel("Номер")
        self.metadata_track_number_edit = QLineEdit()
        self.metadata_track_number_edit.textChanged.connect(
            self.on_metadata_panel_changed
        )
        self.metadata_track_form.addRow(
            self.metadata_track_number_label, self.metadata_track_number_edit
        )

        self.metadata_track_location_label = QLabel("Расположение")
        self.metadata_track_location_button = self.create_text_header_button(
            "Открыть расположение"
        )
        self.metadata_track_location_button.clicked.connect(
            self.open_metadata_panel_track_location
        )
        self.metadata_track_form.addRow(
            self.metadata_track_location_label, self.metadata_track_location_button
        )
        self.metadata_track_section_layout.addLayout(self.metadata_track_form)

        self.metadata_track_buttons = QHBoxLayout()
        self.metadata_track_buttons.setContentsMargins(0, 6, 0, 0)
        self.metadata_track_buttons.setSpacing(10)
        self.metadata_track_buttons.addStretch(1)
        self.metadata_track_cancel_button = self.create_square_icon_button("Отмена")
        self.metadata_track_cancel_button.clicked.connect(
            self.cancel_track_metadata_panel_changes
        )
        self.metadata_track_save_button = self.create_square_icon_button("Сохранить")
        self.metadata_track_save_button.clicked.connect(
            self.save_track_metadata_panel_changes
        )
        self.metadata_track_buttons.addWidget(self.metadata_track_cancel_button)
        self.metadata_track_buttons.addWidget(self.metadata_track_save_button)
        self.metadata_track_section_layout.addLayout(self.metadata_track_buttons)

        self.metadata_generic_section = QWidget()
        self.metadata_generic_section_layout = QVBoxLayout(
            self.metadata_generic_section
        )
        self.metadata_generic_section_layout.setContentsMargins(0, 0, 0, 0)
        self.metadata_generic_section_layout.setSpacing(10)
        metadata_layout.addWidget(self.metadata_generic_section)

        metadata_form = QFormLayout()
        metadata_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        metadata_form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        metadata_form.setHorizontalSpacing(10)
        metadata_form.setVerticalSpacing(10)

        self.metadata_title_label = QLabel("Название")
        self.metadata_title_edit = QLineEdit()
        self.metadata_title_edit.textChanged.connect(self.on_metadata_panel_changed)
        metadata_form.addRow(self.metadata_title_label, self.metadata_title_edit)

        self.metadata_source_label = QLabel("Источник")
        self.metadata_source_value = QLabel("—")
        self.metadata_source_value.setWordWrap(True)
        metadata_form.addRow(self.metadata_source_label, self.metadata_source_value)

        self.metadata_url_label = QLabel("Путь / URL")
        self.metadata_url_value = QLabel("—")
        self.metadata_url_value.setWordWrap(True)

        self.metadata_author_label = QLabel("Автор")
        self.metadata_author_edit = QLineEdit()
        self.metadata_author_edit.textChanged.connect(self.on_metadata_panel_changed)
        self.metadata_author_clear_button = self.create_metadata_clear_button(
            "Очистить автора"
        )
        self.metadata_author_clear_button.clicked.connect(
            self.metadata_author_edit.clear
        )
        self.metadata_author_row = self.create_metadata_edit_row(
            self.metadata_author_edit,
            self.metadata_author_clear_button,
        )
        metadata_form.addRow(self.metadata_author_label, self.metadata_author_row)

        self.metadata_group_label = QLabel("Группа")
        self.metadata_group_edit = QLineEdit()
        self.metadata_group_edit.textChanged.connect(self.on_metadata_panel_changed)
        self.metadata_group_clear_button = self.create_metadata_clear_button(
            "Очистить группу"
        )
        self.metadata_group_clear_button.clicked.connect(self.metadata_group_edit.clear)
        self.metadata_group_row = self.create_metadata_edit_row(
            self.metadata_group_edit,
            self.metadata_group_clear_button,
        )
        metadata_form.addRow(self.metadata_group_label, self.metadata_group_row)

        self.metadata_album_label = QLabel("Альбом")
        self.metadata_album_edit = QLineEdit()
        self.metadata_album_edit.textChanged.connect(self.on_metadata_panel_changed)
        self.metadata_album_clear_button = self.create_metadata_clear_button(
            "Очистить альбом"
        )
        self.metadata_album_clear_button.clicked.connect(self.metadata_album_edit.clear)
        self.metadata_album_row = self.create_metadata_edit_row(
            self.metadata_album_edit,
            self.metadata_album_clear_button,
        )
        metadata_form.addRow(self.metadata_album_label, self.metadata_album_row)

        self.metadata_status_label = QLabel("Статус")
        self.metadata_status_value = QLabel("—")
        self.metadata_status_value.setWordWrap(True)

        self.metadata_generic_section_layout.addLayout(metadata_form)

        metadata_buttons = QHBoxLayout()
        metadata_buttons.setContentsMargins(0, 6, 0, 0)
        metadata_buttons.setSpacing(10)
        metadata_buttons.addStretch(1)
        self.metadata_cancel_button = self.create_square_icon_button("Отмена")
        self.metadata_cancel_button.clicked.connect(self.cancel_metadata_panel_changes)
        self.metadata_save_button = self.create_square_icon_button("Сохранить")
        self.metadata_save_button.clicked.connect(self.save_metadata_panel_changes)
        metadata_buttons.addWidget(self.metadata_cancel_button)
        metadata_buttons.addWidget(self.metadata_save_button)
        self.metadata_generic_section_layout.addLayout(metadata_buttons)
        metadata_layout.addStretch(1)

        self.experimental_splitter.addWidget(self.playlists_panel)
        self.experimental_splitter.addWidget(self.tracks_panel)
        self.experimental_splitter.addWidget(self.metadata_panel)
        self.experimental_splitter.setSizes([220, 620, 280])
        self.experimental_splitter.splitterMoved.connect(
            lambda *_: self.sync_footer_sections()
        )

        experimental_page_layout.addWidget(self.experimental_splitter)
        experimental_page_layout.addWidget(self.experimental_footer_widget)
        layout.addWidget(self.experimental_page)

        self.setCentralWidget(root)
        self.playlist_list.viewport().installEventFilter(self)
        self.playlist_list.currentRowChanged.connect(self.on_playlist_selected)
        self.restore_persisted_playlists()
        self.relayout_status_widgets()
        self.sync_footer_sections()
        self.update_metadata_panel()
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()
        self.set_library_view_mode("playlists")
        self.show_home_page()
        self.reload_theme_icons()
        self.apply_theme()
        if self.startup_root_dir_warning:
            QTimer.singleShot(0, self.show_startup_root_dir_warning)

        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(120)
        self.animation_timer.timeout.connect(self.animate_active_card)
        self.animation_timer.start()
        QTimer.singleShot(0, self.ensure_ffmpeg_available)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.PaletteChange:
            self.reload_theme_icons()
            self.apply_theme()
        super().changeEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.sync_footer_sections()
        self.position_track_search_icon()
        if getattr(self, "experimental_source_mode", "") == "home":
            self.render_home_page()
            return
        if self.has_active_track_search() and self.track_search_scope in {
            "albums",
            "authors",
            "playlists",
        }:
            self.render_track_search_results()

    def eventFilter(self, watched, event) -> bool:
        if (
            hasattr(self, "playlist_list")
            and watched is self.playlist_list.viewport()
            and self.author_sidebar_transition_guard
        ):
            if event.type() in {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
            }:
                return True
        if watched is self.track_search_edit:
            if event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self.position_track_search_icon)
                return False
            if (
                event.type() == QEvent.Type.KeyPress
                and getattr(event, "key", lambda: None)() == Qt.Key.Key_Escape
            ):
                self.clear_track_search_focus()
                return True
        return super().eventFilter(watched, event)

    def is_dark_theme(self) -> bool:
        if self.theme_mode in {"light", "dark"}:
            return self.theme_mode == "dark"
        return self._palette_is_dark(self.palette())

    def _palette_is_dark(self, palette: QPalette) -> bool:
        window_color = palette.color(QPalette.ColorRole.Window)
        text_color = palette.color(QPalette.ColorRole.WindowText)
        return text_color.lightness() > window_color.lightness()

    def build_theme_palette(self, mode: str) -> QPalette:
        palette = QPalette()
        if mode == "light":
            palette.setColor(QPalette.ColorRole.Window, QColor("#eef2f6"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#1f2630"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f5f7fa"))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#1f2630"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#1f2630"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#eef2f6"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1f2630"))
            palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.Link, QColor("#4e88d9"))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#4e88d9"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#788292"))
            return palette

        palette.setColor(QPalette.ColorRole.Window, QColor("#1c1f24"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#eef2f7"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#171717"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#202020"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#2e3136"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#eef2f7"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#eef2f7"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#2e3136"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#eef2f7"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff5c6a"))
        palette.setColor(QPalette.ColorRole.Link, QColor("#5f9ee6"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#355680"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#eef2f7"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8f98a6"))
        return palette

    def apply_theme_mode(
        self, mode: str, *, persist: bool = True, update_ui: bool = True
    ) -> None:
        normalized_mode = mode.strip().lower()
        if normalized_mode not in {"light", "dark"}:
            return
        self.theme_mode = normalized_mode
        app = QApplication.instance()
        if app is not None:
            app.setPalette(self.build_theme_palette(normalized_mode))
        if persist:
            save_theme_mode(normalized_mode)
        if update_ui and hasattr(self, "experimental_page"):
            self.reload_theme_icons()
            self.apply_theme()

    def themed_icon_path(self, base_name: str) -> str:
        suffix = "light" if self.is_dark_theme() else "dark"
        themed_path = resource_path("assets", "icons", f"{base_name}_{suffix}.svg")
        if os.path.exists(themed_path):
            return themed_path
        return resource_path("assets", "icons", f"{base_name}.svg")

    def themed_raster_icon(self, base_name: str, size: int = 18) -> QIcon:
        path = self.themed_icon_path(base_name)
        if QSvgRenderer is not None and path.lower().endswith(".svg"):
            renderer = QSvgRenderer(path)
            if renderer.isValid():
                pixel_ratio = max(1.0, self.devicePixelRatioF())
                raster_size = max(1, int(round(size * pixel_ratio)))
                pixmap = QPixmap(raster_size, raster_size)
                pixmap.setDevicePixelRatio(pixel_ratio)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                renderer.render(
                    painter,
                    QRectF(0.0, 0.0, float(size), float(size)),
                )
                painter.end()
                return QIcon(pixmap)
        source_icon = QIcon(path)
        if source_icon.isNull():
            return source_icon
        return QIcon(source_icon.pixmap(QSize(size, size)))

    def theme_colors(self) -> dict[str, str]:
        if self.is_dark_theme():
            return {
                "app_bg": "#1c1f24",
                "button_bg": "#2e3136",
                "button_hover": "#373b43",
                "button_border": "#3b3f46",
                "button_disabled_bg": "#2a2d33",
                "button_disabled_border": "#353941",
                "button_disabled_text": "#8b93a0",
                "panel_bg": "#202020",
                "panel_border": "#303030",
                "list_bg": "#171717",
                "text_primary": "#eef2f7",
                "text_secondary": "#b4bcc9",
                "text_muted": "#8f98a6",
                "checkbox_bg": "#2e3136",
                "checkbox_border": "#4a515c",
                "checkbox_checked": "#5f9ee6",
                "progress_bg": "#2a2d33",
                "progress_border": "#3a3f48",
                "footer_text": "#b4bcc9",
            }
        return {
            "app_bg": "#eef2f6",
            "button_bg": "#eef2f6",
            "button_hover": "#e4e9f0",
            "button_border": "#cad2de",
            "button_disabled_bg": "#f4f6f9",
            "button_disabled_border": "#d8dee7",
            "button_disabled_text": "#9aa4b2",
            "panel_bg": "#f7f9fc",
            "panel_border": "#d5dbe5",
            "list_bg": "#f5f7fa",
            "text_primary": "#1f2630",
            "text_secondary": "#556170",
            "text_muted": "#788292",
            "checkbox_bg": "#ffffff",
            "checkbox_border": "#b7c1ce",
            "checkbox_checked": "#4e88d9",
            "progress_bg": "#edf1f6",
            "progress_border": "#d0d7e2",
            "footer_text": "#556170",
        }

    def update_track_search_filter_button(self) -> None:
        title_map = {
            "tracks": "Треки",
            "albums": "Альбомы",
            "authors": "Авторы",
            "playlists": "Плейлисты",
        }
        placeholder_map = {
            "tracks": "Поиск по трекам",
            "albums": "Поиск по альбомам",
            "authors": "Поиск по авторам",
            "playlists": "Поиск по плейлистам",
        }
        self.track_search_filter_button.setText(title_map[self.track_search_scope])
        self.track_search_edit.setPlaceholderText(
            placeholder_map[self.track_search_scope]
        )

    def set_track_search_scope(self, scope: str) -> None:
        if scope not in {"tracks", "albums", "authors", "playlists"}:
            return
        if self.track_search_scope == scope:
            return
        self.track_search_scope = scope
        self.search_author_focus = None
        self.update_track_search_filter_button()
        self.refresh_experimental_source_view()

    def on_track_search_changed(self, _text: str) -> None:
        previous_query = self.last_search_query.strip()
        query = self.track_search_edit.text().strip()
        self.last_search_query = query
        self.search_author_focus = None
        if not query and previous_query:
            self.search_results_active = False
            if self.experimental_source_mode != "search_album_tracks":
                self.render_empty_track_results()
                self.update_metadata_panel()
                self.update_tracks_toolbar_visibility()
                return
        self.refresh_experimental_source_view()

    def clear_track_search_focus(self) -> None:
        self.track_search_edit.deselect()
        self.track_search_edit.clearFocus()
        self.playlist_tracks_scroll.setFocus(Qt.FocusReason.OtherFocusReason)

    def position_track_search_icon(self) -> None:
        if not hasattr(self, "track_search_icon_label"):
            return
        icon_size = self.track_search_icon_label.size()
        x_pos = self.track_search_edit.width() - icon_size.width() - 12
        y_pos = (self.track_search_edit.height() - icon_size.height()) // 2
        self.track_search_icon_label.move(max(8, x_pos), max(0, y_pos))

    def render_empty_track_results(self) -> None:
        self.clear_experimental_track_selection()
        self.current_displayed_tracks = []
        self.remote_track_cards = []
        self.clear_track_results_layout()
        self.playlist_tracks_layout.addStretch(1)

    def has_active_track_search(self) -> bool:
        return bool(self.track_search_edit.text().strip())

    def can_use_track_text_search(self) -> bool:
        return self.track_search_scope == "tracks"

    def _match_score(self, query: str, values: list[str]) -> int:
        normalized_query = query.strip().casefold()
        if not normalized_query:
            return 0
        best_score = 0
        for weight, raw_value in enumerate(values):
            value = str(raw_value or "").strip().casefold()
            if not value:
                continue
            field_penalty = weight * 40
            if value == normalized_query:
                best_score = max(best_score, 1000 - field_penalty)
                continue
            if value.startswith(normalized_query):
                best_score = max(best_score, 850 - field_penalty)
            elif any(part.startswith(normalized_query) for part in value.split()):
                best_score = max(best_score, 700 - field_penalty)
            elif normalized_query in value:
                best_score = max(best_score, 500 - field_penalty)
        return best_score

    def search_track_results(
        self, query: str
    ) -> list[RemoteTrack] | list[LocalMusicTrack]:
        base_tracks = self.local_music_tracks
        scored_items: list[tuple[int, int, RemoteTrack | LocalMusicTrack]] = []
        for index, track in enumerate(base_tracks):
            score = self._match_score(
                query,
                [
                    getattr(track, "title", ""),
                ],
            )
            if score > 0:
                scored_items.append((score, -index, track))
        scored_items.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [track for _, _, track in scored_items]

    def build_album_search_results(
        self,
        query: str,
        *,
        author_filter: str | None = None,
    ) -> list[dict[str, object]]:
        grouped: dict[tuple[str, str], list[LocalMusicTrack]] = {}
        for track in self.local_music_tracks:
            album_name = track.album.strip()
            author_name = track.artists.strip()
            if not album_name:
                continue
            if author_filter is not None and author_name != author_filter:
                continue
            grouped.setdefault((album_name, author_name), []).append(track)

        results: list[dict[str, object]] = []
        for (album_name, author_name), tracks in grouped.items():
            score = self._match_score(query, [album_name, author_name])
            if score <= 0:
                continue
            thumbnail_data = next(
                (track.thumbnail_data for track in tracks if track.thumbnail_data),
                None,
            )
            results.append(
                {
                    "album": album_name,
                    "author": author_name,
                    "tracks": self.get_sorted_experimental_tracks(tracks),
                    "track_count": len(tracks),
                    "thumbnail_data": thumbnail_data,
                    "score": score,
                }
            )
        results.sort(
            key=lambda item: (
                int(item["score"]),
                str(item["album"]).casefold(),
                str(item["author"]).casefold(),
            ),
            reverse=True,
        )
        return results

    def build_author_search_results(self, query: str) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for author_name, tracks in self.grouped_tracks_by_author().items():
            score = self._match_score(query, [author_name])
            if score <= 0:
                continue
            album_count = len(
                {track.album.strip() for track in tracks if track.album.strip()}
            )
            results.append(
                {
                    "author": author_name,
                    "track_count": len(tracks),
                    "album_count": album_count,
                    "score": score,
                }
            )
        results.sort(
            key=lambda item: (int(item["score"]), str(item["author"]).casefold()),
            reverse=True,
        )
        return results

    def build_playlist_search_results(self, query: str) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for playlist_index, playlist in enumerate(self.playlists):
            score = self._match_score(query, [playlist.name])
            if score <= 0:
                continue
            author_names = {
                str(getattr(track, "artists", "") or "").strip()
                for track in playlist.tracks
                if str(getattr(track, "artists", "") or "").strip()
            }
            unique_covers: list[bytes] = []
            used_keys: set[str] = set()
            for track in playlist.tracks:
                cover_data = getattr(track, "thumbnail_data", None)
                if not cover_data:
                    continue
                album_name = str(getattr(track, "album", "") or "").strip()
                artists_name = str(getattr(track, "artists", "") or "").strip()
                title_name = str(getattr(track, "title", "") or "").strip()
                unique_key = (
                    f"album:{album_name.casefold()}"
                    if album_name
                    else f"single:{artists_name.casefold()}:{title_name.casefold()}"
                )
                if unique_key in used_keys:
                    continue
                used_keys.add(unique_key)
                unique_covers.append(cover_data)
                if len(unique_covers) == 4:
                    break
            results.append(
                {
                    "playlist_index": playlist_index,
                    "playlist_name": playlist.name,
                    "track_count": len(playlist.tracks),
                    "author_count": len(author_names),
                    "cover_items": unique_covers,
                    "score": score,
                }
            )
        results.sort(
            key=lambda item: (
                int(item["score"]),
                str(item["playlist_name"]).casefold(),
            ),
            reverse=True,
        )
        return results

    def apply_track_search_filter(
        self,
        tracks: list[RemoteTrack] | list[LocalMusicTrack],
    ) -> list[RemoteTrack] | list[LocalMusicTrack]:
        if self.track_search_scope != "tracks" or not self.can_use_track_text_search():
            return list(tracks)
        query = self.track_search_edit.text().strip().casefold()
        if not query:
            return list(tracks)

        def matches(track: RemoteTrack | LocalMusicTrack) -> bool:
            if self.track_search_scope == "albums":
                haystacks = [getattr(track, "album", "")]
            elif self.track_search_scope == "authors":
                haystacks = [
                    getattr(track, "artists", ""),
                    getattr(track, "channel", ""),
                    getattr(track, "group", ""),
                ]
            else:
                haystacks = [getattr(track, "title", "")]
            return any(query in str(value or "").casefold() for value in haystacks)

        return [track for track in tracks if matches(track)]

    def should_show_track_download_control(self) -> bool:
        if (
            self.experimental_source_mode == "playlist"
            and self.selected_playlist_index is not None
            and 0 <= self.selected_playlist_index < len(self.playlists)
        ):
            return self.playlists[self.selected_playlist_index].source == "youtube"
        return False

    def should_show_track_sort_controls(self) -> bool:
        return self.experimental_source_mode in {
            "all_music",
            "playlist",
            "author_collection",
            "album",
            "search_album_tracks",
        }

    def show_home_page(self) -> None:
        self.track_search_edit.blockSignals(True)
        self.track_search_edit.clear()
        self.track_search_edit.blockSignals(False)
        self.last_search_query = ""
        self.search_results_active = False
        self.search_author_focus = None
        self.experimental_source_mode = "home"
        self.current_collection_label = "Домашняя страница"
        self.selected_playlist_index = None
        self.selected_album_name = None
        self.selected_author_name = None
        self.clear_track_search_focus()
        self.clear_experimental_track_selection()
        self.render_home_page()
        self.update_metadata_panel()
        self.update_tracks_toolbar_visibility()

    def update_tracks_toolbar_visibility(self) -> None:
        show_download = self.should_show_track_download_control()
        show_sort = self.should_show_track_sort_controls()
        self.start_button.setVisible(show_download)
        self.sort_date_button.setVisible(show_sort)
        self.sort_title_button.setVisible(show_sort)
        self.delete_files_checkbox.setVisible(
            self.experimental_source_mode == "playlist"
        )

    def dialog_theme_colors(self) -> dict[str, str]:
        return dialog_theme_colors(self.is_dark_theme())

    def style_simple_dialog(self, dialog: QDialog) -> None:
        colors = self.dialog_theme_colors()
        dialog.setStyleSheet(
            "QDialog {"
            f"background:{colors['dialog_bg']};"
            f"color:{colors['text_primary']};"
            "}"
            "QLabel {"
            f"color:{colors['text_primary']};"
            "background:transparent;"
            "font-size:13px;"
            "font-weight:700;"
            "}"
            "QLineEdit, QComboBox, QSpinBox {"
            f"background:{colors['input_bg']};"
            f"border:1px solid {colors['input_border']};"
            "border-radius:8px;"
            f"color:{colors['text_primary']};"
            "padding:6px 8px;"
            "selection-background-color:#4e88d9;"
            "}"
            "QComboBox::drop-down { border:none; width:28px; }"
            "QComboBox QAbstractItemView {"
            f"background:{colors['panel_bg']};"
            f"border:1px solid {colors['panel_border']};"
            f"color:{colors['text_primary']};"
            "selection-background-color:#4e88d9;"
            "}"
            "QPushButton, QToolButton {"
            f"background:{colors['panel_bg']};"
            f"border:1px solid {colors['panel_border']};"
            "border-radius:10px;"
            f"color:{colors['text_primary']};"
            "padding:8px 14px;"
            "font-size:12px;"
            "font-weight:700;"
            "}"
            f"QPushButton:hover, QToolButton:hover {{ background:{colors['panel_hover']}; }}"
            "QDialogButtonBox QPushButton {"
            f"background:{colors['panel_bg']};"
            f"border:1px solid {colors['panel_border']};"
            "border-radius:10px;"
            f"color:{colors['text_primary']};"
            "padding:8px 16px;"
            "font-size:12px;"
            "font-weight:700;"
            "min-width:110px;"
            "}"
            f"QDialogButtonBox QPushButton:hover {{ background:{colors['panel_hover']}; }}"
        )

    def style_input_dialog(self, dialog: QInputDialog) -> None:
        self.style_simple_dialog(dialog)
        dialog.resize(max(dialog.width(), 760), dialog.height())

    def create_text_header_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setFixedHeight(36)
        self.apply_header_button_style(button)
        return button

    def create_square_icon_button(self, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setToolTip(tooltip)
        button.setFixedSize(36, 36)
        self.apply_icon_button_style(button)
        return button

    def create_metadata_clear_button(self, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setToolTip(tooltip)
        button.setFixedSize(28, 28)
        button.setIconSize(QSize(14, 14))
        self.apply_icon_button_style(button)
        return button

    def create_metadata_edit_row(
        self,
        edit: QLineEdit,
        clear_button: QPushButton | None = None,
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(edit, 1)
        if clear_button is not None:
            layout.addWidget(clear_button, 0)
        return row

    def build_library_view_menu(self) -> QMenu:
        menu = QMenu(self)
        self.library_playlist_action = menu.addAction("Плейлисты")
        self.library_authors_action = menu.addAction("Авторы")
        self.library_albums_action = menu.addAction("Альбомы")
        self.library_playlist_action.triggered.connect(
            lambda: self.set_library_view_mode("playlists")
        )
        self.library_authors_action.triggered.connect(
            lambda: self.set_library_view_mode("authors")
        )
        self.library_albums_action.triggered.connect(
            lambda: self.set_library_view_mode("albums")
        )
        return menu

    def build_add_menu(self) -> QMenu:
        menu = QMenu(self)
        self.add_track_action = menu.addAction("Трек")
        self.add_list_action = menu.addAction("Список")
        self.add_playlist_action = menu.addAction("Плейлист")
        self.add_track_action.triggered.connect(
            self.add_new_track_for_experimental_mode
        )
        self.add_list_action.triggered.connect(self.import_links)
        self.add_playlist_action.triggered.connect(self.add_playlist)
        return menu

    def build_track_search_filter_menu(self) -> QMenu:
        menu = QMenu(self)
        self.track_search_tracks_action = menu.addAction("Треки")
        self.track_search_albums_action = menu.addAction("Альбомы")
        self.track_search_authors_action = menu.addAction("Авторы")
        self.track_search_playlists_action = menu.addAction("Плейлисты")
        self.track_search_tracks_action.triggered.connect(
            lambda: self.set_track_search_scope("tracks")
        )
        self.track_search_albums_action.triggered.connect(
            lambda: self.set_track_search_scope("albums")
        )
        self.track_search_authors_action.triggered.connect(
            lambda: self.set_track_search_scope("authors")
        )
        self.track_search_playlists_action.triggered.connect(
            lambda: self.set_track_search_scope("playlists")
        )
        return menu

    def create_section_panel(
        self,
        title: str | QWidget,
        left_header_widgets: list[QWidget] | None = None,
        right_header_widgets: list[QWidget] | None = None,
    ) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        if isinstance(title, QWidget):
            frame.section_title_label = None
            frame.section_title_widget = title
            header_row.addWidget(title)
        else:
            if title:
                title_label = QLabel(title)
                frame.section_title_label = title_label
                frame.section_title_widget = None
                header_row.addWidget(title_label)
            else:
                frame.section_title_label = None
                frame.section_title_widget = None
        for widget in left_header_widgets or []:
            header_row.addWidget(widget)
        header_row.addStretch(1)
        for widget in right_header_widgets or []:
            header_row.addWidget(widget)
        layout.addLayout(header_row)
        self.apply_section_panel_style(frame)
        return frame, layout

    def apply_header_button_style(self, button: QPushButton) -> None:
        colors = self.theme_colors()
        button.setStyleSheet(
            "QPushButton {"
            f"background:{colors['button_bg']};"
            f"border:1px solid {colors['button_border']};"
            "border-radius:8px;"
            "padding:0 12px;"
            f"color:{colors['text_primary']};"
            "font-size:12px;"
            "font-weight:600;"
            "}"
            "QPushButton::menu-indicator { image:none; width:0px; }"
            f"QPushButton:hover {{ background:{colors['button_hover']}; }}"
            "QPushButton:checked { background:#355680; border-color:#4b74a7; }"
            "QPushButton:disabled {"
            f"background:{colors['button_disabled_bg']};"
            f"border-color:{colors['button_disabled_border']};"
            f"color:{colors['button_disabled_text']};"
            "}"
        )

    def apply_icon_button_style(self, button: QPushButton) -> None:
        colors = self.theme_colors()
        button.setStyleSheet(
            "QPushButton {"
            f"background:{colors['button_bg']};"
            f"border:1px solid {colors['button_border']};"
            "border-radius:8px;"
            "}"
            f"QPushButton:hover {{ background:{colors['button_hover']}; }}"
            "QPushButton:disabled {"
            f"background:{colors['button_disabled_bg']};"
            f"border-color:{colors['button_disabled_border']};"
            "}"
        )

    def apply_toolbar_icon_button_style(self, button: QPushButton) -> None:
        colors = self.theme_colors()
        button.setStyleSheet(
            "QPushButton {"
            "background:transparent;"
            "border:none;"
            "padding:0 4px;"
            f"color:{colors['text_primary']};"
            "font-size:12px;"
            "font-weight:700;"
            "}"
            f"QPushButton:hover {{ color:{colors['text_secondary']}; }}"
            f"QPushButton:checked {{ color:{colors['text_primary']}; }}"
            f"QPushButton:disabled {{ color:{colors['text_muted']}; }}"
        )

    def horizontal_scrollbar_style(self) -> str:
        handle = (
            "rgba(127, 135, 148, 0.38)"
            if self.is_dark_theme()
            else "rgba(120, 130, 146, 0.30)"
        )
        handle_hover = (
            "rgba(127, 135, 148, 0.62)"
            if self.is_dark_theme()
            else "rgba(120, 130, 146, 0.48)"
        )
        return (
            "QScrollArea { background:transparent; border:none; }"
            "QScrollBar:horizontal {"
            "background:transparent;"
            "height:7px;"
            "margin:0 4px 0 4px;"
            "border:none;"
            "}"
            "QScrollBar::handle:horizontal {"
            f"background:{handle};"
            "border-radius:3px;"
            "min-width:28px;"
            "}"
            "QScrollBar::handle:horizontal:hover {"
            f"background:{handle_hover};"
            "}"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {"
            "width:0px;"
            "background:transparent;"
            "border:none;"
            "}"
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {"
            "background:transparent;"
            "}"
        )

    def vertical_scrollbar_style(self) -> str:
        handle = (
            "rgba(127, 135, 148, 0.45)"
            if self.is_dark_theme()
            else "rgba(120, 130, 146, 0.35)"
        )
        handle_hover = (
            "rgba(127, 135, 148, 0.7)"
            if self.is_dark_theme()
            else "rgba(120, 130, 146, 0.55)"
        )
        return (
            "QScrollArea { background:transparent; border:none; }"
            "QScrollBar:vertical {"
            "background:transparent;"
            "width:8px;"
            "margin:4px 1px 4px 1px;"
            "border:none;"
            "}"
            "QScrollBar::handle:vertical {"
            f"background:{handle};"
            "border-radius:4px;"
            "min-height:28px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            f"background:{handle_hover};"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "height:0px;"
            "background:transparent;"
            "border:none;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "background:transparent;"
            "}"
        )

    def apply_section_panel_style(self, frame: QFrame) -> None:
        colors = self.theme_colors()
        frame.setStyleSheet(
            f"QFrame {{ background:{colors['panel_bg']}; border:1px solid {colors['panel_border']}; border-radius:10px; }}"
        )
        title_label = getattr(frame, "section_title_label", None)
        if title_label is not None:
            title_label.setStyleSheet(
                f"font-size:14px; font-weight:700; color:{colors['text_primary']}; background:transparent; border:none;"
            )
        title_widget = getattr(frame, "section_title_widget", None)
        if isinstance(title_widget, QPushButton):
            if title_widget.property("icon_header_button"):
                return
            title_widget.setStyleSheet(
                "QPushButton {"
                "background:transparent;"
                "border:none;"
                "padding:0;"
                f"color:{colors['text_primary']};"
                "font-size:14px;"
                "font-weight:700;"
                "text-align:left;"
                "}"
                f"QPushButton:hover {{ color:{colors['text_secondary']}; }}"
            )

    def apply_theme(self) -> None:
        colors = self.theme_colors()
        if hasattr(self, "root_widget"):
            self.root_widget.setStyleSheet(
                f"QWidget#appRoot {{ background:{colors['app_bg']}; border:none; }}"
            )
        self.experimental_page.setStyleSheet("background:transparent; border:none;")
        self.experimental_footer_widget.setStyleSheet(
            f"background:transparent; border:none; border-top:1px solid {colors['panel_border']};"
        )
        self.playlists_panel.setStyleSheet("background:transparent; border:none;")
        self.tracks_panel.setStyleSheet("background:transparent; border:none;")
        for section in [
            self.footer_left_section,
            self.footer_center_section,
            self.footer_right_section,
        ]:
            section.setStyleSheet("background:transparent; border:none;")
        self.scroll_area.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }"
        )
        self.cards_container.setStyleSheet("background:transparent; border:none;")
        self.playlist_tracks_scroll.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }"
            "QScrollBar:vertical {"
            "background:transparent;"
            "width:10px;"
            "margin:4px 2px 4px 2px;"
            "border:none;"
            "}"
            "QScrollBar::handle:vertical {"
            f"background:{'rgba(127, 135, 148, 0.45)' if self.is_dark_theme() else 'rgba(120, 130, 146, 0.35)'};"
            "border-radius:5px;"
            "min-height:28px;"
            "}"
            "QScrollBar::handle:vertical:hover {"
            f"background:{'rgba(127, 135, 148, 0.7)' if self.is_dark_theme() else 'rgba(120, 130, 146, 0.55)'};"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "height:0px;"
            "background:transparent;"
            "border:none;"
            "}"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            "background:transparent;"
            "}"
        )
        self.playlist_tracks_container.setStyleSheet(
            "background:transparent; border:none;"
        )
        for button in [
            self.select_elenveil_root_button,
            self.open_music_folder_button,
            self.import_button,
            self.new_track_button,
            self.home_button,
        ]:
            self.apply_icon_button_style(button)
        self.apply_toolbar_icon_button_style(self.start_button)
        self.apply_header_button_style(self.create_playlist_button)
        self.apply_header_button_style(self.track_search_filter_button)
        self.apply_icon_button_style(self.settings_button)
        self.apply_header_button_style(self.downloads_button)
        self.library_view_button.setStyleSheet(
            "QPushButton {"
            "background:#d97a2b;"
            "border:1px solid #c86b1f;"
            "border-radius:10px;"
            "padding:0;"
            "}"
            "QPushButton:hover { background:#e18738; }"
            "QPushButton:pressed { background:#c96d22; }"
            "QPushButton:disabled { background:#8b5b35; border-color:#8b5b35; }"
            "QPushButton::menu-indicator { image:none; width:0px; }"
        )
        self.library_back_button.setStyleSheet(
            "QToolButton {"
            "background:transparent;"
            "border:none;"
            "padding:0;"
            "}"
            "QToolButton:hover { background:transparent; }"
            "QToolButton:disabled { background:transparent; border:none; }"
        )
        if self.library_view_button.menu() is not None:
            self.library_view_button.menu().setStyleSheet(
                "QMenu {"
                f"background:{colors['panel_bg']};"
                f"border:1px solid {colors['panel_border']};"
                "border-radius:10px;"
                f"color:{colors['text_primary']};"
                "font-size:14px;"
                "padding:8px;"
                "}"
                "QMenu::item {"
                "padding:8px 14px 8px 28px;"
                "border-radius:8px;"
                "margin:2px 0;"
                "}"
                f"QMenu::item:selected {{ background:{colors['button_hover']}; }}"
                "QMenu::icon {"
                "padding-left:2px;"
                "}"
            )
        if self.create_playlist_button.menu() is not None:
            self.create_playlist_button.menu().setStyleSheet(
                "QMenu {"
                f"background:{colors['panel_bg']};"
                f"border:1px solid {colors['panel_border']};"
                "border-radius:10px;"
                f"color:{colors['text_primary']};"
                "font-size:14px;"
                "padding:8px;"
                "}"
                "QMenu::item {"
                "padding:8px 14px 8px 12px;"
                "border-radius:8px;"
                "margin:2px 0;"
                "}"
                f"QMenu::item:selected {{ background:{colors['button_hover']}; }}"
            )
        if self.track_search_filter_button.menu() is not None:
            self.track_search_filter_button.menu().setStyleSheet(
                "QMenu {"
                f"background:{colors['panel_bg']};"
                f"border:1px solid {colors['panel_border']};"
                "border-radius:10px;"
                f"color:{colors['text_primary']};"
                "font-size:14px;"
                "padding:8px;"
                "}"
                "QMenu::item {"
                "padding:8px 14px 8px 24px;"
                "border-radius:8px;"
                "margin:2px 0;"
                "}"
                f"QMenu::item:selected {{ background:{colors['button_hover']}; }}"
                "QMenu::icon {"
                "padding-left:2px;"
                "}"
            )
        for button in [self.sort_date_button, self.sort_title_button]:
            self.apply_toolbar_icon_button_style(button)
        self.track_search_edit.setStyleSheet(
            "QLineEdit {"
            f"background:{colors['list_bg']};"
            f"border:1px solid {colors['panel_border']};"
            "border-radius:8px;"
            f"color:{colors['text_primary']};"
            "padding:0 34px 0 10px;"
            "font-size:12px;"
            "}"
        )
        self.track_search_icon_label.setStyleSheet(
            f"background:transparent; border:none; color:{colors['text_muted']};"
        )
        for button in [
            self.metadata_cancel_button,
            self.metadata_save_button,
            self.metadata_album_cancel_button,
            self.metadata_album_save_button,
            self.metadata_track_cancel_button,
            self.metadata_track_save_button,
            self.metadata_album_title_clear_button,
            self.metadata_album_author_clear_button,
            self.metadata_author_clear_button,
            self.metadata_group_clear_button,
            self.metadata_album_clear_button,
        ]:
            self.apply_icon_button_style(button)
        for button in [
            self.metadata_track_location_button,
        ]:
            self.apply_header_button_style(button)
        if "проверка" in self.ffmpeg_status_label.text().casefold():
            self.ffmpeg_status_label.setStyleSheet(
                f"color:{colors['footer_text']}; font-size:12px;"
            )
        self.delete_files_checkbox.setStyleSheet(
            "QCheckBox {"
            f"color:{colors['text_secondary']};"
            "font-size:12px; spacing:6px; background:transparent; }"
            "QCheckBox::indicator { width:14px; height:14px; }"
            "QCheckBox::indicator:unchecked {"
            f"border:1px solid {colors['checkbox_border']};"
            f"background:{colors['checkbox_bg']};"
            "border-radius:3px; }"
            "QCheckBox::indicator:checked {"
            f"border:1px solid {colors['checkbox_checked']};"
            f"background:{colors['checkbox_checked']};"
            "border-radius:3px; }"
        )
        self.playlist_list.setStyleSheet(
            "QListWidget {"
            f"background:{colors['list_bg']};"
            "border:none; padding:6px; }"
            "QListWidget::item { padding:0; margin:0 0 10px 0; border:none; }"
            "QListWidget::item:selected { background:transparent; }"
        )
        self.playlist_tracks_empty.setStyleSheet(
            f"font-size:14px; color:{colors['text_muted']}; padding:24px; background:transparent; border:none;"
        )
        self.author_context_row.setStyleSheet("background:transparent; border:none;")
        self.author_context_label.setStyleSheet(
            f"font-size:12px; color:{colors['text_secondary']}; font-weight:700; background:transparent; border:none; padding:0 4px 2px 4px;"
        )
        for frame in [
            self.playlists_controls_panel,
            self.playlist_list_panel,
            self.metadata_panel,
        ]:
            self.apply_section_panel_style(frame)
        for frame in [self.tracks_search_panel, self.tracks_list_panel]:
            frame.setStyleSheet(
                f"QFrame {{ background:{colors['panel_bg']}; border:1px solid {colors['panel_border']}; border-radius:10px; }}"
            )
        self.tracks_toolbar_strip.setStyleSheet(
            f"background:{colors['app_bg']}; border:none;"
        )
        for frame in [self.metadata_album_section, self.metadata_track_section]:
            frame.setStyleSheet(
                f"#metadata_subsection {{ background:{colors['panel_bg']}; border:1px solid {colors['panel_border']}; border-radius:10px; }}"
            )
        self.metadata_cover_label.set_theme_colors(
            is_dark=self.is_dark_theme(),
            background=colors["list_bg"],
            border=colors["panel_border"],
            text=colors["text_muted"],
        )
        for label in [
            self.metadata_album_header,
            self.metadata_title_label,
            self.metadata_source_label,
            self.metadata_album_title_label,
            self.metadata_album_author_label,
            self.metadata_track_header,
            self.metadata_track_title_label,
            self.metadata_track_number_label,
            self.metadata_track_location_label,
            self.metadata_author_label,
            self.metadata_group_label,
            self.metadata_album_label,
        ]:
            label.setStyleSheet(
                f"font-size:12px; color:{colors['text_muted']}; font-weight:700; background:transparent; border:none;"
            )
        for label in [self.metadata_source_value]:
            label.setStyleSheet(
                f"font-size:13px; color:{colors['text_primary']}; background:transparent; border:none;"
            )
        for line_edit in [
            self.metadata_album_title_edit,
            self.metadata_album_author_edit,
            self.metadata_track_title_edit,
            self.metadata_track_number_edit,
            self.metadata_title_edit,
            self.metadata_author_edit,
            self.metadata_group_edit,
            self.metadata_album_edit,
        ]:
            line_edit.setStyleSheet(
                "QLineEdit {"
                f"background:{colors['list_bg']};"
                f"border:1px solid {colors['panel_border']};"
                "border-radius:8px;"
                f"color:{colors['text_primary']};"
                "padding:6px 8px;"
                "}"
            )
        for widget in [
            self.metadata_album_title_row,
            self.metadata_album_author_row,
            self.metadata_author_row,
            self.metadata_group_row,
            self.metadata_album_row,
        ]:
            widget.setStyleSheet("background:transparent; border:none;")
        self.metadata_album_separator.setStyleSheet(
            f"background:{colors['panel_border']}; border:none; max-height:1px;"
        )
        for widget in self.playlist_item_widgets:
            widget.apply_theme(self.is_dark_theme())
        for card in self.remote_track_cards:
            card.apply_theme(self.is_dark_theme())
        for card in self.cards:
            card.apply_theme(self.is_dark_theme())
        self.add_card.apply_theme(self.is_dark_theme())
        if self.has_active_track_search() and self.track_search_scope in {
            "albums",
            "authors",
            "playlists",
        }:
            self.render_track_search_results()
        elif self.experimental_source_mode == "home":
            self.render_home_page()
        elif self.experimental_source_mode == "author_albums":
            self.render_author_album_cards(self.selected_author_name or "")
        self.refresh_open_downloads_popup()
        self.position_track_search_icon()
        self.refresh_metadata_panel_cover_preview()

    def update_sort_button_labels(self) -> None:
        date_arrow = "↑" if self.sort_field == "date" and self.sort_ascending else "↓"
        title_arrow = "↑" if self.sort_field == "title" and self.sort_ascending else "↓"
        self.sort_date_button.setText(date_arrow)
        self.sort_title_button.setText(title_arrow)
        self.sort_date_button.setToolTip("Сортировка по номеру")
        self.sort_title_button.setToolTip("Сортировка по названию")
        self.sort_date_button.setChecked(self.sort_field == "date")
        self.sort_title_button.setChecked(self.sort_field == "title")

    def on_sort_requested(self, field: str) -> None:
        if self.sort_field == field:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_field = field
            self.sort_ascending = field == "title"
        self.update_sort_button_labels()
        if self.experimental_source_mode in {
            "all_music",
            "playlist",
            "author_collection",
            "album",
            "search_album_tracks",
        }:
            self.render_experimental_tracks(self.get_current_experimental_tracks())
            self.update_metadata_panel()

    def get_sorted_experimental_tracks(
        self,
        tracks: list[RemoteTrack] | list[LocalMusicTrack],
    ) -> list[RemoteTrack] | list[LocalMusicTrack]:
        if self.sort_field == "date" and self.experimental_source_mode == "playlist":
            return list(tracks) if self.sort_ascending else list(reversed(tracks))

        if self.sort_field == "date" and self.experimental_source_mode in {
            "author_collection",
            "album",
            "search_album_tracks",
        }:
            local_tracks = [
                track for track in tracks if isinstance(track, LocalMusicTrack)
            ]
            if local_tracks and any(track.track_number > 0 for track in local_tracks):
                indexed_tracks = list(enumerate(tracks))
                sorted_items = sorted(
                    indexed_tracks,
                    key=lambda item: (
                        item[1].track_number
                        if isinstance(item[1], LocalMusicTrack)
                        else 0,
                        item[0],
                    ),
                    reverse=not self.sort_ascending,
                )
                return [track for _, track in sorted_items]

        indexed_tracks = list(enumerate(tracks))

        def sort_key(item: tuple[int, RemoteTrack | LocalMusicTrack]) -> tuple:
            index, track = item
            if self.sort_field == "title":
                return (track.title.casefold(), index)
            added_at = getattr(track, "added_at", 0.0)
            return (added_at, index)

        sorted_items = sorted(
            indexed_tracks, key=sort_key, reverse=not self.sort_ascending
        )
        return [track for _, track in sorted_items]

    def get_track_status_title(
        self, track: RemoteTrack | LocalMusicTrack | None
    ) -> str:
        if track is None:
            return "—"
        if isinstance(track, LocalMusicTrack):
            if track.status == STATUS_DONE:
                return "Файл найден"
            if track.status == STATUS_ERROR or track.error:
                return track.error or "Файл отсутствует"
            return "Файл отсутствует"
        status_titles = {
            STATUS_META_LOADING: "Подгрузка метаданных",
            STATUS_PENDING: "Ожидает загрузки",
            STATUS_DOWNLOADING: "Загружается",
            STATUS_DONE: "Загружен",
            STATUS_ERROR: f"Ошибка: {track.error}"
            if getattr(track, "error", "")
            else "Ошибка загрузки",
            STATUS_SKIPPED: (
                f"Пропущен: {track.error}"
                if getattr(track, "error", "")
                else "Пропущен"
            ),
        }
        return status_titles.get(
            getattr(track, "status", STATUS_PENDING), "Ожидает загрузки"
        )

    def refresh_experimental_source_view(self) -> None:
        if (
            self.experimental_source_mode == "home"
            and not self.has_active_track_search()
        ):
            self.render_home_page()
            self.update_metadata_panel()
            self.update_tracks_toolbar_visibility()
            return
        if self.has_active_track_search() and self.track_search_scope == "tracks":
            tracks = self.get_current_experimental_tracks()
            if tracks and (
                self.selected_experimental_track_index is None
                or self.selected_experimental_track_index >= len(tracks)
            ):
                self.selected_experimental_track_index = 0
            self.render_experimental_tracks(tracks)
            self.update_metadata_panel()
            self.update_tracks_toolbar_visibility()
            return
        if self.has_active_track_search() and self.track_search_scope in {
            "albums",
            "authors",
            "playlists",
        }:
            self.render_track_search_results()
            self.update_metadata_panel()
            self.update_tracks_toolbar_visibility()
            return
        if (
            self.experimental_source_mode == "author_albums"
            and self.selected_author_name
        ):
            self.render_author_album_cards(self.selected_author_name)
            self.update_metadata_panel()
            self.update_tracks_toolbar_visibility()
            return
        if self.experimental_source_mode == "all_music":
            tracks = self.get_current_experimental_tracks()
            if tracks and (
                self.selected_experimental_track_index is None
                or self.selected_experimental_track_index >= len(tracks)
            ):
                self.selected_experimental_track_index = 0
            self.render_experimental_tracks(tracks)
            self.update_metadata_panel()
            return
        if self.experimental_source_mode == "author_collection":
            self.render_experimental_tracks(self.get_current_experimental_tracks())
            self.update_metadata_panel()
            return
        if self.experimental_source_mode == "author_albums":
            self.render_author_album_cards(self.selected_author_name or "")
            self.update_metadata_panel()
            self.update_tracks_toolbar_visibility()
            return
        if self.experimental_source_mode == "album":
            self.render_experimental_tracks(self.get_current_experimental_tracks())
            self.update_metadata_panel()
            return
        if self.experimental_source_mode == "search_album_tracks":
            self.render_experimental_tracks(self.get_current_experimental_tracks())
            self.update_metadata_panel()
            return
        if (
            self.experimental_source_mode == "playlist"
            and self.selected_playlist_index is not None
        ):
            tracks = self.get_current_experimental_tracks()
            if tracks and (
                self.selected_experimental_track_index is None
                or self.selected_experimental_track_index >= len(tracks)
            ):
                self.selected_experimental_track_index = 0
            self.render_experimental_tracks(tracks)
            self.update_metadata_panel()

    def refresh_visible_remote_track_card(
        self, playlist_index: int, track: RemoteTrack
    ) -> None:
        if (
            self.experimental_source_mode != "playlist"
            or self.selected_playlist_index != playlist_index
            or not self.remote_track_cards
        ):
            return
        sorted_tracks = self.get_current_experimental_tracks()
        try:
            visible_index = sorted_tracks.index(track)
        except ValueError:
            return
        if 0 <= visible_index < len(self.remote_track_cards):
            self.remote_track_cards[visible_index].update_from_track(
                track,
                self.get_track_display_number(track, visible_index),
            )

    def convert_downloaded_youtube_playlist_to_manual(
        self, playlist_index: int
    ) -> bool:
        if not (0 <= playlist_index < len(self.playlists)):
            return False
        playlist = self.playlists[playlist_index]
        if playlist.source != "youtube" or not playlist.tracks:
            return False
        if any(
            not self.is_playlist_track_downloaded(track) for track in playlist.tracks
        ):
            return False

        m3u8_path = export_playlist_m3u8(
            self.playlists_dir,
            self.music_library_dir,
            playlist.name,
            [
                track.local_file_path
                for track in playlist.tracks
                if track.local_file_path
            ],
        )
        delete_playlist(playlist, self.playlists_dir)
        self.playlists[playlist_index] = load_manual_playlist(
            m3u8_path, self.music_library_dir
        )
        return True

    def update_delete_files_checkbox_visibility(self) -> None:
        self.update_tracks_toolbar_visibility()

    def update_start_button_state(self) -> None:
        enabled = False
        if (
            self.youtube_download_thread is None
            and self.youtube_thread is None
            and self.experimental_source_mode == "playlist"
            and self.selected_playlist_index is not None
            and 0 <= self.selected_playlist_index < len(self.playlists)
        ):
            playlist = self.playlists[self.selected_playlist_index]
            enabled = (
                playlist.source == "youtube"
                and not playlist.is_loading
                and any(
                    track.status in (STATUS_PENDING, STATUS_ERROR, STATUS_SKIPPED)
                    for track in playlist.tracks
                )
            )
        self.start_button.setEnabled(enabled)
        self.update_tracks_toolbar_visibility()

    def refresh_local_music_tracks(self) -> None:
        self.ensure_elenveil_directories()
        self.local_music_tracks = scan_music_directory(self.music_library_dir)
        playlist_count_before_sync = len(self.playlists)
        self.sync_remote_playlists_with_library()
        self.deduplicate_playlists()
        if hasattr(self, "playlist_list"):
            if self.library_view_mode in {"authors", "albums"}:
                self.rebuild_playlist_list()
            elif self.library_view_mode == "playlists":
                if playlist_count_before_sync != len(self.playlists):
                    self.rebuild_playlist_list()
                self.refresh_playlist_item_statuses()

    def normalize_track_text(self, value: str) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    def remote_track_matches_local(
        self, remote_track: RemoteTrack, local_track: LocalMusicTrack
    ) -> bool:
        if self.normalize_track_text(remote_track.title) != self.normalize_track_text(
            local_track.title
        ):
            return False
        if self.normalize_track_text(remote_track.artists) != self.normalize_track_text(
            local_track.artists
        ):
            return False

        remote_album = self.normalize_track_text(remote_track.album)
        local_album = self.normalize_track_text(local_track.album)
        if remote_album and local_album and remote_album != local_album:
            return False
        return True

    def sync_remote_playlist_with_library(
        self, playlist: PlaylistEntry, persist: bool = True
    ) -> bool:
        if playlist.source != "youtube":
            return False

        local_tracks_by_title: dict[str, list[LocalMusicTrack]] = {}
        local_tracks_by_path: dict[str, LocalMusicTrack] = {}
        for local_track in self.local_music_tracks:
            local_tracks_by_path[os.path.abspath(local_track.file_path)] = local_track
            title_key = self.normalize_track_text(local_track.title)
            if not title_key:
                continue
            local_tracks_by_title.setdefault(title_key, []).append(local_track)

        changed = False
        for track in playlist.tracks:
            matched_track = self.find_downloaded_playlist_track(
                track,
                local_tracks_by_path,
                local_tracks_by_title,
            )
            if matched_track is not None:
                if (
                    track.status != STATUS_DONE
                    or track.local_file_path != matched_track.file_path
                    or track.progress != 100.0
                    or track.error
                ):
                    track.status = STATUS_DONE
                    track.local_file_path = matched_track.file_path
                    track.progress = 100.0
                    track.error = ""
                    changed = True
                continue

            if track.status == STATUS_DONE and (
                not track.local_file_path or not os.path.exists(track.local_file_path)
            ):
                track.status = STATUS_PENDING
                track.local_file_path = ""
                track.progress = 0.0
                track.error = ""
                changed = True

        if changed and persist:
            playlist_index = (
                self.playlists.index(playlist) if playlist in self.playlists else -1
            )
            if playlist_index >= 0:
                self.persist_playlist(playlist_index)

        playlist_m3u8_path = os.path.join(
            self.playlists_dir, f"{sanitize_playlist_filename(playlist.name)}.m3u8"
        )
        if any(track.status == STATUS_DONE for track in playlist.tracks) and (
            changed or not os.path.exists(playlist_m3u8_path)
        ):
            try:
                self.export_remote_playlist_m3u8(playlist)
            except Exception:
                pass
        return changed

    def find_downloaded_playlist_track(
        self,
        track: RemoteTrack,
        local_tracks_by_path: dict[str, LocalMusicTrack],
        local_tracks_by_title: dict[str, list[LocalMusicTrack]],
    ) -> LocalMusicTrack | None:
        for raw_path in (
            getattr(track, "local_file_path", ""),
            getattr(track, "file_path", ""),
        ):
            raw_path_text = str(raw_path or "").strip()
            if not raw_path_text:
                continue
            normalized_path = os.path.abspath(raw_path_text)
            if normalized_path in local_tracks_by_path:
                return local_tracks_by_path[normalized_path]
            if os.path.exists(normalized_path):
                return load_music_track(normalized_path)

        title_key = self.normalize_track_text(track.title)
        if not title_key:
            return None
        candidates = local_tracks_by_title.get(title_key, [])
        if not candidates:
            return None

        metadata_match = next(
            (
                local_track
                for local_track in candidates
                if self.remote_track_matches_local(track, local_track)
            ),
            None,
        )
        if metadata_match is not None:
            return metadata_match

        artist_key = self.normalize_track_text(track.artists)
        album_key = self.normalize_track_text(track.album)
        partial_match = next(
            (
                local_track
                for local_track in candidates
                if (
                    artist_key
                    and artist_key == self.normalize_track_text(local_track.artists)
                )
                or (
                    album_key
                    and album_key == self.normalize_track_text(local_track.album)
                )
            ),
            None,
        )
        if partial_match is not None:
            return partial_match

        if len(candidates) == 1:
            return candidates[0]
        return None

    def sync_remote_playlists_with_library(self) -> None:
        converted_indexes: list[int] = []
        for index, playlist in enumerate(self.playlists):
            if playlist.source != "youtube":
                continue
            changed = self.sync_remote_playlist_with_library(playlist, persist=False)
            if self.is_playlist_complete(playlist):
                converted_indexes.append(index)
            elif changed:
                self.persist_playlist(index)
            if index < len(self.playlist_item_widgets):
                self.update_playlist_item_status(index)
        for index in reversed(converted_indexes):
            self.convert_downloaded_youtube_playlist_to_manual(index)

    def set_library_view_mode(self, mode: str) -> None:
        if mode not in {"playlists", "authors", "albums"}:
            return
        if mode != self.library_view_mode and (
            self.youtube_thread is not None or self.youtube_download_thread is not None
        ):
            QMessageBox.information(
                self,
                "Раздел библиотеки",
                "Смена раздела недоступна, пока выполняется работа с плейлистом YouTube.",
            )
            return
        self.library_view_mode = mode
        self.selected_author_name = None
        self.selected_album_name = None
        title_map = {
            "playlists": "Плейлисты",
            "authors": "Авторы",
            "albums": "Альбомы",
        }
        self.library_view_button.setToolTip(title_map[mode])
        self.library_view_button.setAccessibleName(title_map[mode])
        self.update_library_view_icon()
        self.refresh_local_music_tracks()
        self.rebuild_playlist_list()
        if mode == "playlists":
            self.experimental_source_mode = "none"
            self.selected_playlist_index = None
            self.current_collection_label = "Плейлисты"
            self.clear_experimental_track_selection()
            self.playlist_list.blockSignals(True)
            self.playlist_list.setCurrentRow(-1)
            self.playlist_list.blockSignals(False)
            self.restore_sidebar_selection()
            self.render_experimental_tracks([])
            self.update_metadata_panel()
            self.update_delete_files_checkbox_visibility()
            self.update_start_button_state()
            return
        self.playlist_list.blockSignals(True)
        self.playlist_list.setCurrentRow(-1)
        self.playlist_list.blockSignals(False)
        self.restore_sidebar_selection()
        self.experimental_source_mode = (
            "author_browser" if mode == "authors" else "album_browser"
        )
        self.current_collection_label = title_map[mode]
        self.clear_experimental_track_selection()
        self.render_experimental_tracks([])
        self.update_metadata_panel()
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()

    def on_library_back_requested(self) -> None:
        if (
            self.library_view_mode == "authors"
            and self.selected_author_name is not None
        ):
            self.selected_author_name = None
            self.selected_album_name = None
            self.rebuild_playlist_list()
            self.playlist_list.blockSignals(True)
            self.playlist_list.setCurrentRow(-1)
            self.playlist_list.blockSignals(False)
            self.experimental_source_mode = "author_browser"
            self.current_collection_label = "Авторы"
            self.clear_experimental_track_selection()
            self.render_experimental_tracks([])
            self.update_metadata_panel()
            self.update_delete_files_checkbox_visibility()
            self.update_start_button_state()

    def current_library_view_icon(self) -> QIcon:
        if self.library_view_mode == "authors":
            return self.library_author_icon
        if self.library_view_mode == "albums":
            return self.library_album_icon
        return self.library_playlist_icon

    def update_library_view_icon(self) -> None:
        if hasattr(self, "library_view_button"):
            self.library_view_button.setIcon(self.current_library_view_icon())
            self.library_view_button.setIconSize(QSize(24, 24))

    def release_author_sidebar_transition_guard(self) -> None:
        self.author_sidebar_transition_guard = False

    def grouped_tracks_by_author(self) -> dict[str, list[LocalMusicTrack]]:
        grouped: dict[str, list[LocalMusicTrack]] = {}
        for track in self.local_music_tracks:
            author = (
                track.artists or "Неизвестный автор"
            ).strip() or "Неизвестный автор"
            grouped.setdefault(author, []).append(track)
        return grouped

    def grouped_tracks_by_album(self) -> dict[str, list[LocalMusicTrack]]:
        grouped: dict[str, list[LocalMusicTrack]] = {}
        for track in self.local_music_tracks:
            album = track.album.strip()
            if not album:
                continue
            grouped.setdefault(album, []).append(track)
        return grouped

    def author_album_groups(
        self, author_name: str
    ) -> tuple[dict[str, list[LocalMusicTrack]], list[LocalMusicTrack]]:
        album_groups: dict[str, list[LocalMusicTrack]] = {}
        singles: list[LocalMusicTrack] = []
        for track in self.grouped_tracks_by_author().get(author_name, []):
            album = track.album.strip()
            if album:
                album_groups.setdefault(album, []).append(track)
            else:
                singles.append(track)
        return album_groups, singles

    def author_singles_for_display(self, author_name: str) -> list[LocalMusicTrack]:
        _, singles = self.author_album_groups(author_name)
        return sorted(
            singles,
            key=lambda track: (track.added_at, track.title.casefold()),
            reverse=True,
        )

    def relayout_status_widgets(self) -> None:
        self.clear_layout(self.experimental_footer_layout)
        self.experimental_footer_layout.addWidget(
            self.settings_button,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.experimental_footer_layout.addWidget(
            self.downloads_button,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.experimental_footer_layout.addStretch(1)
        self.experimental_footer_widget.setVisible(True)

    def sync_footer_sections(self) -> None:
        return

    def clear_layout(self, layout: QHBoxLayout | QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def open_elenveil_music_folder(self) -> None:
        self.ensure_elenveil_directories()
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.elenveil_root_dir))

    def open_project_github(self) -> None:
        QDesktopServices.openUrl(QUrl(self.PROJECT_GITHUB_URL))

    def show_settings_dialog(self) -> None:
        dialog = SettingsDialog(
            self,
            version_text=self.PROJECT_VERSION,
            active_folder_path=self.elenveil_root_dir,
            theme_mode=self.theme_mode,
            open_folder_icon=self.reveal_icon,
            choose_folder_icon=self.choose_folder_icon,
            youtube_cookies_browser=self.youtube_cookies_browser,
            youtube_cookies_file=self.youtube_cookies_file,
        )
        dialog.github_button.clicked.connect(self.open_project_github)
        dialog.open_folder_button.clicked.connect(self.open_elenveil_music_folder)

        def choose_folder() -> None:
            previous_path = self.elenveil_root_dir
            self.choose_elenveil_root_directory()
            if self.elenveil_root_dir != previous_path:
                dialog.set_active_folder_path(self.elenveil_root_dir)

        def update_theme() -> None:
            selected_mode = dialog.selected_theme_mode()
            if selected_mode == self.theme_mode:
                return
            self.apply_theme_mode(selected_mode)
            dialog.set_theme_mode(selected_mode)
            dialog.set_icons(self.reveal_icon, self.choose_folder_icon)
            dialog.apply_theme()

        dialog.choose_folder_button.clicked.connect(choose_folder)
        dialog.theme_combo.currentIndexChanged.connect(lambda _index: update_theme())
        dialog.exec()
        cookies_browser, cookies_file = dialog.youtube_auth_values()
        self.youtube_cookies_browser = cookies_browser
        self.youtube_cookies_file = cookies_file
        save_youtube_auth_settings(cookies_browser, cookies_file)

    def current_ytdlp_auth_options(self) -> dict:
        return build_ytdlp_auth_options(
            self.youtube_cookies_browser,
            self.youtube_cookies_file,
        )

    def show_downloads_menu(self) -> None:
        if self.downloads_popup is not None and self.downloads_popup.isVisible():
            self.downloads_popup.close()
            return

        popup = QDialog(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        popup.setObjectName("downloads_popup")
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        popup.setFixedWidth(380)
        layout = QVBoxLayout(popup)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("downloads_popup_frame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(10, 10, 10, 10)
        frame_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(self.vertical_scrollbar_style())

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        scroll.setWidget(content)
        frame_layout.addWidget(scroll)
        layout.addWidget(frame)

        self.downloads_popup = popup
        self.downloads_popup_frame = frame
        self.downloads_popup_layout = content_layout
        self.refresh_downloads_popup()

        popup.adjustSize()
        popup.setFixedHeight(min(max(popup.sizeHint().height(), 92), 420))
        button_top_left = self.downloads_button.mapToGlobal(
            self.downloads_button.rect().topLeft()
        )
        popup.move(button_top_left.x(), button_top_left.y() - popup.height() - 8)
        popup.finished.connect(lambda _result: self.clear_downloads_popup())
        popup.show()

    def clear_downloads_popup(self) -> None:
        self.download_queue_cards = []
        self.download_queue_card_keys = []
        self.downloads_popup = None
        self.downloads_popup_frame = None
        self.downloads_popup_layout = None

    def active_download_queue_items(self) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []

        pending_task_indexes = [
            index
            for index, task in enumerate(self.tasks)
            if task.status != STATUS_DONE
            and task.status
            in {
                STATUS_META_LOADING,
                STATUS_PENDING,
                STATUS_DOWNLOADING,
                STATUS_ERROR,
                STATUS_SKIPPED,
            }
        ]
        active_task_indexes = [
            index
            for index in pending_task_indexes
            if self.tasks[index].status == STATUS_DOWNLOADING
        ]
        ordered_task_indexes = [
            index for index in pending_task_indexes if index not in active_task_indexes
        ] + active_task_indexes
        for index in ordered_task_indexes:
            task = self.tasks[index]
            items.append(
                {
                    "key": f"task:{index}",
                    "title": task.meta_title or task.title,
                    "progress": task.progress,
                    "status": task.status,
                    "thumbnail_data": task.thumbnail_data,
                }
            )

        if (
            self.single_download_task is not None
            and self.single_download_task.status != STATUS_DONE
        ):
            task = self.single_download_task
            items.append(
                {
                    "key": "single",
                    "title": task.meta_title or task.title,
                    "progress": task.progress,
                    "status": task.status,
                    "thumbnail_data": task.thumbnail_data,
                }
            )

        if (
            self.active_remote_playlist_index is not None
            and 0 <= self.active_remote_playlist_index < len(self.playlists)
        ):
            playlist = self.playlists[self.active_remote_playlist_index]
            queued_indexes = [
                index
                for index in self.active_youtube_download_queue
                if 0 <= index < len(playlist.tracks)
                and playlist.tracks[index].status != STATUS_DONE
            ]
            active_indexes = [
                index
                for index in queued_indexes
                if playlist.tracks[index].status == STATUS_DOWNLOADING
            ]
            ordered_indexes = [
                index for index in queued_indexes if index not in active_indexes
            ] + active_indexes
            for index in ordered_indexes:
                track = playlist.tracks[index]
                items.append(
                    {
                        "key": f"remote:{self.active_remote_playlist_index}:{index}",
                        "title": track.title,
                        "progress": track.progress,
                        "status": track.status,
                        "thumbnail_data": track.thumbnail_data,
                    }
                )

        return items

    def refresh_downloads_popup(self) -> None:
        if self.downloads_popup_layout is None:
            return
        self.clear_layout(self.downloads_popup_layout)
        self.download_queue_cards = []
        self.download_queue_card_keys = []
        colors = self.theme_colors()
        if self.downloads_popup is not None:
            self.downloads_popup.setStyleSheet(
                "#downloads_popup { background:transparent; border:none; }"
                "QScrollArea, QScrollArea > QWidget > QWidget {"
                "background:transparent;"
                "border:none;"
                "}"
            )
        if self.downloads_popup_frame is not None:
            self.downloads_popup_frame.setStyleSheet(
                "#downloads_popup {"
                "background:transparent;"
                "border:none;"
                "}"
                "#downloads_popup_frame {"
                f"background:{colors['panel_bg']};"
                f"border:1px solid {colors['panel_border']};"
                "border-radius:12px;"
                "}"
            )

        items = self.active_download_queue_items()
        if not items:
            empty_label = QLabel("Активных загрузок нет")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet(
                f"font-size:13px; font-weight:700; color:{colors['text_muted']}; background:transparent; border:none;"
            )
            empty_label.setMinimumHeight(54)
            self.downloads_popup_layout.addWidget(empty_label)
            return

        for item in items:
            card = DownloadQueueCard(
                str(item.get("title") or "Без названия"),
                float(item.get("progress") or 0.0),
                str(item.get("status") or STATUS_PENDING),
                item.get("thumbnail_data"),
                self.status_icons,
            )
            card.apply_theme(self.is_dark_theme())
            self.download_queue_cards.append(card)
            self.download_queue_card_keys.append(str(item.get("key") or ""))
            self.downloads_popup_layout.addWidget(card)
        self.downloads_popup_layout.addStretch(1)

    def refresh_open_downloads_popup(self) -> None:
        if self.downloads_popup is None or not self.downloads_popup.isVisible():
            return
        items = self.active_download_queue_items()
        item_keys = [str(item.get("key") or "") for item in items]
        if (
            items
            and len(items) == len(self.download_queue_cards)
            and item_keys == self.download_queue_card_keys
        ):
            for card, item in zip(self.download_queue_cards, items):
                card.update_content(
                    str(item.get("title") or "Без названия"),
                    float(item.get("progress") or 0.0),
                    str(item.get("status") or STATUS_PENDING),
                    item.get("thumbnail_data"),
                )
            return
        self.refresh_downloads_popup()
        self.downloads_popup.adjustSize()
        self.downloads_popup.setFixedHeight(
            min(max(self.downloads_popup.sizeHint().height(), 92), 420)
        )

    def default_elenveil_root_dir(self) -> str:
        return os.path.join(os.path.expanduser("~"), "Music", "Elenveil")

    def initialize_elenveil_root_dir(
        self, preferred_root_dir: str, fallback_root_dir: str
    ) -> None:
        try:
            self.set_elenveil_root_dir(preferred_root_dir, persist=False)
            return
        except OSError:
            preferred_path = os.path.abspath(
                os.path.expanduser(preferred_root_dir.strip())
            )
            fallback_path = os.path.abspath(
                os.path.expanduser(fallback_root_dir.strip())
            )
            if preferred_path == fallback_path:
                raise

            self.set_elenveil_root_dir(fallback_root_dir, persist=True)
            self.startup_root_dir_warning = (
                f"Папка по пути\n{preferred_path}\n\n"
                "не была найдена, будет использован стандартный путь сохранения:\n\n"
                f"{fallback_path}"
            )

    def show_startup_root_dir_warning(self) -> None:
        if not self.startup_root_dir_warning:
            return
        QMessageBox.warning(
            self,
            "Папка Elenveil",
            self.startup_root_dir_warning,
        )
        self.startup_root_dir_warning = ""

    def update_elenveil_root_paths(self, root_dir: str) -> None:
        normalized_root_dir = os.path.abspath(os.path.expanduser(root_dir.strip()))
        self.elenveil_root_dir = normalized_root_dir
        self.music_library_dir = os.path.join(self.elenveil_root_dir, "music")
        self.playlists_dir = os.path.join(self.elenveil_root_dir, "playlists")

    def set_elenveil_root_dir(self, root_dir: str, persist: bool = True) -> None:
        self.update_elenveil_root_paths(root_dir)
        self.ensure_elenveil_directories()
        if persist:
            save_elenveil_root_dir(self.elenveil_root_dir)

    def choose_elenveil_root_directory(self) -> None:
        if any(
            worker is not None
            for worker in (
                self.metadata_thread,
                self.download_thread,
                self.youtube_thread,
                self.youtube_download_thread,
            )
        ):
            QMessageBox.information(
                self,
                "Папка Elenveil",
                "Смена папки недоступна, пока выполняются фоновые задачи.",
            )
            return
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку Elenveil",
            self.elenveil_root_dir or os.path.expanduser("~"),
        )
        if not selected_dir:
            return

        try:
            self.set_elenveil_root_dir(selected_dir)
        except OSError as error:
            QMessageBox.warning(
                self,
                "Папка Elenveil",
                f"Не удалось использовать выбранную папку:\n{error}",
            )
            return
        self.reload_library_sources_after_root_change()

    def ensure_elenveil_directories(self) -> None:
        os.makedirs(self.elenveil_root_dir, exist_ok=True)
        os.makedirs(self.music_library_dir, exist_ok=True)
        os.makedirs(self.playlists_dir, exist_ok=True)

    def reload_library_sources_after_root_change(self) -> None:
        self.playlists = []
        self.selected_playlist_index = None
        self.selected_experimental_track_index = None
        self.pending_playlist_index = None
        self.rebuild_playlist_list()
        self.refresh_local_music_tracks()
        self.restore_persisted_playlists()
        self.set_library_view_mode(self.library_view_mode)

    def restore_persisted_playlists(self) -> None:
        self.ensure_elenveil_directories()
        self.local_music_tracks = scan_music_directory(self.music_library_dir)
        persisted = load_playlists(self.playlists_dir)
        persisted = [playlist for playlist in persisted if playlist.source == "youtube"]
        persisted.extend(
            load_manual_playlists(self.playlists_dir, self.music_library_dir)
        )
        if not persisted:
            return
        self.playlists = list(persisted)
        self.sync_remote_playlists_with_library()
        self.deduplicate_playlists()
        self.rebuild_playlist_list()
        self.refresh_playlist_item_statuses()

    def deduplicate_playlists(self) -> None:
        unique_playlists: list[PlaylistEntry] = []
        seen_keys: set[tuple[str, str]] = set()
        for playlist in self.playlists:
            source = (playlist.source or "").strip().casefold()
            source_url = str(playlist.source_url or "").strip()
            if source == "manual" and source_url:
                key_value = os.path.abspath(source_url)
            else:
                key_value = source_url or playlist.name.strip().casefold()
            key = (source, key_value)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_playlists.append(playlist)
        self.playlists = unique_playlists

    def rebuild_playlist_list(self) -> None:
        self.playlist_list.blockSignals(True)
        self.playlist_item_widgets = []
        self.sidebar_items = []
        self.playlist_list.clear()
        self.author_context_label.setText("")
        self.author_context_label.setVisible(False)
        self.library_back_button.setVisible(False)
        if self.library_view_mode == "playlists":
            for playlist_index, playlist in enumerate(self.playlists):
                self.add_playlist_list_item(playlist, playlist_index)
        elif self.library_view_mode == "authors":
            available_authors = self.grouped_tracks_by_author()
            if (
                self.selected_author_name is not None
                and self.selected_author_name not in available_authors
            ):
                self.selected_author_name = None
            for author_name in sorted(available_authors, key=str.casefold):
                self.add_sidebar_list_item(
                    author_name,
                    {"kind": "author", "author": author_name},
                    show_delete=True,
                )
        else:
            available_albums = self.grouped_tracks_by_album()
            if (
                self.selected_album_name is not None
                and self.selected_album_name not in available_albums
            ):
                self.selected_album_name = None
            for album_name in sorted(available_albums, key=str.casefold):
                self.add_sidebar_list_item(
                    album_name,
                    {"kind": "album", "album": album_name},
                    show_delete=True,
                )
        self.playlist_list.blockSignals(False)

    def persist_playlist(self, playlist_index: int) -> None:
        if not (0 <= playlist_index < len(self.playlists)):
            return
        playlist = self.playlists[playlist_index]
        if playlist.source != "youtube" or playlist.is_loading:
            return
        save_playlist(playlist, self.playlists_dir)

    def export_remote_playlist_m3u8(self, playlist: PlaylistEntry) -> None:
        if playlist.source != "youtube":
            return
        track_paths: list[str] = []
        for track in playlist.tracks:
            track_path = str(getattr(track, "local_file_path", "") or "").strip()
            if track_path:
                track_paths.append(track_path)
        export_playlist_m3u8(
            self.playlists_dir,
            self.music_library_dir,
            playlist.name,
            track_paths,
        )

    def add_playlist_list_item(
        self, playlist: PlaylistEntry, playlist_index: int
    ) -> int:
        return self.add_sidebar_list_item(
            playlist.name,
            {"kind": "playlist", "playlist_index": playlist_index},
            show_status=True,
            show_delete=True,
            playlist=playlist,
        )

    def add_sidebar_list_item(
        self,
        title: str,
        payload: dict[str, object],
        *,
        show_status: bool = False,
        show_reveal: bool = True,
        show_delete: bool = False,
        playlist: PlaylistEntry | None = None,
    ) -> int:
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 54))
        self.playlist_list.addItem(item)
        widget = PlaylistListItemWidget(
            title,
            self.playlist_loading_icon,
            self.playlist_ready_icon,
            self.reveal_icon,
        )
        widget.apply_theme(self.is_dark_theme())
        widget.set_status_visible(show_status)
        widget.set_reveal_visible(show_reveal)
        widget.set_delete_visible(show_delete)
        if playlist is not None:
            widget.set_loading(playlist.is_loading or playlist.is_downloading)
        else:
            widget.set_loading(False)
        row = self.playlist_list.count() - 1
        widget.clicked.connect(lambda row=row: self.playlist_list.setCurrentRow(row))
        widget.reveal_requested.connect(
            lambda row=row: self.on_sidebar_reveal_requested(row)
        )
        if payload.get("kind") == "playlist":
            widget.context_requested.connect(
                lambda global_pos, row=row: self.on_playlist_context_requested(
                    row, global_pos
                )
            )
        widget.delete_requested.connect(
            lambda row=row: self.on_sidebar_delete_requested(row)
        )
        self.playlist_item_widgets.append(widget)
        self.sidebar_items.append(payload)
        self.playlist_list.setItemWidget(item, widget)
        if playlist is not None:
            self.update_playlist_item_status(row)
        return row

    def restore_sidebar_selection(self) -> None:
        target_row = -1
        if (
            self.library_view_mode == "playlists"
            and self.selected_playlist_index is not None
        ):
            for row, payload in enumerate(self.sidebar_items):
                if (
                    payload.get("kind") == "playlist"
                    and int(payload.get("playlist_index", -1))
                    == self.selected_playlist_index
                ):
                    target_row = row
                    break
        elif self.library_view_mode == "authors":
            if self.selected_author_name is not None:
                for row, payload in enumerate(self.sidebar_items):
                    if (
                        payload.get("kind") == "author"
                        and payload.get("author") == self.selected_author_name
                    ):
                        target_row = row
                        break
        elif self.library_view_mode == "albums" and self.selected_album_name:
            for row, payload in enumerate(self.sidebar_items):
                if (
                    payload.get("kind") == "album"
                    and payload.get("album") == self.selected_album_name
                ):
                    target_row = row
                    break
        self.playlist_list.blockSignals(True)
        self.playlist_list.setCurrentRow(target_row)
        self.playlist_list.blockSignals(False)
        for index, widget in enumerate(self.playlist_item_widgets):
            widget.set_selected(index == target_row)

    def get_playlist_ready_status_icon(self, playlist: PlaylistEntry) -> QIcon:
        if self.is_playlist_complete(playlist):
            return self.status_icons[STATUS_DONE]
        return self.playlist_ready_icon

    def is_playlist_complete(self, playlist: PlaylistEntry) -> bool:
        return bool(playlist.tracks) and all(
            self.is_playlist_track_downloaded(track) for track in playlist.tracks
        )

    def is_playlist_track_downloaded(
        self, track: RemoteTrack | LocalMusicTrack
    ) -> bool:
        if getattr(track, "status", STATUS_PENDING) == STATUS_DONE:
            local_file_path = str(getattr(track, "local_file_path", "") or "").strip()
            file_path = str(getattr(track, "file_path", "") or "").strip()
            if local_file_path:
                return os.path.exists(local_file_path)
            if file_path:
                return os.path.exists(file_path)
            return isinstance(track, LocalMusicTrack)
        local_file_path = str(getattr(track, "local_file_path", "") or "").strip()
        return bool(local_file_path and os.path.exists(local_file_path))

    def update_playlist_item_status(self, row: int) -> None:
        if row >= len(self.playlist_item_widgets) or row >= len(self.sidebar_items):
            return
        payload = self.sidebar_items[row]
        if payload.get("kind") != "playlist":
            return
        playlist_index = int(payload.get("playlist_index", -1))
        if not (0 <= playlist_index < len(self.playlists)):
            return
        playlist = self.playlists[playlist_index]
        widget = self.playlist_item_widgets[row]
        widget.set_ready_icon(self.get_playlist_ready_status_icon(playlist))
        is_complete = self.is_playlist_complete(playlist)
        widget.set_loading(
            (playlist.is_loading or playlist.is_downloading) and not is_complete
        )

    def refresh_playlist_item_statuses(self) -> None:
        for row, payload in enumerate(self.sidebar_items):
            if payload.get("kind") == "playlist":
                self.update_playlist_item_status(row)

    def on_playlist_delete_requested(self, row: int) -> None:
        if not (0 <= row < len(self.sidebar_items)):
            return
        payload = self.sidebar_items[row]
        if payload.get("kind") != "playlist":
            return
        playlist_index = int(payload.get("playlist_index", -1))
        self.delete_playlist_by_index(playlist_index, select_next=True)

    def delete_playlist_by_index(
        self,
        playlist_index: int,
        *,
        select_next: bool,
    ) -> bool:
        if not (0 <= playlist_index < len(self.playlists)):
            return False
        playlist = self.playlists[playlist_index]
        answer = QMessageBox.question(
            self,
            "Удаление плейлиста",
            f"Удалить плейлист '{playlist.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False

        if playlist.source == "manual":
            playlist_path = playlist.source_url.strip()
            if playlist_path and os.path.exists(playlist_path):
                os.remove(playlist_path)
        elif playlist.source == "youtube":
            delete_playlist(playlist, self.playlists_dir)

        self.playlists.pop(playlist_index)
        self.rebuild_playlist_list()
        if not select_next:
            if self.selected_playlist_index == playlist_index:
                self.selected_playlist_index = None
            elif (
                self.selected_playlist_index is not None
                and self.selected_playlist_index > playlist_index
            ):
                self.selected_playlist_index -= 1
            self.update_delete_files_checkbox_visibility()
            self.update_start_button_state()
            return True
        if not self.playlists:
            self.playlist_list.setCurrentRow(-1)
            self.selected_playlist_index = None
            self.selected_experimental_track_index = None
            self.experimental_source_mode = "none"
            self.render_experimental_tracks([])
            self.update_metadata_panel()
        else:
            new_row = min(playlist_index, len(self.playlists) - 1)
            self.playlist_list.setCurrentRow(new_row)
            self.on_playlist_selected(new_row)
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()
        return True

    def get_tracks_for_sidebar_payload(
        self, payload: dict[str, object]
    ) -> list[LocalMusicTrack]:
        item_kind = str(payload.get("kind") or "")
        if item_kind == "author":
            author_name = str(payload.get("author") or "").strip()
            return list(self.grouped_tracks_by_author().get(author_name, []))
        if item_kind == "author_album":
            author_name = str(payload.get("author") or "").strip()
            album_name = str(payload.get("album") or "").strip()
            album_groups, _ = self.author_album_groups(author_name)
            return list(album_groups.get(album_name, []))
        if item_kind == "author_singles":
            author_name = str(payload.get("author") or "").strip()
            _, singles = self.author_album_groups(author_name)
            return list(singles)
        if item_kind == "album":
            album_name = str(payload.get("album") or "").strip()
            return list(self.grouped_tracks_by_album().get(album_name, []))
        return []

    def get_folder_path_for_tracks(self, tracks: list[LocalMusicTrack]) -> str:
        existing_paths = [
            os.path.realpath(track.file_path)
            for track in tracks
            if track.file_path and os.path.exists(track.file_path)
        ]
        if not existing_paths:
            return ""
        common_path = os.path.commonpath(existing_paths)
        if os.path.isfile(common_path):
            return os.path.dirname(common_path)
        if common_path == os.path.realpath(self.music_library_dir):
            return os.path.dirname(existing_paths[0])
        return common_path

    def open_folder_in_file_manager(
        self, folder_path: str, title: str, missing_text: str
    ) -> None:
        normalized_path = os.path.abspath(str(folder_path or "").strip())
        if not normalized_path or not os.path.isdir(normalized_path):
            QMessageBox.information(self, title, missing_text)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(normalized_path))

    def on_sidebar_reveal_requested(self, row: int) -> None:
        if not (0 <= row < len(self.sidebar_items)):
            return
        payload = self.sidebar_items[row]
        item_kind = str(payload.get("kind") or "")
        if (
            self.author_sidebar_transition_guard
            and self.library_view_mode == "authors"
            and item_kind in {"author_album", "author_singles"}
        ):
            self.playlist_list.blockSignals(True)
            self.playlist_list.setCurrentRow(-1)
            self.playlist_list.clearSelection()
            self.playlist_list.blockSignals(False)
            for widget in self.playlist_item_widgets:
                widget.set_selected(False)
            return
        if item_kind == "playlist":
            playlist_index = int(payload.get("playlist_index", -1))
            if not (0 <= playlist_index < len(self.playlists)):
                return
            playlist = self.playlists[playlist_index]
            self.reveal_file_in_file_manager(
                self.get_playlist_reveal_path(playlist),
                "Открыть расположение",
                "Файл плейлиста не найден.",
            )
            return

        tracks = self.get_tracks_for_sidebar_payload(payload)
        self.open_folder_in_file_manager(
            self.get_folder_path_for_tracks(tracks),
            "Открыть расположение",
            "Папка с музыкой не найдена.",
        )

    def delete_sidebar_tracks_group(
        self,
        tracks: list[LocalMusicTrack],
        *,
        title: str,
        prompt: str,
    ) -> bool:
        existing_paths = [
            os.path.realpath(track.file_path)
            for track in tracks
            if track.file_path and os.path.exists(track.file_path)
        ]
        if not existing_paths:
            QMessageBox.information(self, title, "Файлы для удаления не найдены.")
            return False
        answer = QMessageBox.question(
            self,
            title,
            prompt,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        for file_path in existing_paths:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.cleanup_empty_music_directories(os.path.dirname(file_path))

        self.refresh_local_music_tracks()
        self.clear_experimental_track_selection()
        self.set_library_view_mode(self.library_view_mode)
        self.update_metadata_panel()
        self.update_start_button_state()
        return True

    def restore_middle_library_view_after_delete(self, was_home: bool) -> None:
        if was_home:
            self.show_home_page()
            return
        if self.has_active_track_search() and self.track_search_scope in {
            "albums",
            "authors",
            "playlists",
        }:
            self.render_track_search_results()
            self.update_metadata_panel()
            self.update_tracks_toolbar_visibility()

    def on_middle_playlist_delete_requested(self, playlist_index: int) -> None:
        was_home = self.experimental_source_mode == "home"
        if self.delete_playlist_by_index(playlist_index, select_next=False):
            self.restore_middle_library_view_after_delete(was_home)

    def on_middle_album_delete_requested(
        self,
        album_name: str,
        author_name: str,
    ) -> None:
        was_home = self.experimental_source_mode == "home"
        was_author_albums = self.experimental_source_mode == "author_albums"
        tracks = [
            track
            for track in self.local_music_tracks
            if track.album.strip() == album_name
            and track.artists.strip() == author_name
        ]
        if self.delete_sidebar_tracks_group(
            tracks,
            title="Удаление альбома",
            prompt=f"Удалить все треки альбома '{album_name}' из папки music?",
        ):
            if was_author_albums and author_name in self.grouped_tracks_by_author():
                self.selected_author_name = author_name
                self.experimental_source_mode = "author_albums"
                self.current_collection_label = author_name
                self.restore_sidebar_selection()
                self.render_author_album_cards(author_name)
                self.update_metadata_panel()
                self.update_tracks_toolbar_visibility()
            else:
                self.restore_middle_library_view_after_delete(was_home)

    def on_middle_author_singles_delete_requested(self, author_name: str) -> None:
        was_author_albums = self.experimental_source_mode == "author_albums"
        _, singles = self.author_album_groups(author_name)
        if self.delete_sidebar_tracks_group(
            list(singles),
            title="Удаление синглов",
            prompt=f"Удалить все синглы автора '{author_name}' из папки music?",
        ):
            if was_author_albums and author_name in self.grouped_tracks_by_author():
                self.selected_author_name = author_name
                self.experimental_source_mode = "author_albums"
                self.current_collection_label = author_name
                self.restore_sidebar_selection()
                self.render_author_album_cards(author_name)
                self.update_metadata_panel()
                self.update_tracks_toolbar_visibility()

    def on_middle_author_delete_requested(self, author_name: str) -> None:
        was_home = self.experimental_source_mode == "home"
        tracks = list(self.grouped_tracks_by_author().get(author_name, []))
        if self.delete_sidebar_tracks_group(
            tracks,
            title="Удаление автора",
            prompt=f"Удалить все треки автора '{author_name}' из папки music?",
        ):
            self.restore_middle_library_view_after_delete(was_home)

    def on_sidebar_delete_requested(self, row: int) -> None:
        if not (0 <= row < len(self.sidebar_items)):
            return
        payload = self.sidebar_items[row]
        item_kind = str(payload.get("kind") or "")
        if item_kind == "playlist":
            self.on_playlist_delete_requested(row)
            return
        if item_kind == "author":
            author_name = (
                str(payload.get("author") or "").strip() or "Неизвестный автор"
            )
            tracks = self.get_tracks_for_sidebar_payload(payload)
            self.delete_sidebar_tracks_group(
                tracks,
                title="Удаление автора",
                prompt=f"Удалить все треки автора '{author_name}' из папки music?",
            )
            return
        if item_kind == "author_album":
            album_name = str(payload.get("album") or "").strip() or "Без альбома"
            tracks = self.get_tracks_for_sidebar_payload(payload)
            self.delete_sidebar_tracks_group(
                tracks,
                title="Удаление альбома",
                prompt=f"Удалить все треки альбома '{album_name}' из папки music?",
            )
            return
        if item_kind == "author_singles":
            author_name = (
                str(payload.get("author") or "").strip() or "Неизвестный автор"
            )
            tracks = self.get_tracks_for_sidebar_payload(payload)
            self.delete_sidebar_tracks_group(
                tracks,
                title="Удаление синглов",
                prompt=f"Удалить все синглы автора '{author_name}' из папки music?",
            )
            return
        if item_kind == "album":
            album_name = str(payload.get("album") or "").strip() or "Без альбома"
            tracks = self.get_tracks_for_sidebar_payload(payload)
            self.delete_sidebar_tracks_group(
                tracks,
                title="Удаление альбома",
                prompt=f"Удалить все треки альбома '{album_name}' из папки music?",
            )

    def get_playlist_reveal_path(self, playlist: PlaylistEntry) -> str:
        if playlist.source == "manual":
            return playlist.source_url.strip()
        if playlist.source == "youtube":
            return os.path.join(self.playlists_dir, playlist_storage_name(playlist))
        return ""

    def reveal_file_in_file_manager(
        self, file_path: str, title: str, missing_text: str
    ) -> None:
        normalized_path = os.path.abspath(str(file_path or "").strip())
        if not normalized_path or not os.path.exists(normalized_path):
            QMessageBox.information(self, title, missing_text)
            return
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", normalized_path], check=False)
            return
        if os.name == "nt":
            subprocess.run(["explorer", f"/select,{normalized_path}"], check=False)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(normalized_path)))

    def rename_playlist(self, row: int) -> None:
        if not (0 <= row < len(self.playlists)):
            return
        playlist = self.playlists[row]
        current_name = playlist.name.strip()
        new_name, ok = QInputDialog.getText(
            self,
            "Переименовать плейлист",
            "Новое название:",
            text=current_name,
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == current_name:
            return

        if playlist.source == "manual":
            current_path = playlist.source_url.strip()
            target_path = os.path.join(
                self.playlists_dir, f"{sanitize_playlist_filename(new_name)}.m3u8"
            )
            if os.path.abspath(current_path) != os.path.abspath(
                target_path
            ) and os.path.exists(target_path):
                QMessageBox.warning(
                    self,
                    "Переименовать плейлист",
                    "Плейлист с таким именем уже существует.",
                )
                return
            if current_path and os.path.exists(current_path):
                os.replace(current_path, target_path)
            playlist.name = new_name
            playlist.source_url = target_path
            self.playlists[row] = load_manual_playlist(
                target_path, self.music_library_dir
            )
        else:
            old_export_path = os.path.join(
                self.playlists_dir, f"{sanitize_playlist_filename(current_name)}.m3u8"
            )
            new_export_path = os.path.join(
                self.playlists_dir, f"{sanitize_playlist_filename(new_name)}.m3u8"
            )
            if (
                os.path.abspath(old_export_path) != os.path.abspath(new_export_path)
                and os.path.exists(old_export_path)
                and not os.path.exists(new_export_path)
            ):
                os.replace(old_export_path, new_export_path)
            playlist.name = new_name
            self.persist_playlist(row)

        self.rebuild_playlist_list()
        self.playlist_list.setCurrentRow(row)
        self.on_playlist_selected(row)

    def convert_playlist_to_album(self, playlist_index: int) -> None:
        if not (0 <= playlist_index < len(self.playlists)):
            return
        playlist = self.playlists[playlist_index]
        if playlist.source != "manual":
            QMessageBox.information(
                self,
                "Конвертировать в Альбом",
                "Конвертация в альбом доступна только для локальных .m3u8 плейлистов.",
            )
            return
        if not playlist.tracks:
            QMessageBox.information(
                self,
                "Конвертировать в Альбом",
                "В плейлисте нет треков для конвертации.",
            )
            return

        missing_tracks = [
            track.file_path
            for track in playlist.tracks
            if not track.file_path or not os.path.exists(track.file_path)
        ]
        if missing_tracks:
            QMessageBox.warning(
                self,
                "Конвертировать в Альбом",
                "Не все файлы плейлиста найдены в папке music.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Конвертировать в Альбом",
            (
                f"Преобразовать плейлист '{playlist.name}' в альбом?\n\n"
                "У треков будет выставлен одинаковый альбом и порядок треков, "
                "после чего .m3u8 плейлист будет удалён."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            for track_number, track in enumerate(playlist.tracks, start=1):
                apply_mp3_metadata(
                    track.file_path,
                    title=track.title,
                    author=track.artists,
                    group="",
                    album=playlist.name,
                    cover_mode="keep",
                    cover_path="",
                    track_number=track_number,
                )
                self.relocate_music_file_after_metadata_edit(
                    track.file_path,
                    title=track.title,
                    author=track.artists,
                    album=playlist.name,
                )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Конвертировать в Альбом",
                f"Не удалось завершить конвертацию:\n{exc}",
            )
            return

        playlist_path = playlist.source_url.strip()
        if playlist_path and os.path.exists(playlist_path):
            os.remove(playlist_path)
        self.playlists.pop(playlist_index)
        self.refresh_local_music_tracks()
        self.set_library_view_mode("albums")
        for row, payload in enumerate(self.sidebar_items):
            if payload.get("kind") == "album" and payload.get("album") == playlist.name:
                self.playlist_list.setCurrentRow(row)
                break

    def on_playlist_context_requested(self, row: int, global_pos) -> None:
        if not (0 <= row < len(self.sidebar_items)):
            return
        payload = self.sidebar_items[row]
        if payload.get("kind") != "playlist":
            return
        self.playlist_list.setCurrentRow(row)
        playlist_index = int(payload.get("playlist_index", -1))
        if not (0 <= playlist_index < len(self.playlists)):
            return
        playlist = self.playlists[playlist_index]
        menu = QMenu(self)
        rename_action = menu.addAction("Переименовать")
        convert_action = None
        if playlist.source == "manual" and playlist.tracks:
            convert_action = menu.addAction("Конвертировать в Альбом")
        reveal_action = menu.addAction("Открыть расположение")
        reveal_action.setEnabled(bool(self.get_playlist_reveal_path(playlist)))
        delete_action = menu.addAction("Удалить")

        selected_action = menu.exec(global_pos)
        if selected_action == rename_action:
            self.rename_playlist(playlist_index)
            return
        if convert_action is not None and selected_action == convert_action:
            self.convert_playlist_to_album(playlist_index)
            return
        if selected_action == reveal_action:
            self.reveal_file_in_file_manager(
                self.get_playlist_reveal_path(playlist),
                "Открыть расположение",
                "Файл плейлиста не найден.",
            )
            return
        if selected_action == delete_action:
            self.on_playlist_delete_requested(row)

    def add_playlist(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить плейлист")
        self.style_simple_dialog(dialog)
        root = QVBoxLayout(dialog)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        colors = self.dialog_theme_colors()

        title = QLabel("Выберите источник плейлиста")
        title.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{colors['text_primary']}; background:transparent;"
        )
        root.addWidget(title)

        buttons_row = QHBoxLayout()

        def create_source_button(icon: QIcon, tooltip: str) -> QPushButton:
            button = QPushButton()
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.setFixedSize(52, 52)
            button.setStyleSheet(
                "QPushButton {"
                f"background:{colors['panel_bg']};"
                f"border:1px solid {colors['panel_border']};"
                "border-radius:10px; }"
                f"QPushButton:hover {{ background:{colors['panel_hover']}; }}"
                f"QPushButton:pressed {{ background:{colors['panel_hover']}; }}"
            )
            button.setIcon(icon)
            button.setIconSize(QSize(24, 24))
            return button

        manual_button = create_source_button(self.add_playlist_icon, "Ручной")
        youtube_button = create_source_button(
            QIcon(resource_path("assets", "icons", "youtube.svg")),
            "Youtube",
        )
        buttons_row.addWidget(manual_button)
        buttons_row.addWidget(youtube_button)
        root.addLayout(buttons_row)

        cancel_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel_box.rejected.connect(dialog.reject)
        root.addWidget(cancel_box)

        selection = {"value": ""}

        def choose(option: str) -> None:
            selection["value"] = option
            dialog.accept()

        manual_button.clicked.connect(lambda: choose("manual"))
        youtube_button.clicked.connect(lambda: choose("youtube"))

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if selection["value"] == "manual":
            self.add_manual_playlist()
            return
        if selection["value"] == "youtube":
            self.add_youtube_playlist()
            return

    def add_manual_playlist(self) -> None:
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Ручной плейлист")
        dialog.setLabelText("Введите название плейлиста:")
        dialog.setTextEchoMode(QLineEdit.EchoMode.Normal)
        self.style_input_dialog(dialog)
        dialog.resize(520, dialog.sizeHint().height())
        ok = dialog.exec()
        playlist_name = dialog.textValue().strip()
        if not ok or not playlist_name:
            return

        existing_index = next(
            (
                index
                for index, playlist in enumerate(self.playlists)
                if playlist.source == "manual"
                and playlist.name.casefold() == playlist_name.casefold()
            ),
            None,
        )
        if existing_index is not None:
            self.playlist_list.setCurrentRow(existing_index)
            self.on_playlist_selected(existing_index)
            QMessageBox.information(
                self, "Плейлист", "Плейлист с таким названием уже существует."
            )
            return

        try:
            playlist = create_manual_playlist(self.playlists_dir, playlist_name)
        except FileExistsError as exc:
            QMessageBox.warning(self, "Плейлист", str(exc))
            return
        except ValueError as exc:
            QMessageBox.warning(self, "Плейлист", str(exc))
            return

        self.playlists.append(playlist)
        if self.library_view_mode != "playlists":
            self.set_library_view_mode("playlists")
        else:
            self.rebuild_playlist_list()
        row = next(
            (
                index
                for index, payload in enumerate(self.sidebar_items)
                if payload.get("kind") == "playlist"
                and int(payload.get("playlist_index", -1)) == len(self.playlists) - 1
            ),
            -1,
        )
        self.playlist_list.setCurrentRow(row)
        self.on_playlist_selected(row)

    def add_youtube_playlist(self) -> None:
        if self.youtube_thread is not None:
            QMessageBox.information(
                self,
                "YouTube",
                "Подождите завершения текущего импорта плейлиста.",
            )
            return

        dialog = QInputDialog(self)
        dialog.setWindowTitle("YouTube плейлист")
        dialog.setLabelText("Вставьте ссылку на YouTube плейлист:")
        dialog.setTextEchoMode(QLineEdit.EchoMode.Normal)
        self.style_input_dialog(dialog)
        dialog.resize(760, dialog.sizeHint().height())
        dialog.setMinimumWidth(760)
        ok = dialog.exec()
        playlist_url = dialog.textValue().strip()
        if not ok or not playlist_url:
            return

        existing_index = next(
            (
                index
                for index, playlist in enumerate(self.playlists)
                if playlist.source == "youtube"
                and playlist.source_url.strip() == playlist_url
            ),
            None,
        )
        if existing_index is not None:
            self.playlist_list.setCurrentRow(existing_index)
            self.on_playlist_selected(existing_index)
            QMessageBox.information(
                self,
                "YouTube",
                "Этот плейлист уже импортирован и восстановлен из локального кэша.",
            )
            return

        self.create_playlist_button.setEnabled(False)
        if self.library_view_mode != "playlists":
            self.set_library_view_mode("playlists")
        self.pending_playlist_index = self.add_loading_playlist_entry(
            playlist_url,
            "youtube",
        )
        self.start_youtube_playlist_import(playlist_url)

    def start_youtube_playlist_import(self, playlist_url: str) -> None:
        worker = YouTubePlaylistWorker(playlist_url, self.current_ytdlp_auth_options())
        thread = QThread(self)
        self.youtube_worker = worker
        self.youtube_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.playlist_ready.connect(self.on_youtube_playlist_ready)
        worker.playlist_progress.connect(self.on_pending_playlist_progress)
        worker.failed.connect(self.on_youtube_playlist_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_youtube_playlist_import_finished)
        thread.start()

    def on_youtube_playlist_ready(self, playlist: PlaylistEntry) -> None:
        if self.pending_playlist_index is None or self.pending_playlist_index >= len(
            self.playlists
        ):
            return
        self.refresh_local_music_tracks()
        playlist.is_loading = False
        playlist.loading_current = len(playlist.tracks)
        playlist.loading_total = len(playlist.tracks)
        self.sync_remote_playlist_with_library(playlist, persist=False)
        self.playlists[self.pending_playlist_index] = playlist
        widget = self.playlist_item_widgets[self.pending_playlist_index]
        widget.set_title(playlist.name)
        self.update_playlist_item_status(self.pending_playlist_index)
        self.persist_playlist(self.pending_playlist_index)
        self.playlist_list.setCurrentRow(self.pending_playlist_index)
        self.on_playlist_selected(self.pending_playlist_index)
        self.update_start_button_state()

    def on_youtube_playlist_failed(self, error_text: str) -> None:
        if (
            self.pending_playlist_index is not None
            and 0 <= self.pending_playlist_index < len(self.playlists)
        ):
            self.playlists.pop(self.pending_playlist_index)
            self.playlist_item_widgets.pop(self.pending_playlist_index)
            item = self.playlist_list.takeItem(self.pending_playlist_index)
            del item
            if not self.playlists:
                self.selected_playlist_index = None
                self.selected_experimental_track_index = None
                self.render_experimental_tracks([])
                self.update_metadata_panel()
            self.pending_playlist_index = None
        self.update_start_button_state()
        QMessageBox.warning(
            self,
            "YouTube",
            error_text or "Не удалось импортировать плейлист YouTube.",
        )

    def on_youtube_playlist_import_finished(self) -> None:
        self.youtube_thread = None
        self.youtube_worker = None
        self.pending_playlist_index = None
        self.create_playlist_button.setEnabled(True)
        self.update_start_button_state()

    def on_playlist_selected(self, row: int) -> None:
        for index, widget in enumerate(self.playlist_item_widgets):
            widget.set_selected(index == row)
        if row < 0 or row >= len(self.sidebar_items):
            self.experimental_source_mode = "none"
            self.selected_playlist_index = None
            self.clear_experimental_track_selection()
            self.render_experimental_tracks([])
            self.update_metadata_panel()
            self.update_delete_files_checkbox_visibility()
            return

        payload = self.sidebar_items[row]
        item_kind = str(payload.get("kind") or "")
        if item_kind == "playlist":
            playlist_index = int(payload.get("playlist_index", -1))
            if not (0 <= playlist_index < len(self.playlists)):
                return
            self.sort_field = "date"
            self.sort_ascending = False
            self.update_sort_button_labels()
            self.experimental_source_mode = "playlist"
            if self.playlists[playlist_index].source == "manual":
                self.playlists[playlist_index] = load_manual_playlist(
                    self.playlists[playlist_index].source_url,
                    self.music_library_dir,
                )
                self.playlist_item_widgets[row].set_title(
                    self.playlists[playlist_index].name
                )
                self.update_playlist_item_status(row)
            self.selected_playlist_index = playlist_index
            self.current_collection_label = self.playlists[playlist_index].name
            tracks = self.get_sorted_experimental_tracks(
                self.playlists[playlist_index].tracks
            )
        elif item_kind == "author":
            self.selected_author_name = str(payload.get("author") or "").strip()
            self.selected_album_name = None
            self.selected_playlist_index = None
            self.experimental_source_mode = "author_albums"
            self.current_collection_label = self.selected_author_name or "Авторы"
            self.clear_experimental_track_selection()
            self.render_author_album_cards(self.selected_author_name)
            self.update_metadata_panel()
            self.update_delete_files_checkbox_visibility()
            self.update_start_button_state()
            self.update_tracks_toolbar_visibility()
            return
        elif item_kind == "author_album":
            self.selected_playlist_index = None
            self.selected_album_name = str(payload.get("album") or "").strip()
            author_name = str(payload.get("author") or "").strip()
            self.current_collection_label = (
                f"{author_name} — {self.selected_album_name}"
            )
            self.sort_field = "date"
            self.sort_ascending = True
            self.update_sort_button_labels()
            album_groups, _ = self.author_album_groups(author_name)
            tracks = self.get_sorted_experimental_tracks(
                album_groups.get(self.selected_album_name, [])
            )
            self.experimental_source_mode = "author_collection"
        elif item_kind == "author_singles":
            self.selected_playlist_index = None
            author_name = str(payload.get("author") or "").strip()
            _, singles = self.author_album_groups(author_name)
            self.selected_album_name = ""
            self.current_collection_label = f"{author_name} — Синглы"
            tracks = self.get_sorted_experimental_tracks(singles)
            self.experimental_source_mode = "author_collection"
        elif item_kind == "album":
            self.selected_playlist_index = None
            self.selected_album_name = str(payload.get("album") or "").strip()
            self.current_collection_label = self.selected_album_name or "Альбом"
            self.sort_field = "date"
            self.sort_ascending = True
            self.update_sort_button_labels()
            tracks = self.get_sorted_experimental_tracks(
                self.grouped_tracks_by_album().get(self.selected_album_name, [])
            )
            self.experimental_source_mode = "album"
        else:
            self.experimental_source_mode = "none"
            self.selected_playlist_index = None
            self.clear_experimental_track_selection()
            self.render_experimental_tracks([])
            self.update_metadata_panel()
            self.update_delete_files_checkbox_visibility()
            self.update_start_button_state()
            return

        self.clear_experimental_track_selection()
        if tracks:
            self.selected_experimental_track_index = 0
            self.selected_experimental_track_indexes = {0}
            self.experimental_selection_anchor_index = 0
        self.render_experimental_tracks(tracks)
        self.update_metadata_panel()
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()

    def add_loading_playlist_entry(self, source_url: str, source: str) -> int:
        playlist = PlaylistEntry(
            name="Загрузка плейлиста...",
            source=source,
            source_url=source_url,
            tracks=[],
            is_loading=True,
            loading_current=0,
            loading_total=0,
        )
        self.playlists.append(playlist)
        row = self.add_playlist_list_item(playlist, len(self.playlists) - 1)
        self.playlist_list.setCurrentRow(row)
        self.on_playlist_selected(row)
        return row

    def on_pending_playlist_progress(self, loaded_count: int, total_count: int) -> None:
        if self.pending_playlist_index is None or not (
            0 <= self.pending_playlist_index < len(self.playlists)
        ):
            return
        playlist = self.playlists[self.pending_playlist_index]
        playlist.loading_current = max(0, loaded_count)
        playlist.loading_total = max(0, total_count)
        if (
            self.experimental_source_mode == "playlist"
            and self.selected_playlist_index == self.pending_playlist_index
        ):
            self.refresh_experimental_source_view()
            self.update_metadata_panel()

    def get_base_experimental_tracks(
        self,
    ) -> list[RemoteTrack] | list[LocalMusicTrack]:
        tracks: list[RemoteTrack] | list[LocalMusicTrack] = []
        if self.experimental_source_mode == "author_collection":
            if self.selected_author_name is None:
                return []
            album_groups, singles = self.author_album_groups(self.selected_author_name)
            if self.selected_album_name:
                tracks = self.get_sorted_experimental_tracks(
                    album_groups.get(self.selected_album_name, [])
                )
            else:
                tracks = self.get_sorted_experimental_tracks(singles)
        elif self.experimental_source_mode == "album":
            if not self.selected_album_name:
                return []
            tracks = self.get_sorted_experimental_tracks(
                self.grouped_tracks_by_album().get(self.selected_album_name, [])
            )
        elif self.experimental_source_mode == "all_music":
            tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
        elif self.experimental_source_mode == "home":
            tracks = list(self.current_displayed_tracks)
        elif self.experimental_source_mode == "author_albums":
            tracks = self.author_singles_for_display(self.selected_author_name or "")
        elif self.experimental_source_mode == "search_album_tracks":
            tracks = self.get_sorted_experimental_tracks(self.search_album_tracks)
        elif (
            self.experimental_source_mode == "playlist"
            and self.selected_playlist_index is not None
            and 0 <= self.selected_playlist_index < len(self.playlists)
        ):
            tracks = self.get_sorted_experimental_tracks(
                self.playlists[self.selected_playlist_index].tracks
            )
        return tracks

    def get_current_experimental_tracks(
        self,
    ) -> list[RemoteTrack] | list[LocalMusicTrack]:
        tracks = self.get_base_experimental_tracks()
        if self.has_active_track_search() and self.can_use_track_text_search():
            return self.search_track_results(self.track_search_edit.text())
        return self.apply_track_search_filter(tracks)

    def get_track_display_number(
        self,
        track: RemoteTrack | LocalMusicTrack,
        visible_index: int,
    ) -> int:
        if (
            isinstance(track, LocalMusicTrack)
            and track.track_number > 0
            and (
                self.experimental_source_mode == "album"
                or self.experimental_source_mode == "search_album_tracks"
                or (
                    self.experimental_source_mode == "author_collection"
                    and bool(self.selected_album_name)
                )
            )
        ):
            return track.track_number
        return visible_index + 1

    def apply_experimental_track_selection(self) -> None:
        for card_index, card in enumerate(self.remote_track_cards):
            card.set_selected(card_index in self.selected_experimental_track_indexes)

    def clear_experimental_track_selection(self) -> None:
        self.selected_experimental_track_index = None
        self.selected_experimental_track_indexes = set()
        self.experimental_selection_anchor_index = None

    def set_single_experimental_track_selection(self, index: int) -> None:
        self.selected_experimental_track_index = index
        self.selected_experimental_track_indexes = {index}
        self.experimental_selection_anchor_index = index
        self.apply_experimental_track_selection()
        self.update_metadata_panel()

    def set_range_experimental_track_selection(self, index: int) -> None:
        tracks = self.get_current_experimental_tracks()
        if not tracks:
            self.clear_experimental_track_selection()
            self.apply_experimental_track_selection()
            self.update_metadata_panel()
            return
        if self.experimental_selection_anchor_index is None:
            self.set_single_experimental_track_selection(index)
            return
        start = min(self.experimental_selection_anchor_index, index)
        end = max(self.experimental_selection_anchor_index, index)
        self.selected_experimental_track_index = index
        self.selected_experimental_track_indexes = set(range(start, end + 1))
        self.apply_experimental_track_selection()
        self.update_metadata_panel()

    def get_selected_experimental_track_indexes(self) -> list[int]:
        tracks = self.get_current_experimental_tracks()
        valid_indexes = sorted(
            index
            for index in self.selected_experimental_track_indexes
            if 0 <= index < len(tracks)
        )
        if valid_indexes:
            return valid_indexes
        if (
            self.selected_experimental_track_index is not None
            and 0 <= self.selected_experimental_track_index < len(tracks)
        ):
            return [self.selected_experimental_track_index]
        return []

    def should_show_track_previews(self) -> bool:
        if self.experimental_source_mode in {"album", "search_album_tracks"}:
            return False
        if (
            self.experimental_source_mode == "author_collection"
            and self.selected_album_name
        ):
            return False
        return True

    def should_show_track_artist_album(self) -> bool:
        return self.experimental_source_mode not in {
            "author_collection",
            "album",
            "search_album_tracks",
        }

    def should_use_compact_track_cards(self) -> bool:
        return self.experimental_source_mode in {
            "author_collection",
            "album",
            "search_album_tracks",
        }

    def track_preview_size(self) -> int:
        if self.experimental_source_mode == "author_collection" and not bool(
            self.selected_album_name
        ):
            return 54
        return 78

    def should_show_metadata_source(self) -> bool:
        if not self.get_selected_experimental_tracks():
            return False
        if self.experimental_source_mode == "playlist":
            return False
        if self.experimental_source_mode == "search_album_tracks":
            return False
        if self.experimental_source_mode == "author_collection" and not bool(
            self.selected_album_name
        ):
            return False
        return True

    def get_selected_experimental_tracks(self) -> list[RemoteTrack | LocalMusicTrack]:
        tracks = self.get_current_experimental_tracks()
        return [
            tracks[index] for index in self.get_selected_experimental_track_indexes()
        ]

    def get_selected_experimental_file_paths(self) -> list[str]:
        file_paths: list[str] = []
        for track in self.get_selected_experimental_tracks():
            if isinstance(track, LocalMusicTrack):
                if track.file_path:
                    file_paths.append(track.file_path)
                continue
            if track.local_file_path:
                file_paths.append(track.local_file_path)
        return file_paths

    def common_metadata_value(self, values: list[str]) -> str:
        normalized = [str(value or "").strip() for value in values]
        return (
            normalized[0]
            if normalized and all(value == normalized[0] for value in normalized)
            else ""
        )

    def is_album_metadata_mode(self) -> bool:
        return self.experimental_source_mode in {"album", "search_album_tracks"} or (
            self.experimental_source_mode == "author_collection"
            and bool(self.selected_album_name)
        )

    def should_show_album_track_location(self) -> bool:
        return not (
            self.experimental_source_mode == "search_album_tracks"
            or (
                self.experimental_source_mode == "author_collection"
                and bool(self.selected_album_name)
            )
        )

    def current_album_collection_tracks(self) -> list[LocalMusicTrack]:
        tracks = self.get_current_experimental_tracks()
        return [track for track in tracks if isinstance(track, LocalMusicTrack)]

    def load_editable_track_snapshot(
        self, track: RemoteTrack | LocalMusicTrack
    ) -> LocalMusicTrack | None:
        file_path = self.get_track_file_path(track)
        if not file_path or not os.path.exists(file_path):
            return None
        return load_music_track(file_path)

    def set_metadata_panel_dirty(self, is_dirty: bool) -> None:
        self.metadata_panel_dirty = is_dirty
        can_save = is_dirty and bool(
            self.metadata_panel_file_paths or self.metadata_panel_album_file_paths
        )
        self.metadata_save_button.setEnabled(can_save)
        self.metadata_cancel_button.setEnabled(is_dirty)

    def set_album_metadata_dirty(self, is_dirty: bool) -> None:
        self.metadata_album_dirty = is_dirty
        can_save = is_dirty and bool(self.metadata_panel_album_file_paths)
        self.metadata_album_save_button.setEnabled(can_save)
        self.metadata_album_cancel_button.setEnabled(is_dirty)

    def set_track_metadata_dirty(self, is_dirty: bool) -> None:
        self.metadata_track_dirty = is_dirty
        can_save = is_dirty and bool(self.metadata_panel_current_track_path)
        self.metadata_track_save_button.setEnabled(can_save)
        self.metadata_track_cancel_button.setEnabled(is_dirty)

    def on_metadata_panel_changed(self) -> None:
        if self.metadata_panel_updating:
            return
        if self.metadata_panel_mode == "album":
            original_values = self.metadata_panel_original_values
            album_current = {
                "album_title": self.metadata_album_title_edit.text().strip(),
                "album_author": self.metadata_album_author_edit.text().strip(),
            }
            track_current = {
                "track_title": self.metadata_track_title_edit.text().strip(),
                "track_number": self.metadata_track_number_edit.text().strip(),
            }
            album_dirty = (
                any(
                    album_current.get(key, "") != original_values.get(key, "")
                    for key in ["album_title", "album_author"]
                )
                or self.metadata_panel_cover_mode != "keep"
            )
            track_dirty = any(
                track_current.get(key, "") != original_values.get(key, "")
                for key in ["track_title", "track_number"]
            )
            self.set_album_metadata_dirty(album_dirty)
            self.set_track_metadata_dirty(track_dirty)
            return
        else:
            current_values = {
                "title": self.metadata_title_edit.text().strip(),
                "author": self.metadata_author_edit.text().strip(),
                "group": self.metadata_group_edit.text().strip(),
                "album": self.metadata_album_edit.text().strip(),
            }
            compared_keys = ["author", "group", "album"]
            if self.metadata_title_edit.isVisible():
                compared_keys.insert(0, "title")
        original_values = self.metadata_panel_original_values
        is_dirty = (
            any(
                current_values.get(key, "") != original_values.get(key, "")
                for key in compared_keys
            )
            or self.metadata_panel_cover_mode != "keep"
        )
        self.set_metadata_panel_dirty(is_dirty)

    def refresh_metadata_panel_cover_preview(self) -> None:
        pixmap = QPixmap()
        loaded = False
        if (
            self.metadata_panel_cover_mode == "custom"
            and self.metadata_panel_cover_path
            and os.path.exists(self.metadata_panel_cover_path)
        ):
            loaded = pixmap.load(self.metadata_panel_cover_path)
        elif self.metadata_panel_cover_mode != "clear":
            thumbnail_data = getattr(self, "metadata_panel_thumbnail_data", None)
            if thumbnail_data:
                loaded = pixmap.loadFromData(thumbnail_data)

        if loaded:
            self.metadata_cover_label.setPixmap(pixmap)
            self.metadata_cover_label.setText("")
        else:
            self.metadata_cover_label.clear()
            self.metadata_cover_label.setText("Нет\nобложки")

    def pick_metadata_panel_cover(self) -> None:
        if not self.metadata_pick_cover_button.isEnabled():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите обложку",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path:
            return
        self.metadata_panel_cover_path = path
        self.metadata_panel_cover_mode = "custom"
        self.refresh_metadata_panel_cover_preview()
        self.on_metadata_panel_changed()

    def clear_metadata_panel_cover(self) -> None:
        if not self.metadata_clear_cover_button.isEnabled():
            return
        self.metadata_panel_cover_path = ""
        self.metadata_panel_cover_mode = "clear"
        self.refresh_metadata_panel_cover_preview()
        self.on_metadata_panel_changed()

    def set_metadata_panel_edit_enabled(self, enabled: bool) -> None:
        self.metadata_title_edit.setEnabled(
            enabled and self.metadata_title_edit.isVisible()
        )
        self.metadata_author_edit.setEnabled(enabled)
        self.metadata_group_edit.setEnabled(enabled)
        self.metadata_album_edit.setEnabled(enabled)
        self.metadata_author_clear_button.setEnabled(
            enabled and self.metadata_author_row.isVisible()
        )
        self.metadata_group_clear_button.setEnabled(
            enabled and self.metadata_group_row.isVisible()
        )
        self.metadata_album_clear_button.setEnabled(
            enabled and self.metadata_album_row.isVisible()
        )
        self.metadata_album_title_edit.setEnabled(
            enabled and self.metadata_album_title_edit.isVisible()
        )
        self.metadata_album_author_edit.setEnabled(
            enabled and self.metadata_album_author_edit.isVisible()
        )
        self.metadata_album_title_clear_button.setEnabled(
            enabled and self.metadata_album_title_row.isVisible()
        )
        self.metadata_album_author_clear_button.setEnabled(
            enabled and self.metadata_album_author_row.isVisible()
        )
        self.metadata_track_title_edit.setEnabled(
            enabled and self.metadata_track_title_edit.isVisible()
        )
        self.metadata_track_number_edit.setEnabled(
            enabled and self.metadata_track_number_edit.isVisible()
        )
        self.metadata_track_location_button.setEnabled(
            bool(self.metadata_panel_current_track_path)
        )
        self.metadata_pick_cover_button.setEnabled(enabled)
        self.metadata_clear_cover_button.setEnabled(enabled)
        if not enabled:
            self.set_metadata_panel_dirty(False)
            self.set_album_metadata_dirty(False)
            self.set_track_metadata_dirty(False)

    def apply_metadata_panel_state(
        self,
        *,
        title_visible: bool,
        title: str,
        source: str,
        url_value: str,
        author: str,
        group: str,
        album: str,
        status: str,
        thumbnail_data: bytes | None,
        editable_file_paths: list[str],
    ) -> None:
        self.metadata_panel_updating = True
        self.metadata_panel_mode = "generic"
        self.metadata_album_section.setVisible(True)
        self.metadata_track_section.setVisible(False)
        self.metadata_generic_section.setVisible(True)
        self.metadata_title_label.setVisible(title_visible)
        self.metadata_title_edit.setVisible(title_visible)
        self.metadata_cancel_button.setVisible(True)
        self.metadata_save_button.setVisible(True)
        self.metadata_source_label.setVisible(False)
        self.metadata_source_value.setVisible(False)
        self.metadata_url_label.setVisible(False)
        self.metadata_url_value.setVisible(False)
        self.metadata_author_label.setVisible(True)
        self.metadata_author_edit.setVisible(True)
        self.metadata_author_row.setVisible(True)
        self.metadata_author_clear_button.setVisible(True)
        self.metadata_group_label.setVisible(True)
        self.metadata_group_edit.setVisible(True)
        self.metadata_group_row.setVisible(True)
        self.metadata_group_clear_button.setVisible(True)
        self.metadata_album_label.setVisible(True)
        self.metadata_album_edit.setVisible(True)
        self.metadata_album_row.setVisible(True)
        self.metadata_album_clear_button.setVisible(True)
        self.metadata_status_label.setVisible(False)
        self.metadata_status_value.setVisible(False)
        self.metadata_album_header.setVisible(False)
        self.metadata_album_title_label.setVisible(False)
        self.metadata_album_title_edit.setVisible(False)
        self.metadata_album_title_row.setVisible(False)
        self.metadata_album_title_clear_button.setVisible(False)
        self.metadata_album_author_label.setVisible(False)
        self.metadata_album_author_edit.setVisible(False)
        self.metadata_album_author_row.setVisible(False)
        self.metadata_album_author_clear_button.setVisible(False)
        self.metadata_album_cancel_button.setVisible(False)
        self.metadata_album_save_button.setVisible(False)
        self.metadata_album_separator.setVisible(False)
        self.metadata_track_header.setVisible(False)
        self.metadata_track_title_label.setVisible(False)
        self.metadata_track_title_edit.setVisible(False)
        self.metadata_track_number_label.setVisible(False)
        self.metadata_track_number_edit.setVisible(False)
        self.metadata_track_location_label.setVisible(False)
        self.metadata_track_location_button.setVisible(False)
        self.metadata_track_cancel_button.setVisible(False)
        self.metadata_track_save_button.setVisible(False)
        self.metadata_title_edit.setText(title)
        self.metadata_source_value.setText("")
        self.metadata_url_value.setText(url_value or "—")
        self.metadata_author_edit.setText(author)
        self.metadata_group_edit.setText(group)
        self.metadata_album_edit.setText(album)
        self.metadata_status_value.setText(status or "—")
        self.metadata_panel_thumbnail_data = thumbnail_data
        self.metadata_panel_cover_path = ""
        self.metadata_panel_cover_mode = "keep"
        self.metadata_panel_file_paths = list(editable_file_paths)
        self.metadata_panel_album_file_paths = []
        self.metadata_panel_current_track_path = (
            editable_file_paths[0] if editable_file_paths else ""
        )
        self.metadata_panel_original_values = {
            "title": title.strip(),
            "author": author.strip(),
            "group": group.strip(),
            "album": album.strip(),
        }
        self.refresh_metadata_panel_cover_preview()
        self.metadata_panel_updating = False
        self.set_metadata_panel_edit_enabled(bool(editable_file_paths))
        self.set_metadata_panel_dirty(False)
        self.set_album_metadata_dirty(False)
        self.set_track_metadata_dirty(False)

    def restore_experimental_selection_by_file_paths(
        self, file_paths: list[str] | set[str]
    ) -> None:
        normalized_paths = {
            os.path.realpath(path)
            for path in file_paths
            if path and os.path.exists(path)
        }
        tracks = self.get_current_experimental_tracks()
        selected_indexes: set[int] = set()
        for index, track in enumerate(tracks):
            track_path = self.get_track_file_path(track)
            if track_path and os.path.realpath(track_path) in normalized_paths:
                selected_indexes.add(index)
        self.selected_experimental_track_indexes = selected_indexes
        if selected_indexes:
            first_index = min(selected_indexes)
            self.selected_experimental_track_index = first_index
            self.experimental_selection_anchor_index = first_index
        else:
            self.clear_experimental_track_selection()
        self.apply_experimental_track_selection()

    def apply_album_metadata_panel_state(
        self,
        *,
        album_title: str,
        album_author: str,
        track_title: str,
        track_number: int,
        track_path: str,
        thumbnail_data: bytes | None,
        album_file_paths: list[str],
    ) -> None:
        self.metadata_panel_updating = True
        self.metadata_panel_mode = "album"
        self.metadata_album_section.setVisible(True)
        self.metadata_track_section.setVisible(True)
        self.metadata_generic_section.setVisible(False)
        self.metadata_title_label.setVisible(False)
        self.metadata_title_edit.setVisible(False)
        self.metadata_cancel_button.setVisible(False)
        self.metadata_save_button.setVisible(False)
        self.metadata_source_label.setVisible(False)
        self.metadata_source_value.setVisible(False)
        self.metadata_url_label.setVisible(False)
        self.metadata_url_value.setVisible(False)
        self.metadata_author_label.setVisible(False)
        self.metadata_author_edit.setVisible(False)
        self.metadata_author_row.setVisible(False)
        self.metadata_author_clear_button.setVisible(False)
        self.metadata_group_label.setVisible(False)
        self.metadata_group_edit.setVisible(False)
        self.metadata_group_row.setVisible(False)
        self.metadata_group_clear_button.setVisible(False)
        self.metadata_album_label.setVisible(False)
        self.metadata_album_edit.setVisible(False)
        self.metadata_album_row.setVisible(False)
        self.metadata_album_clear_button.setVisible(False)
        self.metadata_status_label.setVisible(False)
        self.metadata_status_value.setVisible(False)

        self.metadata_album_header.setVisible(False)
        self.metadata_album_title_label.setVisible(True)
        self.metadata_album_title_edit.setVisible(True)
        self.metadata_album_title_row.setVisible(True)
        self.metadata_album_title_clear_button.setVisible(True)
        self.metadata_album_author_label.setVisible(True)
        self.metadata_album_author_edit.setVisible(True)
        self.metadata_album_author_row.setVisible(True)
        self.metadata_album_author_clear_button.setVisible(True)
        self.metadata_album_cancel_button.setVisible(True)
        self.metadata_album_save_button.setVisible(True)
        self.metadata_album_separator.setVisible(False)
        self.metadata_track_header.setVisible(False)
        self.metadata_track_title_label.setVisible(True)
        self.metadata_track_title_edit.setVisible(True)
        self.metadata_track_number_label.setVisible(True)
        self.metadata_track_number_edit.setVisible(True)
        self.metadata_track_cancel_button.setVisible(True)
        self.metadata_track_save_button.setVisible(True)
        show_track_location = self.should_show_album_track_location()
        self.metadata_track_location_label.setVisible(show_track_location)
        self.metadata_track_location_button.setVisible(show_track_location)

        self.metadata_album_title_edit.setText(album_title)
        self.metadata_album_author_edit.setText(album_author)
        self.metadata_track_title_edit.setText(track_title)
        self.metadata_track_number_edit.setText(
            str(track_number) if track_number > 0 else ""
        )
        self.metadata_panel_thumbnail_data = thumbnail_data
        self.metadata_panel_cover_path = ""
        self.metadata_panel_cover_mode = "keep"
        self.metadata_panel_file_paths = [track_path] if track_path else []
        self.metadata_panel_album_file_paths = list(album_file_paths)
        self.metadata_panel_current_track_path = track_path
        self.metadata_panel_original_values = {
            "album_title": album_title.strip(),
            "album_author": album_author.strip(),
            "track_title": track_title.strip(),
            "track_number": str(track_number) if track_number > 0 else "",
        }
        self.refresh_metadata_panel_cover_preview()
        self.metadata_panel_updating = False
        self.set_metadata_panel_edit_enabled(bool(album_file_paths))
        self.set_metadata_panel_dirty(False)
        self.set_album_metadata_dirty(False)
        self.set_track_metadata_dirty(False)

    def open_metadata_panel_track_location(self) -> None:
        if not self.metadata_panel_current_track_path:
            return
        self.reveal_file_in_file_manager(
            self.metadata_panel_current_track_path,
            "Открыть расположение",
            "Файл трека не найден.",
        )

    def cancel_metadata_panel_changes(self) -> None:
        self.update_metadata_panel()

    def cancel_album_metadata_panel_changes(self) -> None:
        if self.metadata_panel_mode != "album":
            return
        self.metadata_panel_updating = True
        self.metadata_album_title_edit.setText(
            self.metadata_panel_original_values.get("album_title", "")
        )
        self.metadata_album_author_edit.setText(
            self.metadata_panel_original_values.get("album_author", "")
        )
        self.metadata_panel_cover_path = ""
        self.metadata_panel_cover_mode = "keep"
        self.refresh_metadata_panel_cover_preview()
        self.metadata_panel_updating = False
        self.on_metadata_panel_changed()

    def cancel_track_metadata_panel_changes(self) -> None:
        if self.metadata_panel_mode != "album":
            return
        self.metadata_panel_updating = True
        self.metadata_track_title_edit.setText(
            self.metadata_panel_original_values.get("track_title", "")
        )
        self.metadata_track_number_edit.setText(
            self.metadata_panel_original_values.get("track_number", "")
        )
        self.metadata_panel_updating = False
        self.on_metadata_panel_changed()

    def save_album_metadata_panel_changes(self) -> None:
        if self.metadata_panel_mode != "album":
            return
        album_tracks = [
            snapshot
            for snapshot in (
                self.load_editable_track_snapshot(track)
                for track in self.current_album_collection_tracks()
            )
            if snapshot is not None
        ]
        if not album_tracks:
            return

        album_title = self.metadata_album_title_edit.text().strip()
        album_author = self.metadata_album_author_edit.text().strip()

        updated_file_paths: list[str] = []
        selected_updated_path = ""
        for snapshot in album_tracks:
            try:
                apply_mp3_metadata(
                    snapshot.file_path,
                    title=snapshot.title,
                    author=album_author,
                    group=snapshot.group,
                    album=album_title,
                    cover_mode=self.metadata_panel_cover_mode,
                    cover_path=self.metadata_panel_cover_path,
                    track_number=snapshot.track_number or None,
                )
                updated_file_paths.append(
                    self.relocate_music_file_after_metadata_edit(
                        snapshot.file_path,
                        title=snapshot.title,
                        author=album_author,
                        album=album_title,
                    )
                )
                if self.metadata_panel_current_track_path and os.path.realpath(
                    snapshot.file_path
                ) == os.path.realpath(self.metadata_panel_current_track_path):
                    selected_updated_path = updated_file_paths[-1]
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Метаданные",
                    f"Не удалось обновить метаданные альбома:\n{exc}",
                )
                return
        self.refresh_experimental_track_sources_after_metadata_edit(
            selected_updated_path or updated_file_paths[:1]
        )

    def save_track_metadata_panel_changes(self) -> None:
        if self.metadata_panel_mode != "album":
            return
        selected_tracks = self.get_selected_experimental_tracks()
        selected_track = selected_tracks[0] if selected_tracks else None
        selected_snapshot = (
            self.load_editable_track_snapshot(selected_track)
            if selected_track is not None
            else None
        )
        if selected_snapshot is None:
            QMessageBox.information(
                self,
                "Метаданные",
                "Не удалось определить выбранный трек альбома.",
            )
            return

        track_title = (
            self.metadata_track_title_edit.text().strip()
            or self.metadata_panel_original_values.get(
                "track_title", selected_snapshot.title
            )
        )
        raw_track_number = self.metadata_track_number_edit.text().strip()
        try:
            selected_track_number = int(raw_track_number) if raw_track_number else 0
        except ValueError:
            QMessageBox.warning(
                self,
                "Метаданные",
                "Номер трека должен быть числом.",
            )
            return

        try:
            apply_mp3_metadata(
                selected_snapshot.file_path,
                title=track_title,
                author=selected_snapshot.artists,
                group=selected_snapshot.group,
                album=selected_snapshot.album,
                cover_mode="keep",
                cover_path="",
                track_number=selected_track_number or None,
            )
            final_file_path = self.relocate_music_file_after_metadata_edit(
                selected_snapshot.file_path,
                title=track_title,
                author=selected_snapshot.artists,
                album=selected_snapshot.album,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Метаданные",
                f"Не удалось обновить метаданные трека:\n{exc}",
            )
            return
        self.refresh_experimental_track_sources_after_metadata_edit(final_file_path)

    def save_metadata_panel_changes(self) -> None:
        selected_tracks = self.get_selected_experimental_tracks()
        if self.metadata_panel_mode == "album":
            self.save_album_metadata_panel_changes()
            return

        if not selected_tracks or not self.metadata_panel_file_paths:
            return

        if len(selected_tracks) == 1:
            track = selected_tracks[0]
            snapshot = self.load_editable_track_snapshot(track)
            if snapshot is None:
                QMessageBox.information(
                    self,
                    "Метаданные",
                    "Метаданные можно редактировать только у скачанных mp3-файлов.",
                )
                return
            values = {
                "title": self.metadata_title_edit.text().strip()
                or self.metadata_panel_original_values.get("title", snapshot.title),
                "author": self.metadata_author_edit.text().strip(),
                "group": self.metadata_group_edit.text().strip(),
                "album": self.metadata_album_edit.text().strip(),
            }
            try:
                apply_mp3_metadata(
                    snapshot.file_path,
                    title=values["title"],
                    author=values["author"],
                    group=values["group"],
                    album=values["album"],
                    cover_mode=self.metadata_panel_cover_mode,
                    cover_path=self.metadata_panel_cover_path,
                    track_number=snapshot.track_number or None,
                )
                final_file_path = self.relocate_music_file_after_metadata_edit(
                    snapshot.file_path,
                    title=values["title"],
                    author=values["author"],
                    album=values["album"],
                )
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Метаданные",
                    f"Не удалось обновить метаданные трека:\n{exc}",
                )
                return
            self.refresh_experimental_track_sources_after_metadata_edit(final_file_path)
            return

        updated_file_paths: list[str] = []
        for track in selected_tracks:
            snapshot = self.load_editable_track_snapshot(track)
            if snapshot is None:
                continue
            values = {
                "title": snapshot.title,
                "author": self.metadata_author_edit.text().strip(),
                "group": self.metadata_group_edit.text().strip(),
                "album": self.metadata_album_edit.text().strip(),
            }
            try:
                apply_mp3_metadata(
                    snapshot.file_path,
                    title=values["title"],
                    author=values["author"],
                    group=values["group"],
                    album=values["album"],
                    cover_mode=self.metadata_panel_cover_mode,
                    cover_path=self.metadata_panel_cover_path,
                    track_number=snapshot.track_number or None,
                )
                updated_file_paths.append(
                    self.relocate_music_file_after_metadata_edit(
                        snapshot.file_path,
                        title=values["title"],
                        author=values["author"],
                        album=values["album"],
                    )
                )
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Метаданные",
                    f"Не удалось обновить общие метаданные:\n{exc}",
                )
                return
        if updated_file_paths:
            self.refresh_experimental_track_sources_after_metadata_edit(
                updated_file_paths
            )

    def clear_track_results_layout(self) -> None:
        while self.playlist_tracks_layout.count():
            item = self.playlist_tracks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def track_latest_added_at(
        self, tracks: list[RemoteTrack | LocalMusicTrack]
    ) -> float:
        return max(
            (
                float(getattr(track, "added_at", 0.0) or 0.0)
                for track in tracks
                if isinstance(track, LocalMusicTrack)
            ),
            default=0.0,
        )

    def playlist_latest_added_at(self, playlist: PlaylistEntry) -> float:
        latest_track_time = self.track_latest_added_at(playlist.tracks)
        if latest_track_time > 0:
            return latest_track_time
        playlist_path = str(getattr(playlist, "source_url", "") or "").strip()
        if playlist_path and os.path.exists(playlist_path):
            try:
                return os.path.getmtime(playlist_path)
            except OSError:
                return 0.0
        return 0.0

    def unique_cover_items_for_tracks(
        self, tracks: list[RemoteTrack | LocalMusicTrack]
    ) -> list[bytes]:
        cover_items: list[bytes] = []
        used_keys: set[str] = set()
        for track in tracks:
            cover_data = getattr(track, "thumbnail_data", None)
            if not cover_data:
                continue
            album_name = str(getattr(track, "album", "") or "").strip()
            artists_name = str(getattr(track, "artists", "") or "").strip()
            title_name = str(getattr(track, "title", "") or "").strip()
            unique_key = (
                f"album:{album_name.casefold()}"
                if album_name
                else f"single:{artists_name.casefold()}:{title_name.casefold()}"
            )
            if unique_key in used_keys:
                continue
            used_keys.add(unique_key)
            cover_items.append(cover_data)
            if len(cover_items) == 4:
                break
        return cover_items

    def home_album_items(self) -> list[dict[str, object]]:
        grouped: dict[tuple[str, str], list[LocalMusicTrack]] = {}
        for track in self.local_music_tracks:
            album_name = track.album.strip()
            if not album_name:
                continue
            grouped.setdefault((album_name, track.artists.strip()), []).append(track)

        items: list[dict[str, object]] = []
        self.home_album_tracks_by_key = {}
        for (album_name, author_name), tracks in grouped.items():
            sorted_tracks = sorted(
                tracks,
                key=lambda track: (
                    track.track_number if track.track_number > 0 else 9999,
                    track.added_at,
                ),
            )
            self.home_album_tracks_by_key[(album_name, author_name)] = sorted_tracks
            items.append(
                {
                    "album": album_name,
                    "author": author_name,
                    "track_count": len(tracks),
                    "thumbnail_data": next(
                        (
                            track.thumbnail_data
                            for track in tracks
                            if track.thumbnail_data
                        ),
                        None,
                    ),
                    "latest": self.track_latest_added_at(tracks),
                }
            )
        items.sort(
            key=lambda item: (
                float(item["latest"]),
                str(item["album"]).casefold(),
                str(item["author"]).casefold(),
            ),
            reverse=True,
        )
        return items

    def home_author_items(self) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for author_name, tracks in self.grouped_tracks_by_author().items():
            album_count = len(
                {track.album.strip() for track in tracks if track.album.strip()}
            )
            items.append(
                {
                    "author": author_name,
                    "track_count": len(tracks),
                    "album_count": album_count,
                    "latest": self.track_latest_added_at(tracks),
                }
            )
        items.sort(
            key=lambda item: (
                float(item["latest"]),
                str(item["author"]).casefold(),
            ),
            reverse=True,
        )
        return items

    def home_playlist_items(self) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for playlist_index, playlist in enumerate(self.playlists):
            author_names = {
                str(getattr(track, "artists", "") or "").strip()
                for track in playlist.tracks
                if str(getattr(track, "artists", "") or "").strip()
            }
            items.append(
                {
                    "playlist_index": playlist_index,
                    "playlist_name": playlist.name,
                    "track_count": len(playlist.tracks),
                    "author_count": len(author_names),
                    "cover_items": self.unique_cover_items_for_tracks(playlist.tracks),
                    "latest": self.playlist_latest_added_at(playlist),
                }
            )
        items.sort(
            key=lambda item: (
                float(item["latest"]),
                str(item["playlist_name"]).casefold(),
            ),
            reverse=True,
        )
        return items

    def home_singles(self) -> list[LocalMusicTrack]:
        return sorted(
            [track for track in self.local_music_tracks if not track.album.strip()],
            key=lambda track: (track.added_at, track.title.casefold()),
            reverse=True,
        )

    def home_section_label(self, title: str) -> QLabel:
        colors = self.theme_colors()
        label = QLabel(title)
        label.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{colors['text_primary']}; background:transparent; border:none;"
        )
        return label

    def make_horizontal_home_section(
        self,
        title: str,
        widgets: list[QWidget],
        *,
        empty_text: str,
    ) -> QWidget:
        colors = self.theme_colors()
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(8)
        section_layout.addWidget(self.home_section_label(title))

        if not widgets:
            empty_label = QLabel(empty_text)
            empty_label.setStyleSheet(
                f"font-size:12px; color:{colors['text_muted']}; background:transparent; border:none;"
            )
            section_layout.addWidget(empty_label)
            return section

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(max(widget.height() for widget in widgets) + 18)
        scroll.setStyleSheet(self.horizontal_scrollbar_style())
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        for widget in widgets:
            content_layout.addWidget(widget)
        content_layout.addStretch(1)
        content.adjustSize()
        scroll.setWidget(content)
        section_layout.addWidget(scroll)
        return section

    def render_home_album_grid(self, album_items: list[dict[str, object]]) -> QWidget:
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(8)
        section_layout.addWidget(self.home_section_label("Альбомы"))
        if not album_items:
            colors = self.theme_colors()
            empty_label = QLabel("Альбомы не найдены")
            empty_label.setStyleSheet(
                f"font-size:12px; color:{colors['text_muted']}; background:transparent; border:none;"
            )
            section_layout.addWidget(empty_label)
            return section

        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setHorizontalSpacing(12)
        grid_layout.setVerticalSpacing(12)
        viewport_width = max(1, self.playlist_tracks_scroll.viewport().width())
        card_width = 176
        columns = max(1, (viewport_width + 12) // (card_width + 12))
        for index, item in enumerate(album_items):
            card = SearchAlbumCard(
                str(item["album"]),
                str(item["author"]),
                int(item["track_count"]),
                item.get("thumbnail_data"),
            )
            card.apply_theme(self.is_dark_theme())
            card.clicked.connect(self.on_home_album_selected)
            card.delete_requested.connect(self.on_middle_album_delete_requested)
            grid_layout.addWidget(card, index // columns, index % columns)
        grid_layout.setColumnStretch(columns, 1)
        section_layout.addWidget(grid_container)
        return section

    def render_home_page(self) -> None:
        self.search_results_active = False
        self.current_displayed_tracks = []
        self.remote_track_cards = []
        self.clear_track_results_layout()

        playlist_cards: list[QWidget] = []
        for item in self.home_playlist_items():
            card = SearchPlaylistCard(
                int(item["playlist_index"]),
                str(item["playlist_name"]),
                int(item["track_count"]),
                int(item["author_count"]),
                list(item["cover_items"]),
            )
            card.apply_theme(self.is_dark_theme())
            card.clicked.connect(self.on_search_playlist_selected)
            card.delete_requested.connect(self.on_middle_playlist_delete_requested)
            playlist_cards.append(card)

        author_cards: list[QWidget] = []
        for item in self.home_author_items():
            card = HomeAuthorCard(
                str(item["author"]),
                int(item["track_count"]),
                int(item["album_count"]),
            )
            card.apply_theme(self.is_dark_theme())
            card.clicked.connect(self.on_home_author_selected)
            card.delete_requested.connect(self.on_middle_author_delete_requested)
            author_cards.append(card)

        self.playlist_tracks_layout.addWidget(
            self.make_horizontal_home_section(
                "Плейлисты",
                playlist_cards,
                empty_text="Плейлисты не найдены",
            )
        )
        self.playlist_tracks_layout.addWidget(
            self.make_horizontal_home_section(
                "Авторы",
                author_cards,
                empty_text="Авторы не найдены",
            )
        )
        self.playlist_tracks_layout.addWidget(
            self.render_home_album_grid(self.home_album_items())
        )

        singles = self.home_singles()
        self.playlist_tracks_layout.addWidget(self.home_section_label("Синглы"))
        if singles:
            for track_index, track in enumerate(singles):
                card = RemoteTrackCard(
                    track,
                    track_index,
                    self.status_icons,
                    self.metadata_icon,
                    self.reveal_icon,
                    show_preview=True,
                    display_number=track_index + 1,
                    show_artist_album=True,
                    compact=self.should_use_compact_track_cards(),
                    preview_size=self.track_preview_size(),
                )
                card.apply_theme(self.is_dark_theme())
                card.selected.connect(self.on_remote_track_selected)
                card.context_requested.connect(self.on_remote_track_context_requested)
                card.reveal_requested.connect(
                    self.on_experimental_track_reveal_requested
                )
                card.delete_requested.connect(
                    self.on_experimental_track_delete_requested
                )
                self.remote_track_cards.append(card)
                self.playlist_tracks_layout.addWidget(card)
            self.current_displayed_tracks = singles
        else:
            colors = self.theme_colors()
            empty_label = QLabel("Синглы не найдены")
            empty_label.setStyleSheet(
                f"font-size:12px; color:{colors['text_muted']}; background:transparent; border:none;"
            )
            self.playlist_tracks_layout.addWidget(empty_label)
        self.playlist_tracks_layout.addStretch(1)

    def on_home_album_selected(self, album_name: str, author_name: str) -> None:
        tracks = self.home_album_tracks_by_key.get((album_name, author_name), [])
        if not tracks:
            tracks = [
                track
                for track in self.local_music_tracks
                if track.album.strip() == album_name
                and track.artists.strip() == author_name
            ]
        self.search_album_tracks = list(tracks)
        self.experimental_source_mode = "search_album_tracks"
        self.current_collection_label = album_name
        self.selected_album_name = album_name
        self.selected_author_name = author_name
        self.sort_field = "date"
        self.sort_ascending = True
        self.update_sort_button_labels()
        self.clear_experimental_track_selection()
        if self.search_album_tracks:
            self.selected_experimental_track_index = 0
            self.selected_experimental_track_indexes = {0}
            self.experimental_selection_anchor_index = 0
        self.render_experimental_tracks(self.get_current_experimental_tracks())
        self.update_metadata_panel()
        self.update_tracks_toolbar_visibility()

    def on_home_author_selected(self, author_name: str) -> None:
        self.set_library_view_mode("authors")
        for row, payload in enumerate(self.sidebar_items):
            if payload.get("kind") == "author" and payload.get("author") == author_name:
                self.playlist_list.setCurrentRow(row)
                self.on_playlist_selected(row)
                return

    def render_search_result_grid(
        self,
        widgets: list[QWidget],
        *,
        empty_text: str,
    ) -> None:
        self.clear_experimental_track_selection()
        self.current_displayed_tracks = []
        self.remote_track_cards = []
        self.clear_track_results_layout()

        if not widgets:
            self.playlist_tracks_empty = QLabel(empty_text)
            self.playlist_tracks_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            colors = self.theme_colors()
            self.playlist_tracks_empty.setStyleSheet(
                f"font-size:14px; color:{colors['text_muted']}; background:transparent; border:none;"
            )
            self.playlist_tracks_layout.addWidget(self.playlist_tracks_empty)
            self.playlist_tracks_layout.addStretch(1)
            return

        viewport_width = max(1, self.playlist_tracks_scroll.viewport().width())
        card_width = widgets[0].width()
        columns = max(1, (viewport_width + 12) // (card_width + 12))
        grid_container = QWidget()
        grid_layout = QGridLayout(grid_container)
        grid_layout.setContentsMargins(4, 4, 4, 4)
        grid_layout.setHorizontalSpacing(12)
        grid_layout.setVerticalSpacing(12)

        for index, widget in enumerate(widgets):
            row = index // columns
            column = index % columns
            grid_layout.addWidget(widget, row, column)
        grid_layout.setColumnStretch(columns, 1)
        self.playlist_tracks_layout.addWidget(grid_container)
        self.playlist_tracks_layout.addStretch(1)

    def render_author_album_cards(self, author_name: str) -> None:
        author_name = str(author_name or "").strip()
        if not author_name:
            self.render_search_result_grid([], empty_text="Выберите автора")
            return

        album_groups, singles = self.author_album_groups(author_name)
        singles = self.author_singles_for_display(author_name)
        cards: list[QWidget] = []
        for album_name in sorted(album_groups, key=str.casefold):
            tracks = album_groups.get(album_name, [])
            card = SearchAlbumCard(
                album_name,
                author_name,
                len(tracks),
                next(
                    (track.thumbnail_data for track in tracks if track.thumbnail_data),
                    None,
                ),
            )
            card.apply_theme(self.is_dark_theme())
            card.clicked.connect(self.on_author_album_card_selected)
            card.delete_requested.connect(self.on_middle_album_delete_requested)
            cards.append(card)

        self.search_results_active = False
        self.current_displayed_tracks = list(singles)
        self.remote_track_cards = []
        self.clear_experimental_track_selection()
        self.clear_track_results_layout()

        if not cards and not singles:
            self.playlist_tracks_empty = QLabel("Альбомы и синглы автора не найдены")
            self.playlist_tracks_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            colors = self.theme_colors()
            self.playlist_tracks_empty.setStyleSheet(
                f"font-size:14px; color:{colors['text_muted']}; background:transparent; border:none;"
            )
            self.playlist_tracks_layout.addWidget(self.playlist_tracks_empty)
            self.playlist_tracks_layout.addStretch(1)
            return

        if cards:
            viewport_width = max(1, self.playlist_tracks_scroll.viewport().width())
            card_width = cards[0].width()
            columns = max(1, (viewport_width + 12) // (card_width + 12))
            grid_container = QWidget()
            grid_layout = QGridLayout(grid_container)
            grid_layout.setContentsMargins(4, 4, 4, 4)
            grid_layout.setHorizontalSpacing(12)
            grid_layout.setVerticalSpacing(12)
            for index, widget in enumerate(cards):
                grid_layout.addWidget(widget, index // columns, index % columns)
            grid_layout.setColumnStretch(columns, 1)
            self.playlist_tracks_layout.addWidget(grid_container)

        if singles:
            singles_label = self.home_section_label("Синглы")
            self.playlist_tracks_layout.addWidget(singles_label)
            for track_index, track in enumerate(singles):
                card = RemoteTrackCard(
                    track,
                    track_index,
                    self.status_icons,
                    self.metadata_icon,
                    self.reveal_icon,
                    show_preview=True,
                    display_number=track_index + 1,
                    show_artist_album=False,
                    compact=False,
                    preview_size=self.track_preview_size(),
                )
                card.apply_theme(self.is_dark_theme())
                card.selected.connect(self.on_remote_track_selected)
                card.context_requested.connect(self.on_remote_track_context_requested)
                card.reveal_requested.connect(
                    self.on_experimental_track_reveal_requested
                )
                card.delete_requested.connect(
                    self.on_experimental_track_delete_requested
                )
                self.remote_track_cards.append(card)
                self.playlist_tracks_layout.addWidget(card)

        self.playlist_tracks_layout.addStretch(1)

    def on_author_album_card_selected(self, album_name: str, author_name: str) -> None:
        self.search_results_active = False
        self.search_author_focus = None
        self.track_search_scope = "tracks"
        self.update_track_search_filter_button()
        self.track_search_edit.blockSignals(True)
        self.track_search_edit.clear()
        self.track_search_edit.blockSignals(False)
        self.last_search_query = ""
        self.clear_track_search_focus()

        self.selected_playlist_index = None
        self.selected_author_name = author_name
        self.selected_album_name = "" if album_name == "Синглы" else album_name
        self.experimental_source_mode = "author_collection"
        self.current_collection_label = (
            f"{author_name} — Синглы"
            if not self.selected_album_name
            else f"{author_name} — {self.selected_album_name}"
        )
        self.sort_field = "date"
        self.sort_ascending = True
        self.update_sort_button_labels()
        self.clear_experimental_track_selection()
        tracks = self.get_current_experimental_tracks()
        if tracks:
            self.selected_experimental_track_index = 0
            self.selected_experimental_track_indexes = {0}
            self.experimental_selection_anchor_index = 0
        self.render_experimental_tracks(tracks)
        self.update_metadata_panel()
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()
        self.update_tracks_toolbar_visibility()

    def render_track_search_results(self) -> None:
        query = self.track_search_edit.text().strip()
        if not query:
            self.search_results_active = False
            self.render_empty_track_results()
            return
        self.search_results_active = True
        if self.track_search_scope == "authors":
            results = self.build_author_search_results(query)
            cards: list[QWidget] = []
            for item in results:
                card = SearchAuthorCard(
                    str(item["author"]),
                    int(item["track_count"]),
                    int(item["album_count"]),
                )
                card.apply_theme(self.is_dark_theme())
                card.clicked.connect(self.on_search_author_selected)
                card.delete_requested.connect(self.on_middle_author_delete_requested)
                cards.append(card)
            self.render_search_result_grid(cards, empty_text="Авторы не найдены")
            return
        if self.track_search_scope == "playlists":
            results = self.build_playlist_search_results(query)
            cards = []
            for item in results:
                card = SearchPlaylistCard(
                    int(item["playlist_index"]),
                    str(item["playlist_name"]),
                    int(item["track_count"]),
                    int(item["author_count"]),
                    list(item["cover_items"]),
                )
                card.apply_theme(self.is_dark_theme())
                card.clicked.connect(self.on_search_playlist_selected)
                card.delete_requested.connect(self.on_middle_playlist_delete_requested)
                cards.append(card)
            self.render_search_result_grid(cards, empty_text="Плейлисты не найдены")
            return

        results = self.build_album_search_results(
            query,
            author_filter=self.search_author_focus,
        )
        cards = []
        for item in results:
            card = SearchAlbumCard(
                str(item["album"]),
                str(item["author"]),
                int(item["track_count"]),
                item.get("thumbnail_data"),
            )
            card.apply_theme(self.is_dark_theme())
            card.clicked.connect(self.on_search_album_selected)
            card.delete_requested.connect(self.on_middle_album_delete_requested)
            cards.append(card)
        self.render_search_result_grid(cards, empty_text="Альбомы не найдены")

    def on_search_author_selected(self, author_name: str) -> None:
        self.search_author_focus = author_name
        self.track_search_scope = "albums"
        self.update_track_search_filter_button()
        self.render_track_search_results()
        self.update_metadata_panel()
        self.update_tracks_toolbar_visibility()

    def on_search_album_selected(self, album_name: str, author_name: str) -> None:
        results = self.build_album_search_results(
            self.track_search_edit.text().strip(),
            author_filter=self.search_author_focus,
        )
        selected_tracks = next(
            (
                list(item["tracks"])
                for item in results
                if str(item["album"]) == album_name
                and str(item["author"]) == author_name
            ),
            [],
        )
        self.search_album_tracks = [
            track for track in selected_tracks if isinstance(track, LocalMusicTrack)
        ]
        self.experimental_source_mode = "search_album_tracks"
        self.search_results_active = False
        self.current_collection_label = album_name
        self.selected_album_name = album_name
        self.selected_author_name = author_name
        self.sort_field = "date"
        self.sort_ascending = True
        self.update_sort_button_labels()
        self.search_author_focus = None
        self.track_search_scope = "tracks"
        self.update_track_search_filter_button()
        self.track_search_edit.blockSignals(True)
        self.track_search_edit.clear()
        self.track_search_edit.blockSignals(False)
        self.last_search_query = ""
        self.clear_track_search_focus()
        self.clear_experimental_track_selection()
        if self.search_album_tracks:
            self.selected_experimental_track_index = 0
            self.selected_experimental_track_indexes = {0}
            self.experimental_selection_anchor_index = 0
        self.render_experimental_tracks(self.get_current_experimental_tracks())
        self.update_metadata_panel()
        self.update_tracks_toolbar_visibility()

    def on_search_playlist_selected(self, playlist_index: int) -> None:
        if not (0 <= playlist_index < len(self.playlists)):
            return
        self.search_results_active = False
        self.search_author_focus = None
        self.track_search_scope = "tracks"
        self.update_track_search_filter_button()
        self.track_search_edit.blockSignals(True)
        self.track_search_edit.clear()
        self.track_search_edit.blockSignals(False)
        self.last_search_query = ""
        self.clear_track_search_focus()
        if self.library_view_mode != "playlists":
            self.set_library_view_mode("playlists")
        row = next(
            (
                index
                for index, payload in enumerate(self.sidebar_items)
                if payload.get("kind") == "playlist"
                and int(payload.get("playlist_index", -1)) == playlist_index
            ),
            -1,
        )
        if row >= 0:
            self.playlist_list.setCurrentRow(row)
            self.on_playlist_selected(row)

    def render_experimental_tracks(
        self,
        tracks: list[RemoteTrack] | list[LocalMusicTrack],
    ) -> None:
        self.search_results_active = False
        self.current_displayed_tracks = list(tracks)
        self.clear_track_results_layout()

        self.remote_track_cards = []
        self.selected_experimental_track_indexes = {
            index
            for index in self.selected_experimental_track_indexes
            if 0 <= index < len(tracks)
        }
        if (
            self.selected_experimental_track_index is None
            or self.selected_experimental_track_index >= len(tracks)
        ):
            self.selected_experimental_track_index = 0 if tracks else None
        if self.selected_experimental_track_index is not None:
            if not self.selected_experimental_track_indexes:
                self.selected_experimental_track_indexes = {
                    self.selected_experimental_track_index
                }
            if self.experimental_selection_anchor_index is None:
                self.experimental_selection_anchor_index = (
                    self.selected_experimental_track_index
                )
        if not tracks:
            self.clear_experimental_track_selection()
            playlist = (
                self.playlists[self.selected_playlist_index]
                if self.selected_playlist_index is not None
                and 0 <= self.selected_playlist_index < len(self.playlists)
                else None
            )

            empty_container = QWidget()
            empty_layout = QVBoxLayout(empty_container)
            empty_layout.setContentsMargins(0, 24, 0, 24)
            empty_layout.setSpacing(12)

            self.playlist_tracks_empty = QLabel("Треки не найдены")
            if self.experimental_source_mode == "all_music":
                self.playlist_tracks_empty.setText("В папке music пока нет mp3-файлов")
            elif self.experimental_source_mode == "author_browser":
                if self.selected_author_name:
                    self.playlist_tracks_empty.setText("Выберите альбом или Синглы")
                else:
                    self.playlist_tracks_empty.setText("Выберите автора")
            elif self.experimental_source_mode == "album_browser":
                self.playlist_tracks_empty.setText("Выберите альбом")
            elif playlist is not None and playlist.is_loading:
                self.playlist_tracks_empty.setText("Подгружаем треки плейлиста...")
            elif playlist is not None:
                self.playlist_tracks_empty.setText(
                    playlist.note or "YouTube не вернул треки для этого плейлиста"
                )
            self.playlist_tracks_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            colors = self.theme_colors()
            self.playlist_tracks_empty.setStyleSheet(
                f"font-size:14px; color:{colors['text_muted']}; background:transparent; border:none;"
            )
            empty_layout.addWidget(
                self.playlist_tracks_empty,
                alignment=Qt.AlignmentFlag.AlignHCenter,
            )

            if playlist is not None and playlist.is_loading:
                progress_bar = QProgressBar()
                progress_bar.setFixedWidth(320)
                progress_bar.setTextVisible(True)
                progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
                progress_bar.setStyleSheet(
                    "QProgressBar {"
                    f"background:{colors['progress_bg']};"
                    f"border:1px solid {colors['progress_border']};"
                    "border-radius:8px;"
                    f"color:{colors['text_primary']};"
                    "height:18px;"
                    "text-align:center;"
                    "}"
                    "QProgressBar::chunk { background:#5f9ee6; border-radius:7px; }"
                )
                if playlist.loading_total > 0:
                    current = min(playlist.loading_current, playlist.loading_total)
                    progress_bar.setRange(0, playlist.loading_total)
                    progress_bar.setValue(current)
                    progress_bar.setFormat(f"{current} / {playlist.loading_total}")
                else:
                    progress_bar.setRange(0, 0)
                    progress_bar.setFormat("Подготовка...")
                empty_layout.addWidget(
                    progress_bar,
                    alignment=Qt.AlignmentFlag.AlignHCenter,
                )

            self.playlist_tracks_layout.addWidget(empty_container)
            self.playlist_tracks_layout.addStretch(1)
            return

        for track_index, track in enumerate(tracks):
            card = RemoteTrackCard(
                track,
                track_index,
                self.status_icons,
                self.metadata_icon,
                self.reveal_icon,
                show_preview=self.should_show_track_previews(),
                display_number=self.get_track_display_number(track, track_index),
                show_artist_album=self.should_show_track_artist_album(),
                compact=self.should_use_compact_track_cards(),
                preview_size=self.track_preview_size(),
            )
            card.apply_theme(self.is_dark_theme())
            card.selected.connect(self.on_remote_track_selected)
            card.context_requested.connect(self.on_remote_track_context_requested)
            card.reveal_requested.connect(self.on_experimental_track_reveal_requested)
            card.delete_requested.connect(self.on_experimental_track_delete_requested)
            card.set_selected(track_index in self.selected_experimental_track_indexes)
            self.remote_track_cards.append(card)
            self.playlist_tracks_layout.addWidget(card)
        self.playlist_tracks_layout.addStretch(1)

    def on_remote_track_selected(self, index: int, modifiers_value: int) -> None:
        modifiers = Qt.KeyboardModifier(modifiers_value)
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.set_range_experimental_track_selection(index)
            return
        self.set_single_experimental_track_selection(index)

    def on_experimental_track_reveal_requested(self, index: int) -> None:
        self.reveal_experimental_track_in_file_manager(index)

    def on_remote_track_context_requested(self, index: int, global_pos) -> None:
        if index not in self.selected_experimental_track_indexes:
            self.set_single_experimental_track_selection(index)

        menu = QMenu(self)
        selected_indexes = self.get_selected_experimental_track_indexes()
        is_single_selection = len(selected_indexes) == 1

        reveal_action = None
        if is_single_selection:
            selected_track = self.get_current_experimental_tracks()[selected_indexes[0]]
            reveal_action = menu.addAction("Открыть расположение")
            reveal_action.setEnabled(bool(self.get_track_file_path(selected_track)))
        add_to_playlist_action = menu.addAction("Добавить в плейлист")
        delete_action = menu.addAction("Удалить")

        selected_action = menu.exec(global_pos)
        if reveal_action is not None and selected_action == reveal_action:
            self.reveal_experimental_track_in_file_manager(selected_indexes[0])
            return
        if selected_action == add_to_playlist_action:
            self.add_selected_tracks_to_manual_playlist()
            return
        if selected_action == delete_action:
            self.delete_selected_experimental_tracks()

    def get_track_file_path(self, track: RemoteTrack | LocalMusicTrack) -> str:
        if isinstance(track, LocalMusicTrack):
            return track.file_path
        return track.local_file_path

    def reveal_experimental_track_in_file_manager(self, index: int) -> None:
        tracks = self.get_current_experimental_tracks()
        if not (0 <= index < len(tracks)):
            return

        file_path = self.get_track_file_path(tracks[index])
        if not file_path or not os.path.exists(file_path):
            QMessageBox.information(
                self,
                "Открыть расположение",
                "Файл трека ещё не найден в папке music.",
            )
            return

        normalized_path = os.path.abspath(file_path)
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", normalized_path], check=False)
            return
        if os.name == "nt":
            subprocess.run(["explorer", f"/select,{normalized_path}"], check=False)
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(normalized_path)))

    def on_experimental_track_delete_requested(self, index: int) -> None:
        if self.experimental_source_mode in {
            "all_music",
            "author_albums",
            "author_collection",
            "album",
            "search_album_tracks",
        }:
            self.delete_track_from_all_music(index)
            return
        if self.experimental_source_mode == "playlist":
            self.delete_track_from_selected_playlist(index)

    def on_experimental_track_metadata_requested(self, index: int) -> None:
        tracks = self.get_current_experimental_tracks()
        if not (0 <= index < len(tracks)):
            return
        self.set_single_experimental_track_selection(index)
        if (
            self.metadata_title_edit.isVisible()
            and self.metadata_title_edit.isEnabled()
        ):
            self.metadata_title_edit.setFocus()
            self.metadata_title_edit.selectAll()
        elif self.metadata_author_edit.isEnabled():
            self.metadata_author_edit.setFocus()
            self.metadata_author_edit.selectAll()

    def relocate_music_file_after_metadata_edit(
        self,
        file_path: str,
        *,
        title: str,
        author: str,
        album: str,
    ) -> str:
        source_path = os.path.realpath(file_path)
        if not os.path.exists(source_path):
            return source_path

        target_path = os.path.realpath(
            build_music_file_path(
                self.music_library_dir,
                title=title,
                artist=author,
                album=album,
                extension=".mp3",
                separator=" - ",
            )
        )
        if source_path == target_path:
            return source_path

        final_target_path = target_path
        if os.path.exists(target_path):
            if os.path.samefile(source_path, target_path):
                return source_path
            final_target_path = ensure_unique_music_file_path(target_path)

        os.makedirs(os.path.dirname(final_target_path), exist_ok=True)
        shutil.move(source_path, final_target_path)
        self.cleanup_empty_music_directories(os.path.dirname(source_path))
        rewrite_track_references_in_playlists(
            self.playlists_dir,
            self.music_library_dir,
            source_path,
            final_target_path,
        )
        return os.path.realpath(final_target_path)

    def cleanup_empty_music_directories(self, start_directory: str) -> None:
        music_root = os.path.realpath(self.music_library_dir)
        current_dir = os.path.realpath(start_directory)
        while (
            current_dir
            and current_dir.startswith(music_root)
            and current_dir != music_root
        ):
            try:
                if os.listdir(current_dir):
                    break
                os.rmdir(current_dir)
            except OSError:
                break
            current_dir = os.path.dirname(current_dir)

    def resolve_metadata_values_for_track(
        self,
        track: RemoteTrack | LocalMusicTrack,
        values: dict[str, str],
    ) -> dict[str, str]:
        return {
            "title": values["title"].strip() or track.title,
            "author": values["author"].strip() or track.artists,
            "group": values["group"].strip() or getattr(track, "group", ""),
            "album": values["album"].strip() or track.album,
        }

    def refresh_experimental_track_sources_after_metadata_edit(
        self, file_path: str | list[str]
    ) -> None:
        file_paths = [file_path] if isinstance(file_path, str) else list(file_path)
        resolved_paths = {
            os.path.realpath(path)
            for path in file_paths
            if path and os.path.exists(path)
        }
        self.refresh_local_music_tracks()
        refreshed_local_map = {
            os.path.realpath(local_track.file_path): local_track
            for local_track in self.local_music_tracks
            if os.path.realpath(local_track.file_path) in resolved_paths
        }

        for playlist_index, playlist in enumerate(self.playlists):
            if playlist.source == "manual":
                self.playlists[playlist_index] = load_manual_playlist(
                    playlist.source_url,
                    self.music_library_dir,
                )
                continue

            if playlist.source != "youtube":
                continue

            changed = False
            for track in playlist.tracks:
                refreshed = (
                    refreshed_local_map.get(os.path.realpath(track.local_file_path))
                    if track.local_file_path
                    else None
                )
                if isinstance(track, RemoteTrack) and refreshed is not None:
                    track.title = refreshed.title
                    track.artists = refreshed.artists
                    track.album = refreshed.album
                    track.thumbnail_data = refreshed.thumbnail_data
                    changed = True
            if changed:
                self.persist_playlist(playlist_index)

        self.refresh_playlist_item_statuses()
        self.refresh_experimental_source_view()
        self.restore_experimental_selection_by_file_paths(resolved_paths)
        self.update_metadata_panel()

    def add_selected_tracks_to_manual_playlist(self) -> None:
        selected_file_paths = self.get_selected_experimental_file_paths()
        if not selected_file_paths:
            QMessageBox.information(
                self,
                "Добавить в плейлист",
                "Среди выбранных треков нет доступных mp3-файлов.",
            )
            return

        manual_playlists = [
            (index, playlist)
            for index, playlist in enumerate(self.playlists)
            if playlist.source == "manual"
        ]
        if not manual_playlists:
            QMessageBox.information(
                self,
                "Добавить в плейлист",
                "Сначала создайте хотя бы один ручной плейлист.",
            )
            return

        playlist_names = [playlist.name for _, playlist in manual_playlists]
        selected_name, accepted = QInputDialog.getItem(
            self,
            "Добавить в плейлист",
            "Выберите плейлист:",
            playlist_names,
            0,
            False,
        )
        if not accepted or not selected_name:
            return

        target_index = next(
            (
                index
                for index, playlist in manual_playlists
                if playlist.name == selected_name
            ),
            None,
        )
        if target_index is None:
            return

        updated_playlist = append_tracks_to_manual_playlist(
            self.playlists[target_index].source_url,
            selected_file_paths,
            self.music_library_dir,
        )
        self.playlists[target_index] = updated_playlist
        self.playlist_item_widgets[target_index].set_title(updated_playlist.name)
        if self.selected_playlist_index == target_index:
            self.on_playlist_selected(target_index)

    def edit_shared_metadata_for_selected_tracks(self) -> None:
        if self.metadata_author_edit.isEnabled():
            self.metadata_author_edit.setFocus()
            self.metadata_author_edit.selectAll()

    def delete_selected_experimental_tracks(self) -> None:
        selected_indexes = self.get_selected_experimental_track_indexes()
        if not selected_indexes:
            return
        if self.experimental_source_mode in {
            "all_music",
            "author_albums",
            "author_collection",
            "album",
            "search_album_tracks",
        }:
            self.delete_tracks_from_all_music(selected_indexes)
            return
        if self.experimental_source_mode == "playlist":
            self.delete_tracks_from_selected_playlist(selected_indexes)

    def delete_track_from_all_music(self, index: int) -> None:
        self.delete_tracks_from_all_music([index])

    def delete_tracks_from_all_music(self, indexes: list[int]) -> None:
        tracks = (
            self.get_sorted_experimental_tracks(self.local_music_tracks)
            if self.experimental_source_mode == "all_music"
            else self.get_current_experimental_tracks()
        )
        selected_tracks = [
            tracks[index] for index in indexes if 0 <= index < len(tracks)
        ]
        if not selected_tracks:
            return
        answer = QMessageBox.question(
            self,
            "Удаление трека",
            (
                f"Удалить {len(selected_tracks)} файл(ов) из папки music?"
                if len(selected_tracks) > 1
                else f"Удалить файл '{os.path.basename(selected_tracks[0].file_path)}' из папки music?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        for track in selected_tracks:
            if os.path.exists(track.file_path):
                os.remove(track.file_path)
        self.refresh_local_music_tracks()
        if self.experimental_source_mode == "author_albums":
            self.clear_experimental_track_selection()
            self.render_author_album_cards(self.selected_author_name or "")
            self.update_metadata_panel()
            return
        if self.experimental_source_mode == "all_music":
            refreshed_tracks = self.get_sorted_experimental_tracks(
                self.local_music_tracks
            )
        else:
            refreshed_tracks = self.get_current_experimental_tracks()
        self.clear_experimental_track_selection()
        if refreshed_tracks:
            next_index = min(min(indexes), len(refreshed_tracks) - 1)
            self.selected_experimental_track_index = next_index
            self.selected_experimental_track_indexes = {next_index}
            self.experimental_selection_anchor_index = next_index
        self.render_experimental_tracks(refreshed_tracks)
        self.update_metadata_panel()

    def delete_track_from_selected_playlist(self, index: int) -> None:
        self.delete_tracks_from_selected_playlist([index])

    def delete_tracks_from_selected_playlist(self, indexes: list[int]) -> None:
        if self.selected_playlist_index is None or not (
            0 <= self.selected_playlist_index < len(self.playlists)
        ):
            return
        playlist = self.playlists[self.selected_playlist_index]
        tracks = self.get_sorted_experimental_tracks(playlist.tracks)
        selected_tracks = [
            tracks[index] for index in indexes if 0 <= index < len(tracks)
        ]
        if not selected_tracks:
            return
        delete_files = self.delete_files_checkbox.isChecked()
        answer = QMessageBox.question(
            self,
            "Удаление трека",
            (
                "Удалить выбранные треки?"
                if len(selected_tracks) > 1
                else "Удалить выбранный трек?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        if playlist.source == "manual":
            file_paths_to_remove = [
                track.file_path
                for track in selected_tracks
                if isinstance(track, LocalMusicTrack)
            ]
            if delete_files:
                for file_path in file_paths_to_remove:
                    if os.path.exists(file_path):
                        os.remove(file_path)
            updated_playlist = playlist
            for file_path in file_paths_to_remove:
                updated_playlist = remove_track_from_manual_playlist(
                    updated_playlist.source_url,
                    file_path,
                    self.music_library_dir,
                )
            self.playlists[self.selected_playlist_index] = updated_playlist
            playlist = updated_playlist
        else:
            file_paths_to_delete = []
            selected_track_ids = {id(track) for track in selected_tracks}
            for track in selected_tracks:
                if isinstance(track, RemoteTrack):
                    if track.local_file_path:
                        file_paths_to_delete.append(track.local_file_path)
                elif track.file_path:
                    file_paths_to_delete.append(track.file_path)
            if delete_files:
                for file_path in file_paths_to_delete:
                    if os.path.exists(file_path):
                        os.remove(file_path)
            playlist.tracks = [
                item for item in playlist.tracks if id(item) not in selected_track_ids
            ]
            self.persist_playlist(self.selected_playlist_index)

        if playlist.source == "manual":
            self.playlist_item_widgets[self.selected_playlist_index].set_title(
                playlist.name
            )
        self.refresh_local_music_tracks()
        refreshed_tracks = self.get_sorted_experimental_tracks(playlist.tracks)
        self.clear_experimental_track_selection()
        if refreshed_tracks:
            next_index = min(min(indexes), len(refreshed_tracks) - 1)
            self.selected_experimental_track_index = next_index
            self.selected_experimental_track_indexes = {next_index}
            self.experimental_selection_anchor_index = next_index
        self.render_experimental_tracks(refreshed_tracks)
        self.update_metadata_panel()
        self.update_start_button_state()

    def select_task(self, index: int | None) -> None:
        self.selected_task_index = (
            index if index is not None and 0 <= index < len(self.tasks) else None
        )
        for card_index, card in enumerate(self.cards):
            card.set_selected(card_index == self.selected_task_index)
        self.update_metadata_panel()

    def update_metadata_panel(self) -> None:
        selected_tracks = self.get_selected_experimental_tracks()
        if self.is_album_metadata_mode():
            album_tracks = self.current_album_collection_tracks()
            if not album_tracks:
                self.apply_album_metadata_panel_state(
                    album_title=self.selected_album_name or "",
                    album_author="",
                    track_title="",
                    track_number=0,
                    track_path="",
                    thumbnail_data=None,
                    album_file_paths=[],
                )
                self.metadata_track_title_edit.setPlaceholderText("Трек не выбран")
                self.metadata_track_number_edit.setPlaceholderText("Номер")
                return

            selected_track = (
                selected_tracks[0]
                if selected_tracks
                else (
                    self.get_current_experimental_tracks()[
                        self.selected_experimental_track_index
                    ]
                    if self.selected_experimental_track_index is not None
                    and 0
                    <= self.selected_experimental_track_index
                    < len(self.get_current_experimental_tracks())
                    else None
                )
            )
            selected_snapshot = (
                self.load_editable_track_snapshot(selected_track)
                if selected_track is not None
                else None
            )
            common_author = self.common_metadata_value(
                [track.artists for track in album_tracks]
            )
            thumbnail_data = next(
                (
                    track.thumbnail_data
                    for track in album_tracks
                    if track.thumbnail_data
                ),
                None,
            )
            self.apply_album_metadata_panel_state(
                album_title=self.selected_album_name
                or self.common_metadata_value([track.album for track in album_tracks]),
                album_author=common_author,
                track_title=selected_snapshot.title
                if selected_snapshot is not None
                else "",
                track_number=(
                    selected_snapshot.track_number
                    if selected_snapshot is not None
                    else 0
                ),
                track_path=(
                    selected_snapshot.file_path if selected_snapshot is not None else ""
                ),
                thumbnail_data=(
                    selected_snapshot.thumbnail_data
                    if selected_snapshot is not None
                    and selected_snapshot.thumbnail_data
                    else thumbnail_data
                ),
                album_file_paths=[track.file_path for track in album_tracks],
            )
            self.metadata_album_title_edit.setPlaceholderText(
                self.selected_album_name or "Название альбома"
            )
            self.metadata_album_author_edit.setPlaceholderText("Автор")
            self.metadata_track_title_edit.setPlaceholderText("Название трека")
            self.metadata_track_number_edit.setPlaceholderText("Номер")
            return

        if not selected_tracks:
            playlist = (
                self.playlists[self.selected_playlist_index]
                if self.selected_playlist_index is not None
                and 0 <= self.selected_playlist_index < len(self.playlists)
                else None
            )
            empty_status = "Нет треков"
            if playlist and playlist.is_loading:
                empty_status = "Подгрузка плейлиста"
            elif playlist and playlist.note:
                empty_status = playlist.note
            self.apply_metadata_panel_state(
                title_visible=True,
                title="",
                source=self.current_collection_label,
                url_value="—",
                author="",
                group="",
                album="",
                status=empty_status,
                thumbnail_data=None,
                editable_file_paths=[],
            )
            self.metadata_title_edit.setPlaceholderText("Трек не выбран")
            self.metadata_author_edit.setPlaceholderText("Автор")
            self.metadata_group_edit.setPlaceholderText("Группа")
            self.metadata_album_edit.setPlaceholderText("Альбом")
            return

        if len(selected_tracks) == 1:
            track = selected_tracks[0]
            snapshot = self.load_editable_track_snapshot(track)
            source_name = (
                self.playlists[self.selected_playlist_index].name
                if self.experimental_source_mode == "playlist"
                and self.selected_playlist_index is not None
                and 0 <= self.selected_playlist_index < len(self.playlists)
                else self.current_collection_label
            )
            url_value = self.get_track_file_path(track) or (
                track.source_url if isinstance(track, RemoteTrack) else track.file_path
            )
            self.apply_metadata_panel_state(
                title_visible=True,
                title=(snapshot.title if snapshot is not None else track.title),
                source=source_name,
                url_value=url_value or "—",
                author=(
                    snapshot.artists
                    if snapshot is not None
                    else getattr(track, "artists", "")
                ),
                group=(
                    snapshot.group
                    if snapshot is not None
                    else getattr(track, "group", "")
                ),
                album=(snapshot.album if snapshot is not None else track.album),
                status=self.get_track_status_title(track),
                thumbnail_data=(
                    snapshot.thumbnail_data
                    if snapshot is not None
                    else track.thumbnail_data
                ),
                editable_file_paths=(
                    [snapshot.file_path] if snapshot is not None else []
                ),
            )
            self.metadata_title_edit.setPlaceholderText(track.title or "Название")
            self.metadata_author_edit.setPlaceholderText(
                getattr(track, "artists", "") or "Автор"
            )
            self.metadata_group_edit.setPlaceholderText("Группа")
            self.metadata_album_edit.setPlaceholderText(track.album or "Альбом")
            return

        snapshots = [
            snapshot
            for snapshot in (
                self.load_editable_track_snapshot(track) for track in selected_tracks
            )
            if snapshot is not None
        ]
        thumbnail_data = next(
            (
                snapshot.thumbnail_data
                for snapshot in snapshots
                if snapshot.thumbnail_data
            ),
            None,
        )
        self.apply_metadata_panel_state(
            title_visible=False,
            title="",
            source=f"Выбрано треков: {len(selected_tracks)}",
            url_value=(
                f"Доступно для редактирования: {len(snapshots)}"
                if snapshots
                else "Нет доступных mp3-файлов"
            ),
            author=self.common_metadata_value(
                [snapshot.artists for snapshot in snapshots]
            ),
            group=self.common_metadata_value(
                [snapshot.group for snapshot in snapshots]
            ),
            album=self.common_metadata_value(
                [snapshot.album for snapshot in snapshots]
            ),
            status=(
                "Общие метаданные выбранных треков"
                if snapshots
                else "Для части выбранных треков mp3 ещё не найден"
            ),
            thumbnail_data=thumbnail_data,
            editable_file_paths=[snapshot.file_path for snapshot in snapshots],
        )
        self.metadata_author_edit.setPlaceholderText("Общий автор")
        self.metadata_group_edit.setPlaceholderText("Общая группа")
        self.metadata_album_edit.setPlaceholderText("Общий альбом")

    def reload_theme_icons(self) -> None:
        self.metadata_icon = QIcon(self.themed_icon_path("metadata_edit"))
        self.cover_pick_icon = QIcon(self.themed_icon_path("cover_pick"))
        self.cover_reset_icon = QIcon(self.themed_icon_path("cover_reset"))
        self.save_icon = self.themed_raster_icon("save", 24)
        self.reset_icon = self.themed_raster_icon("reset", 24)
        self.search_icon = self.themed_raster_icon("search", 16)
        self.select_root_icon = self.cover_pick_icon
        self.open_folder_icon = QIcon(self.themed_icon_path("folder"))
        self.reveal_icon = QIcon(self.themed_icon_path("open_folder"))
        self.gear_icon = QIcon(self.themed_icon_path("gear"))
        self.add_playlist_icon = QIcon(self.themed_icon_path("add_playlist"))
        self.add_track_icon = self.themed_raster_icon("track", 20)
        self.add_list_icon = self.themed_raster_icon("list", 20)
        self.library_playlist_icon = self.themed_raster_icon("playlist", 24)
        self.library_author_icon = self.themed_raster_icon("author", 24)
        self.library_album_icon = self.themed_raster_icon("album", 24)
        self.back_icon = QIcon()
        self.new_track_icon = self.add_playlist_icon
        self.choose_folder_icon = QIcon(self.themed_icon_path("pen"))
        self.import_icon = QIcon(self.themed_icon_path("file"))
        self.start_icon = QIcon(self.themed_icon_path("mass_download"))
        self.home_icon = QIcon(self.themed_icon_path("home"))
        self.delete_icon = QIcon(self.themed_icon_path("delete"))
        self.sort_date_icon = QIcon(self.themed_icon_path("number"))
        self.sort_title_icon = QIcon(self.themed_icon_path("by_name"))
        self.status_icons = {
            STATUS_PENDING: QIcon(self.themed_icon_path("to_download")),
            STATUS_META_LOADING: QIcon(self.themed_icon_path("downloading")),
            STATUS_DOWNLOADING: QIcon(self.themed_icon_path("downloading")),
            STATUS_DONE: QIcon(self.themed_icon_path("downloaded")),
            STATUS_ERROR: QIcon(self.themed_icon_path("to_download")),
            STATUS_SKIPPED: QIcon(self.themed_icon_path("to_download")),
        }
        self.playlist_loading_icon = self.status_icons[STATUS_META_LOADING]
        self.playlist_ready_icon = self.status_icons[STATUS_PENDING]
        if hasattr(self, "select_elenveil_root_button"):
            self.select_elenveil_root_button.setIcon(self.select_root_icon)
            self.select_elenveil_root_button.setIconSize(QSize(18, 18))
        if hasattr(self, "open_music_folder_button"):
            self.open_music_folder_button.setIcon(self.open_folder_icon)
            self.open_music_folder_button.setIconSize(QSize(18, 18))
        if hasattr(self, "create_playlist_button"):
            self.create_playlist_button.setIcon(self.add_playlist_icon)
            self.create_playlist_button.setIconSize(QSize(18, 18))
        if hasattr(self, "add_track_action"):
            self.add_track_action.setIcon(self.add_track_icon)
        if hasattr(self, "add_list_action"):
            self.add_list_action.setIcon(self.add_list_icon)
        if hasattr(self, "add_playlist_action"):
            self.add_playlist_action.setIcon(self.library_playlist_icon)
        if hasattr(self, "track_search_tracks_action"):
            self.track_search_tracks_action.setIcon(self.add_track_icon)
        if hasattr(self, "track_search_albums_action"):
            self.track_search_albums_action.setIcon(self.library_album_icon)
        if hasattr(self, "track_search_authors_action"):
            self.track_search_authors_action.setIcon(self.library_author_icon)
        if hasattr(self, "track_search_playlists_action"):
            self.track_search_playlists_action.setIcon(self.library_playlist_icon)
        if hasattr(self, "library_view_button"):
            self.update_library_view_icon()
        if hasattr(self, "library_playlist_action"):
            self.library_playlist_action.setIcon(self.library_playlist_icon)
        if hasattr(self, "library_authors_action"):
            self.library_authors_action.setIcon(self.library_author_icon)
        if hasattr(self, "library_albums_action"):
            self.library_albums_action.setIcon(self.library_album_icon)
        if hasattr(self, "library_back_button"):
            self.library_back_button.set_dark_theme(self.is_dark_theme())
        if hasattr(self, "new_track_button"):
            self.new_track_button.setIcon(self.new_track_icon)
            self.new_track_button.setIconSize(QSize(18, 18))
        if hasattr(self, "home_button"):
            self.home_button.setIcon(self.home_icon)
            self.home_button.setIconSize(QSize(18, 18))
        if hasattr(self, "settings_button"):
            self.settings_button.setIcon(self.gear_icon)
            self.settings_button.setIconSize(QSize(18, 18))
        if hasattr(self, "import_button"):
            self.import_button.setIcon(self.import_icon)
            self.import_button.setIconSize(QSize(18, 18))
        if hasattr(self, "start_button"):
            self.start_button.setIcon(self.start_icon)
            self.start_button.setIconSize(QSize(18, 18))
        if hasattr(self, "metadata_pick_cover_button"):
            self.metadata_pick_cover_button.setIcon(self.cover_pick_icon)
            self.metadata_pick_cover_button.setIconSize(QSize(18, 18))
        if hasattr(self, "metadata_clear_cover_button"):
            self.metadata_clear_cover_button.setIcon(self.cover_reset_icon)
            self.metadata_clear_cover_button.setIconSize(QSize(18, 18))
        if hasattr(self, "metadata_cover_label"):
            self.metadata_cover_label.set_overlay_icons(
                self.cover_pick_icon,
                self.cover_reset_icon,
            )
        for button in [
            getattr(self, "metadata_album_title_clear_button", None),
            getattr(self, "metadata_album_author_clear_button", None),
            getattr(self, "metadata_author_clear_button", None),
            getattr(self, "metadata_group_clear_button", None),
            getattr(self, "metadata_album_clear_button", None),
        ]:
            if button is not None:
                button.setIcon(self.delete_icon)
                button.setIconSize(QSize(14, 14))
        for button in [
            getattr(self, "metadata_save_button", None),
            getattr(self, "metadata_album_save_button", None),
            getattr(self, "metadata_track_save_button", None),
        ]:
            if button is not None:
                button.setIcon(self.save_icon)
                button.setIconSize(QSize(18, 18))
        for button in [
            getattr(self, "metadata_cancel_button", None),
            getattr(self, "metadata_album_cancel_button", None),
            getattr(self, "metadata_track_cancel_button", None),
        ]:
            if button is not None:
                button.setIcon(self.reset_icon)
                button.setIconSize(QSize(18, 18))
        if hasattr(self, "sort_date_button"):
            self.sort_date_button.setIcon(self.sort_date_icon)
            self.sort_date_button.setIconSize(QSize(18, 18))
        if hasattr(self, "sort_title_button"):
            self.sort_title_button.setIcon(self.sort_title_icon)
            self.sort_title_button.setIconSize(QSize(18, 18))
        if hasattr(self, "track_search_icon_label"):
            self.track_search_icon_label.setPixmap(
                self.search_icon.pixmap(QSize(16, 16))
            )
            self.position_track_search_icon()
        for widget in self.playlist_item_widgets:
            widget.set_loading_icon(self.playlist_loading_icon)
            widget.set_reveal_icon(self.reveal_icon)
        if hasattr(self, "playlist_item_widgets") and hasattr(self, "sidebar_items"):
            self.refresh_playlist_item_statuses()
        for card in self.cards:
            card.set_metadata_icon(self.metadata_icon)
            card.set_status_icons(self.status_icons)
        for card in self.remote_track_cards:
            card.set_status_icons(self.status_icons)
            card.set_reveal_icon(self.reveal_icon)
        for card in self.download_queue_cards:
            card.set_status_icons(self.status_icons)

    def on_single_download_started(self, index: int) -> None:
        del index
        if self.single_download_task is None:
            return
        self.single_download_task.status = STATUS_DOWNLOADING
        self.single_download_task.progress = 0.0
        self.refresh_open_downloads_popup()

    def on_single_download_progress(self, index: int, percent: float) -> None:
        del index
        if self.single_download_task is None:
            return
        self.single_download_task.progress = percent
        self.refresh_open_downloads_popup()

    def on_single_track_download_finished(
        self, index: int, success: bool, error_text: str
    ) -> None:
        del index
        if self.single_download_task is not None:
            self.single_download_task.status = STATUS_DONE if success else STATUS_ERROR
            self.single_download_task.progress = (
                100.0 if success else self.single_download_task.progress
            )
            self.single_download_task.error = error_text
            if success:
                self.single_download_task = None
            self.refresh_open_downloads_popup()
        if success:
            self.refresh_local_music_tracks()
            self.refresh_experimental_source_view()
            self.update_metadata_panel()
            return
        QMessageBox.warning(
            self,
            "Новый трек",
            error_text or "Не удалось сохранить mp3 в папку music.",
        )

    def on_sliced_track_download_finished(self, success: bool, error_text: str) -> None:
        if success:
            self.refresh_local_music_tracks()
            self.refresh_experimental_source_view()
            self.update_metadata_panel()
            return
        QMessageBox.warning(
            self,
            "Нарезка",
            error_text or "Не удалось сохранить фрагменты в папку music.",
        )

    def on_single_track_download_thread_finished(self) -> None:
        self.download_thread = None
        self.download_worker = None
        self.new_track_button.setEnabled(True)
        self.import_button.setEnabled(True)
        self.update_start_button_state()
        self.refresh_open_downloads_popup()

    def choose_ffmpeg_directory(self) -> bool:
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Выберите директорию с ffmpeg и ffprobe",
            self.ffmpeg_location or "",
        )
        if not selected_dir:
            return False

        if not self.validate_ffmpeg_directory(selected_dir):
            QMessageBox.warning(
                self,
                "FFmpeg не найден",
                "В выбранной директории ffmpeg/ffprobe не найдены или недоступны для запуска.",
            )
            self.update_ffmpeg_status(False)
            return False

        self.ffmpeg_location = selected_dir
        self.ffmpeg_auto_found = False
        self.update_ffmpeg_status(True)
        return True

    def detect_default_ffmpeg_directory(self) -> str:
        preferred_dirs = ["/opt/homebrew/bin", "/opt/local/bin"]
        for candidate_dir in preferred_dirs:
            if self.validate_ffmpeg_directory(candidate_dir):
                return candidate_dir

        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")
        if ffmpeg_path and ffprobe_path:
            candidate_dir = os.path.dirname(ffmpeg_path)
            if self.validate_ffmpeg_directory(candidate_dir):
                return candidate_dir

        known_dirs = [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/opt/local/bin",
            "/usr/bin",
        ]
        for candidate_dir in known_dirs:
            if self.validate_ffmpeg_directory(candidate_dir):
                return candidate_dir
        return ""

    def validate_ffmpeg_directory(self, directory: str) -> bool:
        ffmpeg_path = os.path.join(directory, "ffmpeg")
        ffprobe_path = os.path.join(directory, "ffprobe")
        if not (
            os.path.isfile(ffmpeg_path)
            and os.path.isfile(ffprobe_path)
            and os.access(ffmpeg_path, os.X_OK)
            and os.access(ffprobe_path, os.X_OK)
        ):
            return False

        env = os.environ.copy()
        path = env.get("PATH", "")
        env["PATH"] = f"{directory}:{path}" if path else directory
        ffmpeg_check = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        ffprobe_check = subprocess.run(
            [ffprobe_path, "-version"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        return ffmpeg_check.returncode == 0 and ffprobe_check.returncode == 0

    def ensure_ffmpeg_available(self) -> None:
        detected = self.detect_default_ffmpeg_directory()
        if detected:
            self.ffmpeg_location = detected
            self.ffmpeg_auto_found = True
            self.update_ffmpeg_status(True)
            return
        self.update_ffmpeg_status(False)
        self.show_ffmpeg_setup_dialog()

    def update_ffmpeg_status(self, is_found: bool) -> None:
        if is_found:
            self.ffmpeg_status_label.setText("FFmpeg найден ✅")
            self.ffmpeg_status_label.setStyleSheet("color:#77d88d; font-size:12px;")
        else:
            self.ffmpeg_status_label.setText("FFmpeg не найден ❌")
            self.ffmpeg_status_label.setStyleSheet("color:#ff8f8f; font-size:12px;")

    def show_ffmpeg_setup_dialog(self) -> None:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("FFmpeg не найден")
        message.setText(
            "Приложение не нашло ffmpeg и ffprobe в путях по умолчанию.\n"
            "Выберите один из вариантов установки/настройки."
        )
        manual_button = message.addButton(
            "Выбрать вручную", QMessageBox.ButtonRole.ActionRole
        )
        brew_button = None
        port_button = None
        if shutil.which("brew"):
            brew_button = message.addButton(
                "Установить через brew", QMessageBox.ButtonRole.ActionRole
            )
        if shutil.which("port"):
            port_button = message.addButton(
                "Установить через ports", QMessageBox.ButtonRole.ActionRole
            )
        message.addButton(QMessageBox.StandardButton.Cancel)
        message.exec()

        clicked = message.clickedButton()
        if clicked == manual_button:
            self.choose_ffmpeg_directory()
            return
        if brew_button is not None and clicked == brew_button:
            self.install_ffmpeg_with_package_manager("brew")
            return
        if port_button is not None and clicked == port_button:
            self.install_ffmpeg_with_package_manager("ports")

    def install_ffmpeg_with_package_manager(self, manager: str) -> None:
        if manager == "brew":
            command = ["brew", "install", "ffmpeg"]
            fallback = "brew install ffmpeg"
        else:
            command = ["port", "install", "ffmpeg"]
            fallback = "sudo port install ffmpeg"

        result = subprocess.run(command, capture_output=True, text=True, check=False)
        detected = self.detect_default_ffmpeg_directory()
        if result.returncode == 0 and detected:
            self.ffmpeg_location = detected
            self.ffmpeg_auto_found = True
            self.update_ffmpeg_status(True)
            QMessageBox.information(self, "FFmpeg установлен", f"Найдено: {detected}")
            return

        error_tail = (result.stderr or result.stdout or "").strip()
        if len(error_tail) > 500:
            error_tail = error_tail[-500:]
        QMessageBox.warning(
            self,
            "Не удалось установить FFmpeg",
            "Автоустановка завершилась с ошибкой.\n"
            f"Попробуйте выполнить вручную:\n{fallback}\n\n"
            f"Детали:\n{error_tail or 'Нет вывода команды'}",
        )

    def import_links(self) -> None:
        self.import_links_for_experimental_mode()

    def import_links_for_experimental_mode(self) -> None:
        txt_file, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите .txt файл со ссылками",
            "",
            "Text files (*.txt)",
        )
        if not txt_file:
            return

        try:
            with open(txt_file, "r", encoding="utf-8") as source:
                links = [line.strip() for line in source if line.strip()]
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать файл:\n{exc}")
            return

        if not links:
            QMessageBox.information(self, "Пустой файл", "Ссылки не найдены.")
            return

        dialog = ExperimentalImportDialog(
            self,
            links,
            self.music_library_dir,
            self.ffmpeg_location,
            self.metadata_icon,
            self.cover_pick_icon,
            self.cover_reset_icon,
            self.status_icons,
            self.current_ytdlp_auth_options(),
        )
        dialog.downloads_completed.connect(self.on_experimental_import_completed)
        dialog.exec()

    def on_experimental_import_completed(self) -> None:
        self.refresh_local_music_tracks()
        self.refresh_experimental_source_view()
        self.update_metadata_panel()

    def add_new_track_for_experimental_mode(self) -> None:
        if any(
            thread is not None
            for thread in (
                self.metadata_thread,
                self.download_thread,
                self.youtube_thread,
                self.youtube_download_thread,
            )
        ):
            QMessageBox.information(
                self,
                "Новый трек",
                "Дождитесь завершения текущей обработки.",
            )
            return

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Новый трек")
        dialog.setLabelText("Вставьте ссылку на трек:")
        dialog.setTextEchoMode(QLineEdit.EchoMode.Normal)
        self.style_input_dialog(dialog)
        dialog.resize(760, dialog.sizeHint().height())
        dialog.setMinimumWidth(760)
        ok = dialog.exec()
        link = dialog.textValue().strip()
        if not ok or not link:
            return

        task = self.fetch_metadata_for_single_track(link)
        if task is None:
            return

        metadata_dialog = MetadataDialog(
            self,
            task,
            self.cover_pick_icon,
            self.cover_reset_icon,
            allow_slicing=True,
        )
        dialog_result = metadata_dialog.exec()
        if dialog_result == MetadataDialog.SLICE_REQUESTED:
            self.start_track_slicing_flow(task, metadata_dialog)
            return
        if dialog_result != QDialog.DialogCode.Accepted:
            return

        values, cover_path, cover_mode = metadata_dialog.get_metadata_values()
        if not values["url"]:
            QMessageBox.warning(self, "Новый трек", "Ссылка не может быть пустой.")
            return

        task.url = values["url"]
        task.meta_title = values["title"]
        task.meta_author = values["author"]
        task.meta_group = values["group"]
        task.meta_album = values["album"]
        if cover_mode == "custom":
            task.meta_cover_path = cover_path
        elif cover_mode == "clear":
            task.meta_cover_path = ""

        self.download_single_track_to_music(task)

    def start_track_slicing_flow(
        self,
        source_task: DownloadTask,
        metadata_dialog: MetadataDialog,
    ) -> None:
        base_values, base_cover_path, base_cover_mode = (
            metadata_dialog.get_metadata_values()
        )
        if not base_values["url"]:
            QMessageBox.warning(self, "Нарезка", "Ссылка не может быть пустой.")
            return

        slice_dialog = SliceSegmentsDialog(self)
        if slice_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        segment_payloads: list[dict[str, object]] = []
        for index, (start_value, end_value) in enumerate(
            slice_dialog.get_segments(), start=1
        ):
            segment_task = DownloadTask(
                url=base_values["url"],
                title=source_task.title,
                channel=source_task.channel,
                status=STATUS_PENDING,
                thumbnail_data=source_task.thumbnail_data,
                meta_title="",
                meta_author=base_values["author"],
                meta_group=base_values["group"],
                meta_album=base_values["album"],
                meta_cover_path=(
                    base_cover_path
                    if base_cover_mode == "custom" and base_cover_path
                    else ""
                ),
            )
            segment_dialog = MetadataDialog(
                self,
                segment_task,
                self.cover_pick_icon,
                self.cover_reset_icon,
                initial_title="",
            )
            if segment_dialog.exec() != QDialog.DialogCode.Accepted:
                return

            values, cover_path, cover_mode = segment_dialog.get_metadata_values()
            if not values["title"]:
                QMessageBox.warning(
                    self,
                    "Нарезка",
                    f"Укажите название для фрагмента {index}.",
                )
                return
            segment_payloads.append(
                {
                    "start": start_value,
                    "end": end_value,
                    "title": values["title"],
                    "artist": values["author"],
                    "group": values["group"],
                    "album": values["album"],
                    "cover_path": cover_path,
                    "cover_mode": cover_mode,
                }
            )

        if not segment_payloads:
            return

        self.download_sliced_track_to_music(
            base_values["url"],
            source_task.thumbnail_data,
            segment_payloads,
        )

    def fetch_metadata_for_single_track(self, url: str) -> DownloadTask | None:
        task = DownloadTask(url=url)
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        options.update(self.current_ytdlp_auth_options())
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
            task.title = info.get("title") or url
            task.channel = (
                info.get("channel")
                or info.get("uploader")
                or info.get("uploader_id")
                or "Неизвестный канал"
            )
            thumbnail_url = info.get("thumbnail")
            if thumbnail_url:
                try:
                    with urllib.request.urlopen(thumbnail_url, timeout=15) as response:
                        task.thumbnail_data = response.read()
                except Exception:
                    task.thumbnail_data = None
            task.meta_title = (info.get("track") or info.get("title") or "").strip()
            task.meta_author = (
                info.get("artist") or info.get("uploader") or info.get("channel") or ""
            ).strip()
            task.meta_group = (info.get("album_artist") or "").strip()
            task.meta_album = (info.get("album") or "").strip()
            task.status = STATUS_PENDING
            return task
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Новый трек",
                f"Не удалось получить метаданные по ссылке:\n{exc}",
            )
            return None

    def download_single_track_to_music(self, task: DownloadTask) -> None:
        self.ensure_elenveil_directories()
        output_template = build_music_output_template(
            self.music_library_dir,
            title=task.meta_title or task.title,
            artist=task.meta_author,
            album=task.meta_album,
            separator=" - ",
        )
        metadata_overrides = {
            "title": task.meta_title,
            "artist": task.meta_author,
            "album_artist": task.meta_group,
            "album": task.meta_album,
        }

        worker = DownloadWorker(
            0,
            task.url,
            self.music_library_dir,
            metadata_overrides,
            task.meta_cover_path,
            self.ffmpeg_location,
            output_template=output_template,
            ytdlp_options=self.current_ytdlp_auth_options(),
        )
        thread = QThread(self)
        self.download_worker = worker
        self.download_thread = thread
        self.single_download_task = task
        task.status = STATUS_PENDING
        task.progress = 0.0
        self.new_track_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.start_button.setEnabled(False)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.started.connect(self.on_single_download_started)
        worker.progress_changed.connect(self.on_single_download_progress)
        worker.finished.connect(self.on_single_track_download_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_single_track_download_thread_finished)
        self.refresh_open_downloads_popup()
        thread.start()

    def download_sliced_track_to_music(
        self,
        source_url: str,
        thumbnail_data: bytes | None,
        segment_payloads: list[dict[str, object]],
    ) -> None:
        self.ensure_elenveil_directories()
        worker = SlicedTrackDownloadWorker(
            source_url,
            self.music_library_dir,
            segment_payloads,
            thumbnail_data,
            self.ffmpeg_location,
            self.current_ytdlp_auth_options(),
        )
        thread = QThread(self)
        self.download_worker = worker
        self.download_thread = thread
        self.new_track_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.start_button.setEnabled(False)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.on_sliced_track_download_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_single_track_download_thread_finished)
        thread.start()

    def add_link_from_dialog(self) -> None:
        if self.metadata_thread is not None:
            QMessageBox.information(
                self, "Добавить", "Дождитесь завершения подгрузки метаданных."
            )
            return

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Добавить ссылку")
        dialog.setLabelText("Вставьте ссылку для загрузки:")
        dialog.setTextEchoMode(QLineEdit.EchoMode.Normal)
        self.style_input_dialog(dialog)
        dialog.resize(760, dialog.sizeHint().height())
        dialog.setMinimumWidth(760)
        ok = dialog.exec()
        link = dialog.textValue().strip()
        if not ok or not link:
            return

        self.enqueue_links([link])

    def enqueue_links(self, links: list[str]) -> None:
        start_index = len(self.tasks)
        index_url_pairs: list[tuple[int, str]] = []
        for offset, link in enumerate(links):
            task = DownloadTask(url=link)
            self.tasks.append(task)
            card = DownloadCard(
                task, start_index + offset, self.metadata_icon, self.status_icons
            )
            card.apply_theme(self.is_dark_theme())
            card.metadata_requested.connect(self.on_card_metadata_requested)
            card.delete_requested.connect(self.on_card_delete_requested)
            card.selected.connect(self.on_card_selected)
            self.cards.append(card)
            insert_pos = max(0, self.cards_layout.count() - 1)
            self.cards_layout.insertWidget(insert_pos, card)
            index_url_pairs.append((start_index + offset, link))

        self.start_button.setEnabled(False)
        self.import_button.setEnabled(False)
        if self.selected_task_index is None and self.tasks:
            self.select_task(0)
        elif self.tasks:
            self.select_task(start_index)
        self.refresh_open_downloads_popup()
        self.start_metadata_load(index_url_pairs)

    def start_metadata_load(self, index_url_pairs: list[tuple[int, str]]) -> None:
        worker = MetadataWorker(index_url_pairs, self.current_ytdlp_auth_options())
        thread = QThread(self)
        self.metadata_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.metadata_ready.connect(self.on_metadata_ready)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_metadata_finished)
        self.metadata_thread = thread
        thread.start()

    def on_metadata_ready(
        self,
        index: int,
        title: str,
        channel: str,
        thumbnail_data: bytes | None,
        error_text: str,
        extracted_meta: dict[str, str],
    ) -> None:
        task = self.tasks[index]
        task.title = title
        task.channel = channel
        task.thumbnail_data = thumbnail_data
        task.status = STATUS_PENDING
        task.error = error_text
        task.meta_title = (
            task.meta_title or extracted_meta.get("title") or title
        ).strip()
        task.meta_author = (
            task.meta_author or extracted_meta.get("author") or channel
        ).strip()
        task.meta_group = (task.meta_group or extracted_meta.get("group") or "").strip()
        task.meta_album = (task.meta_album or extracted_meta.get("album") or "").strip()
        self.refresh_card(index)
        self.refresh_open_downloads_popup()
        if self.selected_task_index == index:
            self.update_metadata_panel()

    def on_metadata_finished(self) -> None:
        self.metadata_thread = None
        self.metadata_worker = None
        self.import_button.setEnabled(True)
        self.start_button.setEnabled(
            any(task.status == STATUS_PENDING for task in self.tasks)
        )
        self.refresh_open_downloads_popup()

    def on_card_selected(self, index: int) -> None:
        self.select_task(index)

    def on_card_metadata_requested(self, index: int) -> None:
        if self.metadata_thread is not None or self.download_thread is not None:
            QMessageBox.information(
                self,
                "Изменение метаданных недоступно",
                "Дождитесь завершения текущей обработки.",
            )
            return
        if index < 0 or index >= len(self.tasks):
            return

        task = self.tasks[index]
        dialog = MetadataDialog(self, task, self.cover_pick_icon, self.cover_reset_icon)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values, cover_path, cover_mode = dialog.get_metadata_values()
        new_url = values["url"]
        if not new_url:
            QMessageBox.warning(
                self, "Некорректная ссылка", "Ссылка не может быть пустой."
            )
            return

        task.meta_title = values["title"]
        task.meta_author = values["author"]
        task.meta_group = values["group"]
        task.meta_album = values["album"]
        if cover_mode == "custom":
            task.meta_cover_path = cover_path
        elif cover_mode == "clear":
            task.meta_cover_path = ""

        if new_url != task.url:
            task.url = new_url
            task.title = "Загрузка метаданных..."
            task.channel = ""
            task.status = STATUS_META_LOADING
            task.progress = 0.0
            task.error = ""
            task.thumbnail_data = None
            task.meta_title = ""
            task.meta_author = ""
            task.meta_group = ""
            task.meta_album = ""
            task.meta_cover_path = ""
            self.refresh_card(index)
            if self.selected_task_index == index:
                self.update_metadata_panel()
            self.start_button.setEnabled(False)
            self.import_button.setEnabled(False)
            self.start_metadata_load([(index, new_url)])
            return

        if self.selected_task_index == index:
            self.update_metadata_panel()

    def on_card_delete_requested(self, index: int) -> None:
        if self.metadata_thread is not None or self.download_thread is not None:
            QMessageBox.information(
                self,
                "Удаление недоступно",
                "Дождитесь завершения текущей обработки.",
            )
            return
        if index < 0 or index >= len(self.tasks):
            return

        answer = QMessageBox.question(
            self,
            "Удаление ссылки",
            "Удалить ссылку из списка загрузок?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.tasks.pop(index)
        card = self.cards.pop(index)
        self.cards_layout.removeWidget(card)
        card.deleteLater()
        self.renumber_cards()
        if self.selected_task_index is None:
            self.update_metadata_panel()
        elif not self.tasks:
            self.select_task(None)
        elif self.selected_task_index == index:
            self.select_task(min(index, len(self.tasks) - 1))
        elif self.selected_task_index > index:
            self.select_task(self.selected_task_index - 1)
        self.start_button.setEnabled(
            any(task.status == STATUS_PENDING for task in self.tasks)
        )
        self.refresh_open_downloads_popup()

    def renumber_cards(self) -> None:
        for index, card in enumerate(self.cards):
            card.set_list_index(index)

    def start_downloads(self) -> None:
        self.start_playlist_track_downloads()

    def start_playlist_track_downloads(self) -> None:
        if self.youtube_thread is not None:
            QMessageBox.information(
                self, "Старт", "Дождитесь завершения импорта плейлиста."
            )
            return
        if self.youtube_download_thread is not None:
            QMessageBox.information(
                self, "Старт", "Загрузка треков плейлиста уже выполняется."
            )
            return
        if (
            self.experimental_source_mode != "playlist"
            or self.selected_playlist_index is None
        ):
            QMessageBox.information(self, "Старт", "Выберите плейлист в левой панели.")
            return

        playlist = self.playlists[self.selected_playlist_index]
        if playlist.source == "youtube":
            self.start_youtube_track_downloads(playlist)
            return
        QMessageBox.information(
            self,
            "Старт",
            "Сейчас загрузка доступна только для YouTube-плейлистов.",
        )

    def start_youtube_track_downloads(self, playlist: PlaylistEntry) -> None:
        if playlist.source != "youtube":
            return
        if playlist.is_loading:
            QMessageBox.information(self, "Старт", "Плейлист ещё подгружается.")
            return
        if not playlist.tracks:
            QMessageBox.information(
                self, "Старт", "В выбранном плейлисте нет треков для загрузки."
            )
            return

        downloadable_indexes = [
            index
            for index, track in enumerate(playlist.tracks)
            if track.status in (STATUS_PENDING, STATUS_ERROR, STATUS_SKIPPED)
        ]
        if not downloadable_indexes:
            QMessageBox.information(
                self, "Старт", "Нет YouTube-треков, ожидающих загрузку."
            )
            return

        self.ensure_elenveil_directories()
        self.start_button.setEnabled(False)
        self.create_playlist_button.setEnabled(False)
        self.active_remote_playlist_index = self.selected_playlist_index
        self.active_youtube_download_queue = list(downloadable_indexes)
        playlist.is_downloading = True
        self.playlist_item_widgets[self.selected_playlist_index].set_loading(True)
        self.refresh_open_downloads_popup()

        worker = YouTubePlaylistDownloadWorker(
            [
                (
                    index,
                    playlist.tracks[index].source_url,
                    playlist.tracks[index].title,
                    playlist.tracks[index].artists,
                    playlist.tracks[index].album,
                )
                for index in downloadable_indexes
            ],
            self.music_library_dir,
            self.ffmpeg_location,
            self.current_ytdlp_auth_options(),
        )
        thread = QThread(self)
        self.youtube_download_worker = worker
        self.youtube_download_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.track_started.connect(self.on_remote_track_download_started)
        worker.progress_changed.connect(self.on_remote_track_download_progress)
        worker.track_finished.connect(self.on_remote_track_download_finished)
        worker.failed.connect(self.on_youtube_track_download_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_youtube_track_downloads_finished)
        thread.start()

    def on_remote_track_download_started(self, track_index: int) -> None:
        if self.active_remote_playlist_index is None:
            return
        playlist = self.playlists[self.active_remote_playlist_index]
        if not (0 <= track_index < len(playlist.tracks)):
            return
        track = playlist.tracks[track_index]
        track.status = STATUS_DOWNLOADING
        track.progress = 0.0
        track.error = ""
        self.persist_playlist(self.active_remote_playlist_index)
        self.update_playlist_item_status(self.active_remote_playlist_index)
        self.refresh_experimental_source_view()
        self.update_start_button_state()
        self.refresh_open_downloads_popup()

    def on_remote_track_download_progress(
        self, track_index: int, percent: float
    ) -> None:
        if self.active_remote_playlist_index is None:
            return
        playlist = self.playlists[self.active_remote_playlist_index]
        if not (0 <= track_index < len(playlist.tracks)):
            return
        track = playlist.tracks[track_index]
        track.progress = percent
        self.persist_playlist(self.active_remote_playlist_index)
        self.refresh_visible_remote_track_card(self.active_remote_playlist_index, track)
        if self.selected_playlist_index == self.active_remote_playlist_index:
            self.update_metadata_panel()
        self.refresh_open_downloads_popup()

    def on_remote_track_download_finished(
        self,
        track_index: int,
        status: str,
        local_file_path: str,
        error_text: str,
    ) -> None:
        if self.active_remote_playlist_index is None:
            return
        playlist = self.playlists[self.active_remote_playlist_index]
        if not (0 <= track_index < len(playlist.tracks)):
            return
        track = playlist.tracks[track_index]
        track.status = status
        track.progress = 100.0 if status == STATUS_DONE else 0.0
        track.local_file_path = local_file_path
        track.error = error_text
        self.persist_playlist(self.active_remote_playlist_index)
        self.update_playlist_item_status(self.active_remote_playlist_index)
        self.refresh_visible_remote_track_card(self.active_remote_playlist_index, track)
        self.update_start_button_state()
        self.refresh_open_downloads_popup()

    def on_youtube_track_download_failed(self, error_text: str) -> None:
        QMessageBox.warning(
            self,
            "YouTube",
            error_text or "Не удалось запустить загрузку YouTube-треков.",
        )
        self.update_start_button_state()

    def on_youtube_track_downloads_finished(self) -> None:
        summary_playlist = None
        completed_playlist_index = self.active_remote_playlist_index
        if (
            self.active_remote_playlist_index is not None
            and 0 <= self.active_remote_playlist_index < len(self.playlists)
        ):
            summary_playlist = self.playlists[self.active_remote_playlist_index]
            summary_playlist.is_downloading = False
            self.update_playlist_item_status(self.active_remote_playlist_index)
            self.persist_playlist(self.active_remote_playlist_index)
            try:
                self.export_remote_playlist_m3u8(summary_playlist)
            except Exception as error:
                QMessageBox.warning(
                    self,
                    "Плейлист",
                    f"Не удалось обновить .m3u8 для плейлиста '{summary_playlist.name}'.\n\n{error}",
                )
        self.youtube_download_thread = None
        self.youtube_download_worker = None
        self.active_remote_playlist_index = None
        self.active_youtube_download_queue = []
        self.create_playlist_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.refresh_local_music_tracks()
        if completed_playlist_index is not None:
            converted = self.convert_downloaded_youtube_playlist_to_manual(
                completed_playlist_index
            )
            if converted:
                self.rebuild_playlist_list()
                if completed_playlist_index < len(self.playlists):
                    self.selected_playlist_index = completed_playlist_index
                    self.playlist_list.setCurrentRow(completed_playlist_index)
            elif 0 <= completed_playlist_index < len(self.playlist_item_widgets):
                self.update_playlist_item_status(completed_playlist_index)
        self.refresh_experimental_source_view()
        self.update_start_button_state()
        self.refresh_open_downloads_popup()
        if (
            completed_playlist_index is not None
            and self.selected_playlist_index == completed_playlist_index
        ):
            self.update_metadata_panel()
        if summary_playlist is not None:
            downloaded = sum(
                1 for track in summary_playlist.tracks if track.status == STATUS_DONE
            )
            skipped = sum(
                1 for track in summary_playlist.tracks if track.status == STATUS_SKIPPED
            )
            failed = sum(
                1 for track in summary_playlist.tracks if track.status == STATUS_ERROR
            )
            if skipped or failed:
                QMessageBox.information(
                    self,
                    "YouTube",
                    f"Загрузка плейлиста завершена.\n\n"
                    f"Загружено: {downloaded}\n"
                    f"Пропущено: {skipped}\n"
                    f"Ошибок: {failed}",
                )

    def start_next_download(self) -> None:
        next_index = next(
            (
                index
                for index, task in enumerate(self.tasks)
                if task.status == STATUS_PENDING
            ),
            None,
        )
        if next_index is None:
            self.active_download_index = None
            self.download_thread = None
            self.start_button.setEnabled(
                any(task.status == STATUS_PENDING for task in self.tasks)
            )
            self.refresh_open_downloads_popup()
            return

        task = self.tasks[next_index]
        metadata_overrides = {
            "title": task.meta_title,
            "artist": task.meta_author,
            "album_artist": task.meta_group,
            "album": task.meta_album,
        }
        output_template = build_music_output_template(
            self.output_dir,
            title=task.meta_title or task.title,
            artist=task.meta_author,
            album=task.meta_album,
            separator=" - ",
        )
        worker = DownloadWorker(
            next_index,
            task.url,
            self.output_dir,
            metadata_overrides,
            task.meta_cover_path,
            self.ffmpeg_location,
            output_template=output_template,
            ytdlp_options=self.current_ytdlp_auth_options(),
        )
        thread = QThread(self)
        self.download_worker = worker
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.started.connect(self.on_download_started)
        worker.progress_changed.connect(self.on_download_progress)
        worker.finished.connect(self.on_download_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_download_thread_finished)

        self.download_thread = thread
        thread.start()

    def on_download_started(self, index: int) -> None:
        self.active_download_index = index
        task = self.tasks[index]
        task.status = STATUS_DOWNLOADING
        task.progress = 0.0
        self.refresh_card(index)
        self.refresh_open_downloads_popup()
        if self.selected_task_index == index:
            self.update_metadata_panel()

    def on_download_progress(self, index: int, percent: float) -> None:
        task = self.tasks[index]
        task.progress = percent
        self.refresh_card(index)
        self.refresh_open_downloads_popup()
        if self.selected_task_index == index:
            self.update_metadata_panel()

    def on_download_finished(self, index: int, success: bool, error_text: str) -> None:
        task = self.tasks[index]
        task.status = STATUS_DONE if success else STATUS_ERROR
        task.progress = 100.0 if success else task.progress
        task.error = error_text
        self.refresh_card(index)
        self.refresh_open_downloads_popup()
        if self.selected_task_index == index:
            self.update_metadata_panel()
        if not success:
            QMessageBox.warning(
                self,
                "Ошибка загрузки",
                f"Не удалось загрузить аудио:\n{task.url}\n\n{error_text or 'Неизвестная ошибка'}",
            )

    def on_download_thread_finished(self) -> None:
        self.download_thread = None
        self.download_worker = None
        self.start_next_download()

    def animate_active_card(self) -> None:
        self.animation_phase = not self.animation_phase
        for widget in self.playlist_item_widgets:
            widget.tick_animation()
        for card in self.cards:
            card.tick_status_icon_animation()
        for card in self.remote_track_cards:
            card.tick_status_icon_animation()
        for card in self.download_queue_cards:
            card.tick_status_icon_animation()

    def refresh_card(self, index: int, pulse: bool = False) -> None:
        self.cards[index].update_from_task(
            self.tasks[index], pulse and self.animation_phase
        )
