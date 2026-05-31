import os
import shutil
import subprocess

from PyQt6.QtCore import QEvent, QSize, Qt, QThread, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .dialogs import ExperimentalImportDialog, MetadataDialog, SpotifyCredentialsDialog
from .library_scanner import load_music_track, scan_music_directory
from .manual_playlist import (
    create_manual_playlist,
    load_manual_playlist,
    load_manual_playlists,
    remove_track_from_manual_playlist,
)
from .metadata_editor import apply_mp3_metadata
from .models import (
    LocalMusicTrack,
    PlaylistEntry,
    SpotifyTrack,
    STATUS_DOWNLOADING,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_META_LOADING,
    STATUS_PENDING,
    STATUS_SKIPPED,
    DownloadTask,
)
from .paths import resource_path
from .playlist_storage import delete_playlist, load_playlists, save_playlist
from .settings import (
    load_elenveil_root_dir,
    load_spotify_credentials,
    save_elenveil_root_dir,
    save_spotify_credentials,
)
from .widgets import AddCard, DownloadCard, PlaylistListItemWidget, SpotifyTrackCard, ToggleSwitch
from .workers import DownloadWorker, MetadataWorker, SpotDLDownloadWorker, SpotifyPlaylistWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Elenveil")
        self.resize(640, 640)

        self.tasks: list[DownloadTask] = []
        self.cards: list[DownloadCard] = []
        self.playlists: list[PlaylistEntry] = []
        self.local_music_tracks: list[LocalMusicTrack] = []
        self.spotify_track_cards: list[SpotifyTrackCard] = []
        self.playlist_item_widgets: list[PlaylistListItemWidget] = []
        self.output_dir = ""
        self.ffmpeg_location = ""
        self.ffmpeg_auto_found = False
        self.metadata_icon = QIcon()
        self.cover_pick_icon = QIcon()
        self.cover_reset_icon = QIcon()
        self.select_root_icon = QIcon()
        self.open_folder_icon = QIcon()
        self.add_playlist_icon = QIcon()
        self.import_icon = QIcon()
        self.start_icon = QIcon()
        self.status_icons: dict[str, QIcon] = {}
        self.spotify_credentials = load_spotify_credentials()
        self.reload_theme_icons()

        self.metadata_thread: QThread | None = None
        self.metadata_worker: MetadataWorker | None = None
        self.download_thread: QThread | None = None
        self.download_worker: DownloadWorker | None = None
        self.spotify_thread: QThread | None = None
        self.spotify_worker: SpotifyPlaylistWorker | None = None
        self.spotify_download_thread: QThread | None = None
        self.spotify_download_worker: SpotDLDownloadWorker | None = None
        self.pending_playlist_index: int | None = None
        self.active_spotify_playlist_index: int | None = None
        self.active_download_index: int | None = None
        self.selected_task_index: int | None = None
        self.selected_experimental_track_index: int | None = None
        self.selected_playlist_index: int | None = None
        self.experimental_source_mode = "none"
        self.sort_field = "date"
        self.sort_ascending = False
        self.animation_phase = False
        default_elenveil_root_dir = os.path.join(os.path.expanduser("~"), "Music", "Elenveil")
        self.elenveil_root_dir = ""
        self.music_library_dir = ""
        self.playlists_dir = ""
        self.set_elenveil_root_dir(load_elenveil_root_dir() or default_elenveil_root_dir, persist=False)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)

        self.select_elenveil_root_button = QPushButton()
        self.select_elenveil_root_button.setToolTip("Выбрать папку Elenveil")
        self.select_elenveil_root_button.setAccessibleName("Выбрать папку Elenveil")
        self.select_elenveil_root_button.setFixedSize(36, 36)
        self.select_elenveil_root_button.setStyleSheet(
            "QPushButton { background:#2e3136; border:1px solid #3b3f46; border-radius:8px; }"
            "QPushButton:hover { background:#373b43; }"
            "QPushButton:disabled { background:#2a2d33; border-color:#353941; }"
        )
        self.select_elenveil_root_button.clicked.connect(self.choose_elenveil_root_directory)
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
        self.create_playlist_button = QPushButton()
        self.create_playlist_button.setToolTip("Добавить плейлист")
        self.create_playlist_button.setAccessibleName("Добавить плейлист")
        self.create_playlist_button.setFixedSize(36, 36)
        self.create_playlist_button.setStyleSheet(
            "QPushButton { background:#2e3136; border:1px solid #3b3f46; border-radius:8px; }"
            "QPushButton:hover { background:#373b43; }"
            "QPushButton:disabled { background:#2a2d33; border-color:#353941; }"
        )
        self.create_playlist_button.clicked.connect(self.add_playlist)

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

        self.experimental_mode_toggle = ToggleSwitch()
        self.experimental_mode_toggle.setChecked(False)
        self.experimental_mode_toggle.setToolTip("Экспериментальный режим")
        self.experimental_mode_toggle.toggled.connect(self.on_experimental_mode_toggled)
        self.experimental_mode_label = QLabel("Экспериментальный режим")
        self.experimental_mode_label.setStyleSheet("color:#b4bcc9; font-size:12px;")
        experimental_layout = QHBoxLayout()
        experimental_layout.setContentsMargins(0, 0, 0, 0)
        experimental_layout.setSpacing(6)
        experimental_layout.addWidget(self.experimental_mode_label)
        experimental_layout.addWidget(self.experimental_mode_toggle)

        self.ffmpeg_status_label = QLabel("FFmpeg: проверка...")
        self.ffmpeg_status_label.setStyleSheet("color:#b4bcc9; font-size:12px;")
        top.addStretch(1)
        top.addLayout(experimental_layout)
        top.addSpacing(12)
        top.addWidget(self.ffmpeg_status_label)
        layout.addLayout(top)

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

        self.content_stack = QStackedWidget()
        self.normal_page = QWidget()
        self.normal_page_layout = QVBoxLayout(self.normal_page)
        self.normal_page_layout.setContentsMargins(0, 0, 0, 0)
        self.normal_page_layout.setSpacing(0)

        self.experimental_page = QWidget()
        experimental_page_layout = QVBoxLayout(self.experimental_page)
        experimental_page_layout.setContentsMargins(0, 0, 0, 0)
        experimental_page_layout.setSpacing(8)

        self.sort_date_button = self.create_text_header_button("")
        self.sort_title_button = self.create_text_header_button("")
        self.sort_date_button.clicked.connect(lambda: self.on_sort_requested("date"))
        self.sort_title_button.clicked.connect(lambda: self.on_sort_requested("title"))
        self.update_sort_button_labels()
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

        self.playlists_panel, playlists_layout = self.create_section_panel(
            "Плейлисты",
            right_header_widgets=[
                self.select_elenveil_root_button,
                self.open_music_folder_button,
                self.create_playlist_button,
            ],
        )
        self.all_music_button = self.create_text_header_button("Вся музыка")
        self.all_music_button.setCheckable(True)
        self.all_music_button.clicked.connect(self.show_all_music)
        playlists_layout.addWidget(self.all_music_button)
        self.playlist_list = QListWidget()
        self.playlist_list.setStyleSheet(
            "QListWidget { background:#20242a; border:none; padding:6px; }"
            "QListWidget::item { padding:0; margin:0 0 8px 0; border:none; }"
            "QListWidget::item:selected { background:transparent; }"
        )
        playlists_layout.addWidget(self.playlist_list)

        self.tracks_panel, tracks_layout = self.create_section_panel(
            "Треки",
            [
                self.import_button,
                self.start_button,
            ],
            [
                self.delete_files_checkbox,
                self.sort_date_button,
                self.sort_title_button,
            ],
        )
        self.spotify_tracks_scroll = QScrollArea()
        self.spotify_tracks_scroll.setWidgetResizable(True)
        self.spotify_tracks_container = QWidget()
        self.spotify_tracks_layout = QVBoxLayout(self.spotify_tracks_container)
        self.spotify_tracks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.spotify_tracks_layout.setContentsMargins(4, 4, 4, 4)
        self.spotify_tracks_layout.setSpacing(8)
        self.spotify_tracks_empty = QLabel("Плейлист не выбран")
        self.spotify_tracks_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spotify_tracks_empty.setStyleSheet(
            "font-size:14px; color:#8f98a6; padding:24px; background:transparent; border:none;"
        )
        self.spotify_tracks_layout.addWidget(self.spotify_tracks_empty)
        self.spotify_tracks_layout.addStretch(1)
        self.spotify_tracks_scroll.setWidget(self.spotify_tracks_container)
        tracks_layout.addWidget(self.spotify_tracks_scroll)

        self.metadata_panel, metadata_layout = self.create_section_panel("Метаданные")
        self.metadata_values: dict[str, QLabel] = {}
        for label_text in ("Название", "Канал", "URL", "Автор", "Альбом", "Статус"):
            title_label = QLabel(label_text)
            title_label.setStyleSheet(
                "font-size:12px; color:#8f98a6; font-weight:700; background:transparent; border:none;"
            )
            value_label = QLabel("—")
            value_label.setWordWrap(True)
            value_label.setStyleSheet(
                "font-size:13px; color:#eef2f7; background:transparent; border:none;"
            )
            metadata_layout.addWidget(title_label)
            metadata_layout.addWidget(value_label)
            self.metadata_values[label_text] = value_label
        metadata_layout.addStretch(1)

        self.experimental_splitter.addWidget(self.playlists_panel)
        self.experimental_splitter.addWidget(self.tracks_panel)
        self.experimental_splitter.addWidget(self.metadata_panel)
        self.experimental_splitter.setSizes([220, 620, 280])

        experimental_page_layout.addWidget(self.experimental_splitter)
        self.content_stack.addWidget(self.normal_page)
        self.content_stack.addWidget(self.experimental_page)
        layout.addWidget(self.content_stack)

        self.setCentralWidget(root)
        self.relocate_track_view(self.normal_page_layout)
        self.playlist_list.currentRowChanged.connect(self.on_playlist_selected)
        self.restore_persisted_playlists()
        self.update_metadata_panel()
        self.apply_mode_state(False)

        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(120)
        self.animation_timer.timeout.connect(self.animate_active_card)
        self.animation_timer.start()
        QTimer.singleShot(0, self.ensure_ffmpeg_available)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.PaletteChange:
            self.reload_theme_icons()
        super().changeEvent(event)

    def is_dark_theme(self) -> bool:
        palette = self.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        text_color = palette.color(QPalette.ColorRole.WindowText)
        return text_color.lightness() > window_color.lightness()

    def themed_icon_path(self, base_name: str) -> str:
        suffix = "light" if self.is_dark_theme() else "dark"
        return resource_path("assets", "icons", f"{base_name}_{suffix}.svg")

    def create_text_header_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setFixedHeight(36)
        button.setStyleSheet(
            "QPushButton {"
            "background:#2e3136;"
            "border:1px solid #3b3f46;"
            "border-radius:8px;"
            "padding:0 12px;"
            "color:#eef2f7;"
            "font-size:12px;"
            "font-weight:600;"
            "}"
            "QPushButton:hover { background:#373b43; }"
            "QPushButton:checked { background:#355680; border-color:#4b74a7; }"
            "QPushButton:disabled { background:#2a2d33; border-color:#353941; color:#8b93a0; }"
        )
        return button

    def create_section_panel(
        self,
        title: str,
        left_header_widgets: list[QWidget] | None = None,
        right_header_widgets: list[QWidget] | None = None,
    ) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background:#1c2026; border:1px solid #343941; border-radius:10px; }"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-size:14px; font-weight:700; color:#eef2f7; background:transparent; border:none;"
        )
        header_row.addWidget(title_label)
        for widget in left_header_widgets or []:
            header_row.addWidget(widget)
        header_row.addStretch(1)
        for widget in right_header_widgets or []:
            header_row.addWidget(widget)
        layout.addLayout(header_row)
        return frame, layout

    def relocate_track_view(self, target_layout: QVBoxLayout) -> None:
        current_parent = self.scroll_area.parentWidget()
        if current_parent is not None:
            self.scroll_area.setParent(None)
        target_layout.addWidget(self.scroll_area)

    def update_sort_button_labels(self) -> None:
        date_arrow = "↑" if self.sort_field == "date" and self.sort_ascending else "↓"
        title_arrow = "↑" if self.sort_field == "title" and self.sort_ascending else "↓"
        self.sort_date_button.setText(f"По дате {date_arrow}")
        self.sort_title_button.setText(f"По названию {title_arrow}")
        self.sort_date_button.setChecked(self.sort_field == "date")
        self.sort_title_button.setChecked(self.sort_field == "title")

    def on_sort_requested(self, field: str) -> None:
        if self.sort_field == field:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_field = field
            self.sort_ascending = field == "title"
        self.update_sort_button_labels()
        if self.experimental_source_mode == "all_music":
            self.render_experimental_tracks(self.get_sorted_experimental_tracks(self.local_music_tracks))
        elif self.experimental_source_mode == "playlist" and self.selected_playlist_index is not None:
            playlist = self.playlists[self.selected_playlist_index]
            self.render_experimental_tracks(self.get_sorted_experimental_tracks(playlist.tracks))

    def get_sorted_experimental_tracks(
        self,
        tracks: list[SpotifyTrack] | list[LocalMusicTrack],
    ) -> list[SpotifyTrack] | list[LocalMusicTrack]:
        indexed_tracks = list(enumerate(tracks))

        def sort_key(item: tuple[int, SpotifyTrack | LocalMusicTrack]) -> tuple:
            index, track = item
            if self.sort_field == "title":
                return (track.title.casefold(), index)
            added_at = getattr(track, "added_at", 0.0)
            return (added_at, index)

        sorted_items = sorted(indexed_tracks, key=sort_key, reverse=not self.sort_ascending)
        return [track for _, track in sorted_items]

    def get_track_status_title(self, track: SpotifyTrack | LocalMusicTrack | None) -> str:
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
            STATUS_DOWNLOADING: "Загружается через spotdl",
            STATUS_DONE: "Загружен",
            STATUS_ERROR: f"Ошибка: {track.error}" if getattr(track, "error", "") else "Ошибка загрузки",
            STATUS_SKIPPED: (
                f"Пропущен: {track.error}"
                if getattr(track, "error", "")
                else "Пропущен: spotdl не нашёл источник"
            ),
        }
        return status_titles.get(getattr(track, "status", STATUS_PENDING), "Ожидает загрузки")

    def refresh_experimental_source_view(self) -> None:
        if not self.experimental_mode_toggle.isChecked():
            return
        if self.experimental_source_mode == "all_music":
            tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
            if tracks and (self.selected_experimental_track_index is None or self.selected_experimental_track_index >= len(tracks)):
                self.selected_experimental_track_index = 0
            self.render_experimental_tracks(tracks)
            self.update_metadata_panel()
            return
        if self.experimental_source_mode == "playlist" and self.selected_playlist_index is not None:
            playlist = self.playlists[self.selected_playlist_index]
            tracks = self.get_sorted_experimental_tracks(playlist.tracks)
            if tracks and (self.selected_experimental_track_index is None or self.selected_experimental_track_index >= len(tracks)):
                self.selected_experimental_track_index = 0
            self.render_experimental_tracks(tracks)
            self.update_metadata_panel()

    def update_delete_files_checkbox_visibility(self) -> None:
        visible = self.experimental_mode_toggle.isChecked() and self.experimental_source_mode == "playlist"
        self.delete_files_checkbox.setVisible(visible)

    def update_start_button_state(self) -> None:
        if self.experimental_mode_toggle.isChecked():
            enabled = False
            if (
                self.spotify_download_thread is None
                and self.spotify_thread is None
                and self.experimental_source_mode == "playlist"
                and self.selected_playlist_index is not None
                and 0 <= self.selected_playlist_index < len(self.playlists)
            ):
                playlist = self.playlists[self.selected_playlist_index]
                enabled = (
                    playlist.source == "spotify"
                    and not playlist.is_loading
                    and any(
                        track.status in (STATUS_PENDING, STATUS_ERROR, STATUS_SKIPPED)
                        for track in playlist.tracks
                    )
                )
            self.start_button.setEnabled(enabled)
            return

        self.start_button.setEnabled(any(task.status == STATUS_PENDING for task in self.tasks))

    def refresh_local_music_tracks(self) -> None:
        self.ensure_elenveil_directories()
        self.local_music_tracks = scan_music_directory(self.music_library_dir)

    def show_all_music(self) -> None:
        self.experimental_source_mode = "all_music"
        self.selected_playlist_index = None
        self.selected_experimental_track_index = None
        self.all_music_button.setChecked(True)
        self.playlist_list.blockSignals(True)
        self.playlist_list.setCurrentRow(-1)
        self.playlist_list.blockSignals(False)
        for widget in self.playlist_item_widgets:
            widget.set_selected(False)
        self.refresh_local_music_tracks()
        tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
        self.selected_experimental_track_index = 0 if tracks else None
        self.render_experimental_tracks(tracks)
        self.update_metadata_panel()
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()

    def apply_mode_state(self, is_experimental: bool) -> None:
        self.select_elenveil_root_button.setVisible(is_experimental)
        self.open_music_folder_button.setVisible(is_experimental)
        self.create_playlist_button.setVisible(is_experimental)
        if is_experimental:
            self.content_stack.setCurrentWidget(self.experimental_page)
            self.resize(max(self.width(), 1180), max(self.height(), 720))
        else:
            self.relocate_track_view(self.normal_page_layout)
            self.content_stack.setCurrentWidget(self.normal_page)
            self.resize(640, max(self.height(), 640))
        self.update_metadata_panel()
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()

    def on_experimental_mode_toggled(self, checked: bool) -> None:
        self.apply_mode_state(checked)
        if checked:
            self.show_all_music()

    def open_elenveil_music_folder(self) -> None:
        self.ensure_elenveil_directories()
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.elenveil_root_dir))

    def set_elenveil_root_dir(self, root_dir: str, persist: bool = True) -> None:
        normalized_root_dir = os.path.abspath(os.path.expanduser(root_dir.strip()))
        self.elenveil_root_dir = normalized_root_dir
        self.music_library_dir = os.path.join(self.elenveil_root_dir, "music")
        self.playlists_dir = os.path.join(self.elenveil_root_dir, "playlists")
        self.ensure_elenveil_directories()
        if persist:
            save_elenveil_root_dir(self.elenveil_root_dir)

    def choose_elenveil_root_directory(self) -> None:
        if any(
            worker is not None
            for worker in (
                self.metadata_thread,
                self.download_thread,
                self.spotify_thread,
                self.spotify_download_thread,
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

        self.set_elenveil_root_dir(selected_dir)
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
        if self.experimental_mode_toggle.isChecked():
            self.show_all_music()
        else:
            self.update_metadata_panel()
            self.update_start_button_state()

    def restore_persisted_playlists(self) -> None:
        self.ensure_elenveil_directories()
        persisted = load_playlists(self.playlists_dir)
        persisted.extend(load_manual_playlists(self.playlists_dir, self.music_library_dir))
        if not persisted:
            return
        self.playlists = list(persisted)
        self.rebuild_playlist_list()

    def rebuild_playlist_list(self) -> None:
        self.playlist_item_widgets = []
        self.playlist_list.clear()
        for playlist in self.playlists:
            self.add_playlist_list_item(playlist)

    def persist_playlist(self, playlist_index: int) -> None:
        if not (0 <= playlist_index < len(self.playlists)):
            return
        playlist = self.playlists[playlist_index]
        if playlist.source != "spotify" or playlist.is_loading:
            return
        save_playlist(playlist, self.playlists_dir)

    def add_playlist_list_item(self, playlist: PlaylistEntry) -> int:
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 44))
        self.playlist_list.addItem(item)
        widget = PlaylistListItemWidget(
            playlist.name,
            self.playlist_loading_icon,
            self.playlist_ready_icon,
        )
        widget.set_loading(playlist.is_loading or playlist.is_downloading)
        row = self.playlist_list.count() - 1
        widget.clicked.connect(lambda row=row: self.playlist_list.setCurrentRow(row))
        widget.delete_requested.connect(lambda row=row: self.on_playlist_delete_requested(row))
        self.playlist_item_widgets.append(widget)
        self.playlist_list.setItemWidget(item, widget)
        return row

    def on_playlist_delete_requested(self, row: int) -> None:
        if not (0 <= row < len(self.playlists)):
            return
        playlist = self.playlists[row]
        answer = QMessageBox.question(
            self,
            "Удаление плейлиста",
            f"Удалить плейлист '{playlist.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        if playlist.source == "manual":
            playlist_path = playlist.source_url.strip()
            if playlist_path and os.path.exists(playlist_path):
                os.remove(playlist_path)
        elif playlist.source == "spotify":
            delete_playlist(playlist, self.playlists_dir)

        self.playlists.pop(row)
        self.rebuild_playlist_list()
        if not self.playlists:
            self.playlist_list.setCurrentRow(-1)
            self.selected_playlist_index = None
            self.selected_experimental_track_index = None
            self.experimental_source_mode = "none"
            self.render_experimental_tracks([])
            self.update_metadata_panel()
        else:
            new_row = min(row, len(self.playlists) - 1)
            self.playlist_list.setCurrentRow(new_row)
            self.on_playlist_selected(new_row)
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()

    def add_playlist(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить плейлист")
        root = QVBoxLayout(dialog)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("Выберите источник плейлиста")
        title.setStyleSheet("font-size:14px; font-weight:700;")
        root.addWidget(title)

        buttons_row = QHBoxLayout()
        manual_button = self.create_text_header_button("Ручной")
        spotify_button = self.create_text_header_button("Spotify")
        youtube_button = self.create_text_header_button("Youtube")
        buttons_row.addWidget(manual_button)
        buttons_row.addWidget(spotify_button)
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
        spotify_button.clicked.connect(lambda: choose("spotify"))
        youtube_button.clicked.connect(lambda: choose("youtube"))

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if selection["value"] == "spotify":
            self.add_spotify_playlist()
            return
        if selection["value"] == "manual":
            self.add_manual_playlist()
            return
        if selection["value"] == "youtube":
            QMessageBox.information(self, "Скоро будет", "Импорт плейлиста Youtube пока не реализован.")

    def add_manual_playlist(self) -> None:
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Ручной плейлист")
        dialog.setLabelText("Введите название плейлиста:")
        dialog.setTextEchoMode(QLineEdit.EchoMode.Normal)
        dialog.resize(520, dialog.sizeHint().height())
        ok = dialog.exec()
        playlist_name = dialog.textValue().strip()
        if not ok or not playlist_name:
            return

        existing_index = next(
            (
                index
                for index, playlist in enumerate(self.playlists)
                if playlist.source == "manual" and playlist.name.casefold() == playlist_name.casefold()
            ),
            None,
        )
        if existing_index is not None:
            self.playlist_list.setCurrentRow(existing_index)
            self.on_playlist_selected(existing_index)
            QMessageBox.information(self, "Плейлист", "Плейлист с таким названием уже существует.")
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
        row = self.add_playlist_list_item(playlist)
        self.playlist_list.setCurrentRow(row)
        self.on_playlist_selected(row)

    def add_spotify_playlist(self) -> None:
        if self.spotify_thread is not None:
            QMessageBox.information(self, "Spotify", "Подождите завершения текущего импорта плейлиста.")
            return
        if not self.ensure_spotify_credentials():
            return

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Spotify плейлист")
        dialog.setLabelText("Вставьте ссылку на Spotify плейлист:")
        dialog.setTextEchoMode(QLineEdit.EchoMode.Normal)
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
                if playlist.source == "spotify" and playlist.source_url.strip() == playlist_url
            ),
            None,
        )
        if existing_index is not None:
            self.playlist_list.setCurrentRow(existing_index)
            self.on_playlist_selected(existing_index)
            QMessageBox.information(self, "Spotify", "Этот плейлист уже импортирован и восстановлен из локального кэша.")
            return

        self.create_playlist_button.setEnabled(False)
        self.pending_playlist_index = self.add_loading_playlist_entry(playlist_url)
        self.start_spotify_playlist_import(playlist_url)

    def ensure_spotify_credentials(self) -> bool:
        client_id = self.spotify_credentials.get("client_id", "").strip()
        client_secret = self.spotify_credentials.get("client_secret", "").strip()
        if client_id and client_secret:
            return True

        dialog = SpotifyCredentialsDialog(self, client_id, client_secret)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        client_id, client_secret = dialog.get_values()
        if not client_id or not client_secret:
            QMessageBox.warning(
                self,
                "Spotify",
                "Client ID и Client Secret не могут быть пустыми.",
            )
            return False

        self.spotify_credentials = {
            "client_id": client_id,
            "client_secret": client_secret,
        }
        save_spotify_credentials(client_id, client_secret)
        return True

    def start_spotify_playlist_import(self, playlist_url: str) -> None:
        worker = SpotifyPlaylistWorker(
            playlist_url,
            self.spotify_credentials.get("client_id", ""),
            self.spotify_credentials.get("client_secret", ""),
        )
        thread = QThread(self)
        self.spotify_worker = worker
        self.spotify_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.playlist_ready.connect(self.on_spotify_playlist_ready)
        worker.failed.connect(self.on_spotify_playlist_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_spotify_playlist_import_finished)
        thread.start()

    def on_spotify_playlist_ready(self, playlist: PlaylistEntry) -> None:
        if self.pending_playlist_index is None or self.pending_playlist_index >= len(self.playlists):
            return
        playlist.is_loading = False
        self.playlists[self.pending_playlist_index] = playlist
        widget = self.playlist_item_widgets[self.pending_playlist_index]
        widget.set_title(playlist.name)
        widget.set_loading(False)
        self.persist_playlist(self.pending_playlist_index)
        self.playlist_list.setCurrentRow(self.pending_playlist_index)
        self.on_playlist_selected(self.pending_playlist_index)
        self.update_start_button_state()

    def on_spotify_playlist_failed(self, error_text: str) -> None:
        if self.pending_playlist_index is not None and 0 <= self.pending_playlist_index < len(self.playlists):
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
        message = error_text or "Не удалось импортировать плейлист Spotify."
        if "Client ID" in message or "Client Secret" in message or "инициализировать Spotify API" in message:
            answer = QMessageBox.question(
                self,
                "Spotify",
                f"{message}\n\nОткрыть диалог ввода Spotify-данных?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.spotify_credentials = {"client_id": "", "client_secret": ""}
                self.ensure_spotify_credentials()
            return
        QMessageBox.warning(
            self,
            "Spotify",
            message,
        )

    def on_spotify_playlist_import_finished(self) -> None:
        self.spotify_thread = None
        self.spotify_worker = None
        self.pending_playlist_index = None
        self.create_playlist_button.setEnabled(True)
        self.update_start_button_state()

    def on_playlist_selected(self, row: int) -> None:
        self.all_music_button.setChecked(False)
        for index, widget in enumerate(self.playlist_item_widgets):
            widget.set_selected(index == row)
        if row < 0 or row >= len(self.playlists):
            self.experimental_source_mode = "none"
            self.selected_playlist_index = None
            self.selected_experimental_track_index = None
            self.render_experimental_tracks([])
            self.update_metadata_panel()
            self.update_delete_files_checkbox_visibility()
            return
        self.experimental_source_mode = "playlist"
        if self.playlists[row].source == "manual":
            self.playlists[row] = load_manual_playlist(self.playlists[row].source_url, self.music_library_dir)
            self.playlist_item_widgets[row].set_title(self.playlists[row].name)
        self.selected_playlist_index = row
        tracks = self.get_sorted_experimental_tracks(self.playlists[row].tracks)
        self.selected_experimental_track_index = 0 if tracks else None
        self.render_experimental_tracks(tracks)
        self.update_metadata_panel()
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()

    def add_loading_playlist_entry(self, source_url: str) -> int:
        playlist = PlaylistEntry(
            name="Загрузка плейлиста...",
            source="spotify",
            source_url=source_url,
            tracks=[],
            is_loading=True,
        )
        self.playlists.append(playlist)
        row = self.add_playlist_list_item(playlist)
        self.playlist_list.setCurrentRow(row)
        self.on_playlist_selected(row)
        return row

    def render_experimental_tracks(
        self,
        tracks: list[SpotifyTrack] | list[LocalMusicTrack],
    ) -> None:
        while self.spotify_tracks_layout.count():
            item = self.spotify_tracks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.spotify_track_cards = []
        if not tracks:
            self.spotify_tracks_empty = QLabel("Треки не найдены")
            if self.experimental_source_mode == "all_music":
                self.spotify_tracks_empty.setText("В папке music пока нет mp3-файлов")
            elif self.selected_playlist_index is not None and 0 <= self.selected_playlist_index < len(self.playlists):
                playlist = self.playlists[self.selected_playlist_index]
                if playlist.is_loading:
                    self.spotify_tracks_empty.setText("Подгружаем треки плейлиста...")
                else:
                    self.spotify_tracks_empty.setText(
                        playlist.note or "Spotify не вернул треки для этого плейлиста"
                    )
            self.spotify_tracks_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.spotify_tracks_empty.setStyleSheet(
                "font-size:14px; color:#8f98a6; padding:24px; background:transparent; border:none;"
            )
            self.spotify_tracks_layout.addWidget(self.spotify_tracks_empty)
            self.spotify_tracks_layout.addStretch(1)
            return

        for track_index, track in enumerate(tracks):
            card = SpotifyTrackCard(track, track_index, self.status_icons, self.metadata_icon)
            card.selected.connect(self.on_spotify_track_selected)
            card.delete_requested.connect(self.on_experimental_track_delete_requested)
            card.metadata_requested.connect(self.on_experimental_track_metadata_requested)
            card.set_selected(track_index == self.selected_experimental_track_index)
            self.spotify_track_cards.append(card)
            self.spotify_tracks_layout.addWidget(card)
        self.spotify_tracks_layout.addStretch(1)

    def on_spotify_track_selected(self, index: int) -> None:
        self.selected_experimental_track_index = index
        for card_index, card in enumerate(self.spotify_track_cards):
            card.set_selected(card_index == index)
        self.update_metadata_panel()

    def on_experimental_track_delete_requested(self, index: int) -> None:
        if self.experimental_source_mode == "all_music":
            self.delete_track_from_all_music(index)
            return
        if self.experimental_source_mode == "playlist":
            self.delete_track_from_selected_playlist(index)

    def on_experimental_track_metadata_requested(self, index: int) -> None:
        if self.experimental_source_mode == "all_music":
            tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
        elif self.experimental_source_mode == "playlist" and self.selected_playlist_index is not None:
            tracks = self.get_sorted_experimental_tracks(self.playlists[self.selected_playlist_index].tracks)
        else:
            return

        if not (0 <= index < len(tracks)):
            return
        track = tracks[index]
        file_path = track.file_path if isinstance(track, LocalMusicTrack) else track.local_file_path
        if not file_path:
            QMessageBox.information(
                self,
                "Метаданные",
                "Метаданные можно редактировать только у уже существующего mp3-файла.",
            )
            return
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Метаданные", "Файл mp3 не найден.")
            return

        dialog_task = DownloadTask(
            url=file_path,
            title=track.title,
            channel=track.artists,
            thumbnail_data=track.thumbnail_data,
            meta_title=track.title,
            meta_author=track.artists,
            meta_group="",
            meta_album=track.album,
        )
        dialog = MetadataDialog(self, dialog_task, self.cover_pick_icon, self.cover_reset_icon)
        dialog.url_edit.setReadOnly(True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values, cover_path, cover_mode = dialog.get_metadata_values()
        try:
            apply_mp3_metadata(
                file_path,
                title=values["title"],
                author=values["author"],
                group=values["group"],
                album=values["album"],
                cover_mode=cover_mode,
                cover_path=cover_path,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Метаданные", f"Не удалось обновить mp3-метаданные:\n{exc}")
            return

        self.refresh_experimental_track_sources_after_metadata_edit(file_path)

    def refresh_experimental_track_sources_after_metadata_edit(self, file_path: str) -> None:
        resolved_path = os.path.realpath(file_path)
        self.refresh_local_music_tracks()

        for playlist_index, playlist in enumerate(self.playlists):
            if playlist.source == "manual":
                contains_track = any(
                    isinstance(track, LocalMusicTrack)
                    and os.path.realpath(track.file_path) == resolved_path
                    for track in playlist.tracks
                )
                if contains_track:
                    self.playlists[playlist_index] = load_manual_playlist(
                        playlist.source_url,
                        self.music_library_dir,
                    )
                continue

            if playlist.source != "spotify":
                continue

            refreshed = None
            for local_track in self.local_music_tracks:
                if os.path.realpath(local_track.file_path) == resolved_path:
                    refreshed = local_track
                    break
            if refreshed is None:
                continue

            changed = False
            for track in playlist.tracks:
                if isinstance(track, SpotifyTrack) and track.local_file_path and os.path.realpath(track.local_file_path) == resolved_path:
                    track.title = refreshed.title
                    track.artists = refreshed.artists
                    track.album = refreshed.album
                    track.thumbnail_data = refreshed.thumbnail_data
                    changed = True
            if changed:
                self.persist_playlist(playlist_index)

        self.refresh_experimental_source_view()

    def delete_track_from_all_music(self, index: int) -> None:
        tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
        if not (0 <= index < len(tracks)):
            return
        track = tracks[index]
        answer = QMessageBox.question(
            self,
            "Удаление трека",
            f"Удалить файл '{os.path.basename(track.file_path)}' из папки music?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        if os.path.exists(track.file_path):
            os.remove(track.file_path)
        self.refresh_local_music_tracks()
        refreshed_tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
        self.selected_experimental_track_index = min(index, len(refreshed_tracks) - 1) if refreshed_tracks else None
        self.render_experimental_tracks(refreshed_tracks)
        self.update_metadata_panel()

    def delete_track_from_selected_playlist(self, index: int) -> None:
        if self.selected_playlist_index is None or not (0 <= self.selected_playlist_index < len(self.playlists)):
            return
        playlist = self.playlists[self.selected_playlist_index]
        tracks = self.get_sorted_experimental_tracks(playlist.tracks)
        if not (0 <= index < len(tracks)):
            return
        track = tracks[index]
        delete_files = self.delete_files_checkbox.isChecked()
        answer = QMessageBox.question(
            self,
            "Удаление трека",
            "Удалить выбранный трек?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        if isinstance(track, LocalMusicTrack):
            if delete_files and os.path.exists(track.file_path):
                os.remove(track.file_path)
            if playlist.source == "manual":
                updated_playlist = remove_track_from_manual_playlist(
                    playlist.source_url,
                    track.file_path,
                    self.music_library_dir,
                )
                self.playlists[self.selected_playlist_index] = updated_playlist
                playlist = updated_playlist
            else:
                playlist.tracks = [item for item in playlist.tracks if item is not track]
                self.persist_playlist(self.selected_playlist_index)
        else:
            if delete_files and track.local_file_path and os.path.exists(track.local_file_path):
                os.remove(track.local_file_path)
                track.local_file_path = ""
                if track.status == STATUS_DONE:
                    track.status = STATUS_PENDING
            playlist.tracks = [item for item in playlist.tracks if item is not track]
            self.persist_playlist(self.selected_playlist_index)

        if playlist.source == "manual":
            self.playlist_item_widgets[self.selected_playlist_index].set_title(playlist.name)
        self.refresh_local_music_tracks()
        refreshed_tracks = self.get_sorted_experimental_tracks(playlist.tracks)
        self.selected_experimental_track_index = min(index, len(refreshed_tracks) - 1) if refreshed_tracks else None
        self.render_experimental_tracks(refreshed_tracks)
        self.update_metadata_panel()
        self.update_start_button_state()

    def select_task(self, index: int | None) -> None:
        self.selected_task_index = index if index is not None and 0 <= index < len(self.tasks) else None
        for card_index, card in enumerate(self.cards):
            card.set_selected(card_index == self.selected_task_index)
        self.update_metadata_panel()

    def update_metadata_panel(self) -> None:
        if self.experimental_mode_toggle.isChecked():
            if self.experimental_source_mode == "all_music":
                track = (
                    self.get_sorted_experimental_tracks(self.local_music_tracks)[self.selected_experimental_track_index]
                    if self.selected_experimental_track_index is not None
                    and 0 <= self.selected_experimental_track_index < len(self.local_music_tracks)
                    else None
                )
                values = {
                    "Название": track.title if track else "Трек не выбран",
                    "Канал": "Вся музыка",
                    "URL": track.file_path if track else "—",
                    "Автор": track.artists if track else "—",
                    "Альбом": track.album if track else "—",
                    "Статус": self.get_track_status_title(track) if track else "Нет треков",
                }
            else:
                playlist = (
                    self.playlists[self.selected_playlist_index]
                    if self.selected_playlist_index is not None and 0 <= self.selected_playlist_index < len(self.playlists)
                    else None
                )
                sorted_tracks = (
                    self.get_sorted_experimental_tracks(playlist.tracks)
                    if playlist is not None
                    else []
                )
                track = (
                    sorted_tracks[self.selected_experimental_track_index]
                    if self.selected_experimental_track_index is not None
                    and 0 <= self.selected_experimental_track_index < len(sorted_tracks)
                    else None
                )
                values = {
                    "Название": track.title if track else "Трек не выбран",
                    "Канал": playlist.name if playlist else "—",
                    "URL": (
                        track.spotify_url
                        if isinstance(track, SpotifyTrack)
                        else track.file_path
                    ) if track else "—",
                    "Автор": track.artists if track else "—",
                    "Альбом": track.album if track else "—",
                    "Статус": (
                        self.get_track_status_title(track)
                        if track
                        else (
                            "Подгрузка Spotify-плейлиста"
                            if playlist and playlist.is_loading
                            else (playlist.note or "Нет треков") if playlist else "Нет треков"
                        )
                    ),
                }
        else:
            task = self.tasks[self.selected_task_index] if self.selected_task_index is not None else None
            if task is None:
                values = {
                    "Название": "Трек не выбран",
                    "Канал": "—",
                    "URL": "—",
                    "Автор": "—",
                    "Альбом": "—",
                    "Статус": "—",
                }
            else:
                status_titles = {
                    STATUS_META_LOADING: "Подгрузка метаданных",
                    STATUS_PENDING: "Ожидает загрузки",
                    STATUS_DOWNLOADING: "Загружается",
                    STATUS_DONE: "Завершено",
                    STATUS_ERROR: "Ошибка",
                }
                values = {
                    "Название": task.title or "—",
                    "Канал": task.channel or "—",
                    "URL": task.url or "—",
                    "Автор": task.meta_author or "—",
                    "Альбом": task.meta_album or "—",
                    "Статус": status_titles.get(task.status, "—"),
                }
        for key, value in values.items():
            self.metadata_values[key].setText(value)

    def reload_theme_icons(self) -> None:
        self.metadata_icon = QIcon(self.themed_icon_path("metadata_edit"))
        self.cover_pick_icon = QIcon(self.themed_icon_path("cover_pick"))
        self.cover_reset_icon = QIcon(self.themed_icon_path("cover_reset"))
        self.select_root_icon = self.cover_pick_icon
        self.open_folder_icon = QIcon(self.themed_icon_path("folder"))
        self.add_playlist_icon = QIcon(self.themed_icon_path("add_playlist"))
        self.import_icon = QIcon(self.themed_icon_path("file"))
        self.start_icon = QIcon(self.themed_icon_path("mass_download"))
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
        if hasattr(self, "import_button"):
            self.import_button.setIcon(self.import_icon)
            self.import_button.setIconSize(QSize(18, 18))
        if hasattr(self, "start_button"):
            self.start_button.setIcon(self.start_icon)
            self.start_button.setIconSize(QSize(18, 18))
        for widget in self.playlist_item_widgets:
            widget.set_loading_icon(self.playlist_loading_icon)
            widget.set_ready_icon(self.playlist_ready_icon)
        for card in self.cards:
            card.set_metadata_icon(self.metadata_icon)
            card.set_status_icons(self.status_icons)
        for card in self.spotify_track_cards:
            card.set_status_icons(self.status_icons)
            card.set_metadata_icon(self.metadata_icon)

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
        ffmpeg_check = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, check=False, env=env)
        ffprobe_check = subprocess.run([ffprobe_path, "-version"], capture_output=True, text=True, check=False, env=env)
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
        manual_button = message.addButton("Выбрать вручную", QMessageBox.ButtonRole.ActionRole)
        brew_button = None
        port_button = None
        if shutil.which("brew"):
            brew_button = message.addButton("Установить через brew", QMessageBox.ButtonRole.ActionRole)
        if shutil.which("port"):
            port_button = message.addButton("Установить через ports", QMessageBox.ButtonRole.ActionRole)
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
        if self.experimental_mode_toggle.isChecked():
            self.import_links_for_experimental_mode()
            return
        if self.metadata_thread is not None:
            QMessageBox.information(self, "Импорт", "Дождитесь завершения подгрузки метаданных.")
            return

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

        self.enqueue_links(links)

    def import_links_for_experimental_mode(self) -> None:
        if self.experimental_source_mode != "all_music":
            QMessageBox.information(
                self,
                "Импорт",
                "Импорт ссылок в экспериментальном режиме сейчас доступен только для раздела 'Вся музыка'.",
            )
            return

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
        )
        dialog.downloads_completed.connect(self.on_experimental_import_completed)
        dialog.exec()

    def on_experimental_import_completed(self) -> None:
        self.refresh_local_music_tracks()
        if self.experimental_mode_toggle.isChecked() and self.experimental_source_mode == "all_music":
            tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
            if tracks and (self.selected_experimental_track_index is None or self.selected_experimental_track_index >= len(tracks)):
                self.selected_experimental_track_index = 0
            self.render_experimental_tracks(tracks)
            self.update_metadata_panel()

    def add_link_from_dialog(self) -> None:
        if self.metadata_thread is not None:
            QMessageBox.information(self, "Добавить", "Дождитесь завершения подгрузки метаданных.")
            return

        dialog = QInputDialog(self)
        dialog.setWindowTitle("Добавить ссылку")
        dialog.setLabelText("Вставьте ссылку для загрузки:")
        dialog.setTextEchoMode(QLineEdit.EchoMode.Normal)
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
            card = DownloadCard(task, start_index + offset, self.metadata_icon, self.status_icons)
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
        self.start_metadata_load(index_url_pairs)

    def start_metadata_load(self, index_url_pairs: list[tuple[int, str]]) -> None:
        worker = MetadataWorker(index_url_pairs)
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
        task.meta_title = (task.meta_title or extracted_meta.get("title") or title).strip()
        task.meta_author = (
            task.meta_author
            or extracted_meta.get("author")
            or channel
        ).strip()
        task.meta_group = (task.meta_group or extracted_meta.get("group") or "").strip()
        task.meta_album = (task.meta_album or extracted_meta.get("album") or "").strip()
        self.refresh_card(index)
        if self.selected_task_index == index:
            self.update_metadata_panel()

    def on_metadata_finished(self) -> None:
        self.metadata_thread = None
        self.metadata_worker = None
        self.import_button.setEnabled(True)
        self.start_button.setEnabled(any(task.status == STATUS_PENDING for task in self.tasks))

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
            QMessageBox.warning(self, "Некорректная ссылка", "Ссылка не может быть пустой.")
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
        self.start_button.setEnabled(any(task.status == STATUS_PENDING for task in self.tasks))

    def renumber_cards(self) -> None:
        for index, card in enumerate(self.cards):
            card.set_list_index(index)

    def start_downloads(self) -> None:
        if self.experimental_mode_toggle.isChecked():
            self.start_spotify_track_downloads()
            return

        if self.metadata_thread is not None:
            QMessageBox.information(self, "Старт", "Дождитесь завершения подгрузки метаданных.")
            return

        if self.download_thread is not None:
            QMessageBox.information(self, "Старт", "Загрузка уже выполняется.")
            return

        if not any(task.status == STATUS_PENDING for task in self.tasks):
            QMessageBox.information(self, "Старт", "Нет задач со статусом ожидания.")
            return

        os.makedirs(self.music_library_dir, exist_ok=True)
        out_dir = QFileDialog.getExistingDirectory(
            self,
            "Выберите директорию загрузки mp3",
            self.music_library_dir,
        )
        if not out_dir:
            return

        self.output_dir = out_dir
        self.start_button.setEnabled(False)
        self.start_next_download()

    def start_spotify_track_downloads(self) -> None:
        if self.spotify_thread is not None:
            QMessageBox.information(self, "Старт", "Дождитесь завершения импорта Spotify-плейлиста.")
            return
        if self.spotify_download_thread is not None:
            QMessageBox.information(self, "Старт", "Загрузка Spotify-треков уже выполняется.")
            return
        if self.experimental_source_mode != "playlist" or self.selected_playlist_index is None:
            QMessageBox.information(self, "Старт", "Выберите Spotify-плейлист в левой панели.")
            return

        playlist = self.playlists[self.selected_playlist_index]
        if playlist.source != "spotify":
            QMessageBox.information(self, "Старт", "Сейчас загрузка через spotdl доступна только для Spotify-плейлистов.")
            return
        if playlist.is_loading:
            QMessageBox.information(self, "Старт", "Плейлист ещё подгружается.")
            return
        if not playlist.tracks:
            QMessageBox.information(self, "Старт", "В выбранном плейлисте нет треков для загрузки.")
            return

        downloadable_indexes = [
            index
            for index, track in enumerate(playlist.tracks)
            if track.status in (STATUS_PENDING, STATUS_ERROR, STATUS_SKIPPED)
        ]
        if not downloadable_indexes:
            QMessageBox.information(self, "Старт", "Нет Spotify-треков, ожидающих загрузку.")
            return

        self.ensure_elenveil_directories()
        self.start_button.setEnabled(False)
        self.create_playlist_button.setEnabled(False)
        self.active_spotify_playlist_index = self.selected_playlist_index
        playlist.is_downloading = True
        self.playlist_item_widgets[self.selected_playlist_index].set_loading(True)

        worker = SpotDLDownloadWorker(
            [
                (
                    index,
                    playlist.tracks[index].spotify_url,
                    playlist.tracks[index].title,
                    playlist.tracks[index].artists,
                    playlist.tracks[index].album,
                )
                for index in downloadable_indexes
            ],
            self.music_library_dir,
            self.spotify_credentials.get("client_id", ""),
            self.spotify_credentials.get("client_secret", ""),
            self.ffmpeg_location,
        )
        thread = QThread(self)
        self.spotify_download_worker = worker
        self.spotify_download_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.track_started.connect(self.on_spotify_track_download_started)
        worker.track_finished.connect(self.on_spotify_track_download_finished)
        worker.failed.connect(self.on_spotify_track_download_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_spotify_track_downloads_finished)
        thread.start()

    def on_spotify_track_download_started(self, track_index: int) -> None:
        if self.active_spotify_playlist_index is None:
            return
        playlist = self.playlists[self.active_spotify_playlist_index]
        if not (0 <= track_index < len(playlist.tracks)):
            return
        track = playlist.tracks[track_index]
        track.status = STATUS_DOWNLOADING
        track.progress = 0.0
        track.error = ""
        self.persist_playlist(self.active_spotify_playlist_index)
        self.refresh_experimental_source_view()
        self.update_start_button_state()

    def on_spotify_track_download_finished(
        self,
        track_index: int,
        status: str,
        local_file_path: str,
        error_text: str,
    ) -> None:
        if self.active_spotify_playlist_index is None:
            return
        playlist = self.playlists[self.active_spotify_playlist_index]
        if not (0 <= track_index < len(playlist.tracks)):
            return
        track = playlist.tracks[track_index]
        track.status = status
        track.progress = 100.0 if status == STATUS_DONE else 0.0
        track.local_file_path = local_file_path
        track.error = error_text
        self.persist_playlist(self.active_spotify_playlist_index)
        self.refresh_experimental_source_view()
        self.update_start_button_state()

    def on_spotify_track_download_failed(self, error_text: str) -> None:
        QMessageBox.warning(
            self,
            "spotdl",
            error_text or "Не удалось запустить загрузку Spotify-треков через spotdl.",
        )
        self.update_start_button_state()

    def on_spotify_track_downloads_finished(self) -> None:
        summary_playlist = None
        if self.active_spotify_playlist_index is not None and 0 <= self.active_spotify_playlist_index < len(self.playlists):
            summary_playlist = self.playlists[self.active_spotify_playlist_index]
            summary_playlist.is_downloading = False
            self.playlist_item_widgets[self.active_spotify_playlist_index].set_loading(False)
            self.persist_playlist(self.active_spotify_playlist_index)
        self.spotify_download_thread = None
        self.spotify_download_worker = None
        self.active_spotify_playlist_index = None
        self.create_playlist_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.refresh_local_music_tracks()
        self.refresh_experimental_source_view()
        self.update_start_button_state()
        if summary_playlist is not None:
            downloaded = sum(1 for track in summary_playlist.tracks if track.status == STATUS_DONE)
            skipped = sum(1 for track in summary_playlist.tracks if track.status == STATUS_SKIPPED)
            failed = sum(1 for track in summary_playlist.tracks if track.status == STATUS_ERROR)
            if skipped or failed:
                QMessageBox.information(
                    self,
                    "spotdl",
                    f"Загрузка плейлиста завершена.\n\n"
                    f"Загружено: {downloaded}\n"
                    f"Пропущено: {skipped}\n"
                    f"Ошибок: {failed}",
                )

    def start_next_download(self) -> None:
        next_index = next(
            (index for index, task in enumerate(self.tasks) if task.status == STATUS_PENDING),
            None,
        )
        if next_index is None:
            self.active_download_index = None
            self.download_thread = None
            self.start_button.setEnabled(any(task.status == STATUS_PENDING for task in self.tasks))
            return

        task = self.tasks[next_index]
        metadata_overrides = {
            "title": task.meta_title,
            "artist": task.meta_author,
            "album_artist": task.meta_group,
            "album": task.meta_album,
        }
        worker = DownloadWorker(
            next_index,
            task.url,
            self.output_dir,
            metadata_overrides,
            task.meta_cover_path,
            self.ffmpeg_location,
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
        if self.selected_task_index == index:
            self.update_metadata_panel()

    def on_download_progress(self, index: int, percent: float) -> None:
        task = self.tasks[index]
        task.progress = percent
        self.refresh_card(index)
        if self.selected_task_index == index:
            self.update_metadata_panel()

    def on_download_finished(self, index: int, success: bool, error_text: str) -> None:
        task = self.tasks[index]
        task.status = STATUS_DONE if success else STATUS_ERROR
        task.progress = 100.0 if success else task.progress
        task.error = error_text
        self.refresh_card(index)
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
        for card in self.spotify_track_cards:
            card.tick_status_icon_animation()

    def refresh_card(self, index: int, pulse: bool = False) -> None:
        self.cards[index].update_from_task(self.tasks[index], pulse and self.animation_phase)
