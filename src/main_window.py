import os
import shutil
import subprocess
import urllib.request

import yt_dlp
from PyQt6.QtCore import QEvent, QSize, Qt, QThread, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
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
    QMenu,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .dialogs import ExperimentalImportDialog, MetadataDialog
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
from .music_paths import (
    build_music_file_path,
    build_music_output_template,
    ensure_unique_music_file_path,
)
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
from .paths import resource_path
from .playlist_storage import delete_playlist, load_playlists, save_playlist
from .settings import load_elenveil_root_dir, save_elenveil_root_dir
from .widgets import (
    AddCard,
    DownloadCard,
    PlaylistListItemWidget,
    RemoteTrackCard,
)
from .workers import (
    DownloadWorker,
    MetadataWorker,
    YouTubePlaylistDownloadWorker,
    YouTubePlaylistWorker,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Elenveil")
        self.resize(1180, 720)
        self.startup_root_dir_warning = ""

        self.tasks: list[DownloadTask] = []
        self.cards: list[DownloadCard] = []
        self.playlists: list[PlaylistEntry] = []
        self.local_music_tracks: list[LocalMusicTrack] = []
        self.remote_track_cards: list[RemoteTrackCard] = []
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
        self.new_track_icon = QIcon()
        self.import_icon = QIcon()
        self.start_icon = QIcon()
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
        self.active_download_index: int | None = None
        self.selected_task_index: int | None = None
        self.selected_experimental_track_index: int | None = None
        self.selected_experimental_track_indexes: set[int] = set()
        self.experimental_selection_anchor_index: int | None = None
        self.selected_playlist_index: int | None = None
        self.experimental_source_mode = "none"
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
        self.experimental_footer_widget.setFixedHeight(22)
        self.experimental_footer_layout = QHBoxLayout()
        self.experimental_footer_layout.setContentsMargins(8, 0, 8, 0)
        self.experimental_footer_layout.setSpacing(8)
        self.experimental_footer_widget.setLayout(self.experimental_footer_layout)

        self.sort_date_button = self.create_text_header_button("")
        self.sort_title_button = self.create_text_header_button("")
        self.sort_date_button.clicked.connect(lambda: self.on_sort_requested("date"))
        self.sort_title_button.clicked.connect(lambda: self.on_sort_requested("title"))
        self.update_sort_button_labels()
        self.sort_date_button.setIcon(self.sort_date_icon)
        self.sort_date_button.setIconSize(QSize(18, 18))
        self.sort_title_button.setIcon(self.sort_title_icon)
        self.sort_title_button.setIconSize(QSize(18, 18))
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
                self.new_track_button,
                self.import_button,
                self.start_button,
            ],
            [
                self.delete_files_checkbox,
                self.sort_date_button,
                self.sort_title_button,
            ],
        )
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
        tracks_layout.addWidget(self.playlist_tracks_scroll)

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
        experimental_page_layout.addWidget(self.experimental_footer_widget)
        layout.addWidget(self.experimental_page)

        self.setCentralWidget(root)
        self.playlist_list.currentRowChanged.connect(self.on_playlist_selected)
        self.restore_persisted_playlists()
        self.relayout_status_widgets()
        self.update_metadata_panel()
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()
        self.show_all_music()
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

    def is_dark_theme(self) -> bool:
        palette = self.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        text_color = palette.color(QPalette.ColorRole.WindowText)
        return text_color.lightness() > window_color.lightness()

    def themed_icon_path(self, base_name: str) -> str:
        suffix = "light" if self.is_dark_theme() else "dark"
        themed_path = resource_path("assets", "icons", f"{base_name}_{suffix}.svg")
        if os.path.exists(themed_path):
            return themed_path
        return resource_path("assets", "icons", f"{base_name}.svg")

    def theme_colors(self) -> dict[str, str]:
        if self.is_dark_theme():
            return {
                "button_bg": "#2e3136",
                "button_hover": "#373b43",
                "button_border": "#3b3f46",
                "button_disabled_bg": "#2a2d33",
                "button_disabled_border": "#353941",
                "button_disabled_text": "#8b93a0",
                "panel_bg": "#1c2026",
                "panel_border": "#343941",
                "list_bg": "#20242a",
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

    def create_text_header_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setFixedHeight(36)
        self.apply_header_button_style(button)
        return button

    def create_section_panel(
        self,
        title: str,
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
        title_label = QLabel(title)
        frame.section_title_label = title_label
        header_row.addWidget(title_label)
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

    def apply_theme(self) -> None:
        colors = self.theme_colors()
        self.experimental_page.setStyleSheet("background:transparent; border:none;")
        self.experimental_footer_widget.setStyleSheet("background:transparent; border:none;")
        self.scroll_area.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        self.cards_container.setStyleSheet("background:transparent; border:none;")
        self.playlist_tracks_scroll.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }"
        )
        self.playlist_tracks_container.setStyleSheet("background:transparent; border:none;")
        for button in [
            self.select_elenveil_root_button,
            self.open_music_folder_button,
            self.create_playlist_button,
            self.import_button,
            self.new_track_button,
            self.start_button,
        ]:
            self.apply_icon_button_style(button)
        for button in [self.sort_date_button, self.sort_title_button]:
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
            "QListWidget::item { padding:0; margin:0 0 8px 0; border:none; }"
            "QListWidget::item:selected { background:transparent; }"
        )
        self.playlist_tracks_empty.setStyleSheet(
            f"font-size:14px; color:{colors['text_muted']}; padding:24px; background:transparent; border:none;"
        )
        for frame in [self.playlists_panel, self.tracks_panel, self.metadata_panel]:
            self.apply_section_panel_style(frame)
        for key, value_label in self.metadata_values.items():
            value_label.setStyleSheet(
                f"font-size:13px; color:{colors['text_primary']}; background:transparent; border:none;"
            )
        for layout_index in range(self.metadata_panel.layout().count()):
            item = self.metadata_panel.layout().itemAt(layout_index)
            widget = item.widget()
            if isinstance(widget, QLabel) and widget not in self.metadata_values.values():
                widget.setStyleSheet(
                    f"font-size:12px; color:{colors['text_muted']}; font-weight:700; background:transparent; border:none;"
                )
        for widget in self.playlist_item_widgets:
            widget.apply_theme(self.is_dark_theme())
        for card in self.remote_track_cards:
            card.apply_theme(self.is_dark_theme())
        for card in self.cards:
            card.apply_theme(self.is_dark_theme())
        self.add_card.apply_theme(self.is_dark_theme())

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
        if self.experimental_source_mode == "all_music":
            self.render_experimental_tracks(
                self.get_sorted_experimental_tracks(self.local_music_tracks)
            )
        elif (
            self.experimental_source_mode == "playlist"
            and self.selected_playlist_index is not None
        ):
            playlist = self.playlists[self.selected_playlist_index]
            self.render_experimental_tracks(
                self.get_sorted_experimental_tracks(playlist.tracks)
            )

    def get_sorted_experimental_tracks(
        self,
        tracks: list[RemoteTrack] | list[LocalMusicTrack],
    ) -> list[RemoteTrack] | list[LocalMusicTrack]:
        if self.sort_field == "date" and self.experimental_source_mode == "playlist":
            return list(tracks) if self.sort_ascending else list(reversed(tracks))

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
        if self.experimental_source_mode == "all_music":
            tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
            if tracks and (
                self.selected_experimental_track_index is None
                or self.selected_experimental_track_index >= len(tracks)
            ):
                self.selected_experimental_track_index = 0
            self.render_experimental_tracks(tracks)
            self.update_metadata_panel()
            return
        if (
            self.experimental_source_mode == "playlist"
            and self.selected_playlist_index is not None
        ):
            playlist = self.playlists[self.selected_playlist_index]
            tracks = self.get_sorted_experimental_tracks(playlist.tracks)
            if tracks and (
                self.selected_experimental_track_index is None
                or self.selected_experimental_track_index >= len(tracks)
            ):
                self.selected_experimental_track_index = 0
            self.render_experimental_tracks(tracks)
            self.update_metadata_panel()

    def update_delete_files_checkbox_visibility(self) -> None:
        visible = self.experimental_source_mode == "playlist"
        self.delete_files_checkbox.setVisible(visible)

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

    def refresh_local_music_tracks(self) -> None:
        self.ensure_elenveil_directories()
        self.local_music_tracks = scan_music_directory(self.music_library_dir)
        self.sync_remote_playlists_with_library()

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
        for local_track in self.local_music_tracks:
            title_key = self.normalize_track_text(local_track.title)
            if not title_key:
                continue
            local_tracks_by_title.setdefault(title_key, []).append(local_track)

        changed = False
        for track in playlist.tracks:
            title_key = self.normalize_track_text(track.title)
            candidates = local_tracks_by_title.get(title_key, [])
            matched_track = next(
                (
                    local_track
                    for local_track in candidates
                    if self.remote_track_matches_local(track, local_track)
                ),
                None,
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
            playlist_index = self.playlists.index(playlist) if playlist in self.playlists else -1
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

    def sync_remote_playlists_with_library(self) -> None:
        for index, playlist in enumerate(self.playlists):
            if playlist.source != "youtube":
                continue
            changed = self.sync_remote_playlist_with_library(playlist, persist=False)
            if changed:
                self.persist_playlist(index)
            if index < len(self.playlist_item_widgets):
                self.update_playlist_item_status(index)

    def show_all_music(self) -> None:
        self.experimental_source_mode = "all_music"
        self.selected_playlist_index = None
        self.clear_experimental_track_selection()
        self.all_music_button.setChecked(True)
        self.playlist_list.blockSignals(True)
        self.playlist_list.setCurrentRow(-1)
        self.playlist_list.blockSignals(False)
        for widget in self.playlist_item_widgets:
            widget.set_selected(False)
        self.refresh_local_music_tracks()
        tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
        if tracks:
            self.selected_experimental_track_index = 0
            self.selected_experimental_track_indexes = {0}
            self.experimental_selection_anchor_index = 0
        self.render_experimental_tracks(tracks)
        self.update_metadata_panel()
        self.update_delete_files_checkbox_visibility()
        self.update_start_button_state()

    def relayout_status_widgets(self) -> None:
        self.clear_layout(self.experimental_footer_layout)
        self.experimental_footer_layout.addStretch(1)
        self.experimental_footer_layout.addWidget(
            self.ffmpeg_status_label,
            0,
            Qt.AlignmentFlag.AlignCenter,
        )
        self.experimental_footer_layout.addStretch(1)

    def clear_layout(self, layout: QHBoxLayout | QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def open_elenveil_music_folder(self) -> None:
        self.ensure_elenveil_directories()
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.elenveil_root_dir))

    def default_elenveil_root_dir(self) -> str:
        return os.path.join(os.path.expanduser("~"), "Music", "Elenveil")

    def initialize_elenveil_root_dir(
        self, preferred_root_dir: str, fallback_root_dir: str
    ) -> None:
        try:
            self.set_elenveil_root_dir(preferred_root_dir, persist=False)
            return
        except OSError:
            preferred_path = os.path.abspath(os.path.expanduser(preferred_root_dir.strip()))
            fallback_path = os.path.abspath(os.path.expanduser(fallback_root_dir.strip()))
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
        self.show_all_music()

    def restore_persisted_playlists(self) -> None:
        self.ensure_elenveil_directories()
        persisted = load_playlists(self.playlists_dir)
        persisted = [playlist for playlist in persisted if playlist.source == "youtube"]
        persisted.extend(
            load_manual_playlists(self.playlists_dir, self.music_library_dir)
        )
        if not persisted:
            return
        self.playlists = list(persisted)
        self.rebuild_playlist_list()
        self.sync_remote_playlists_with_library()

    def rebuild_playlist_list(self) -> None:
        self.playlist_item_widgets = []
        self.playlist_list.clear()
        for playlist in self.playlists:
            self.add_playlist_list_item(playlist)

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

    def add_playlist_list_item(self, playlist: PlaylistEntry) -> int:
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 44))
        self.playlist_list.addItem(item)
        widget = PlaylistListItemWidget(
            playlist.name,
            self.playlist_loading_icon,
            self.playlist_ready_icon,
        )
        widget.apply_theme(self.is_dark_theme())
        widget.set_loading(playlist.is_loading or playlist.is_downloading)
        row = self.playlist_list.count() - 1
        widget.clicked.connect(lambda row=row: self.playlist_list.setCurrentRow(row))
        widget.delete_requested.connect(
            lambda row=row: self.on_playlist_delete_requested(row)
        )
        self.playlist_item_widgets.append(widget)
        self.playlist_list.setItemWidget(item, widget)
        self.update_playlist_item_status(row)
        return row

    def get_playlist_ready_status_icon(self, playlist: PlaylistEntry) -> QIcon:
        if playlist.tracks and all(
            getattr(track, "status", STATUS_PENDING) == STATUS_DONE
            for track in playlist.tracks
        ):
            return self.status_icons[STATUS_DONE]
        return self.playlist_ready_icon

    def update_playlist_item_status(self, row: int) -> None:
        if not (0 <= row < len(self.playlists)) or row >= len(self.playlist_item_widgets):
            return
        playlist = self.playlists[row]
        widget = self.playlist_item_widgets[row]
        widget.set_ready_icon(self.get_playlist_ready_status_icon(playlist))
        widget.set_loading(playlist.is_loading or playlist.is_downloading)

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
        elif playlist.source == "youtube":
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

        def create_source_button(icon: QIcon, tooltip: str) -> QPushButton:
            button = QPushButton()
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.setFixedSize(52, 52)
            button.setStyleSheet(
                "QPushButton { background:#2e3136; border:1px solid #3b3f46; border-radius:10px; }"
                "QPushButton:hover { background:#373b43; }"
                "QPushButton:pressed { background:#2a2d33; }"
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
        row = self.add_playlist_list_item(playlist)
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
        self.pending_playlist_index = self.add_loading_playlist_entry(
            playlist_url,
            "youtube",
        )
        self.start_youtube_playlist_import(playlist_url)

    def start_youtube_playlist_import(self, playlist_url: str) -> None:
        worker = YouTubePlaylistWorker(playlist_url)
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
        self.all_music_button.setChecked(False)
        for index, widget in enumerate(self.playlist_item_widgets):
            widget.set_selected(index == row)
        if row < 0 or row >= len(self.playlists):
            self.experimental_source_mode = "none"
            self.selected_playlist_index = None
            self.clear_experimental_track_selection()
            self.render_experimental_tracks([])
            self.update_metadata_panel()
            self.update_delete_files_checkbox_visibility()
            return
        self.experimental_source_mode = "playlist"
        if self.playlists[row].source == "manual":
            self.playlists[row] = load_manual_playlist(
                self.playlists[row].source_url, self.music_library_dir
            )
            self.playlist_item_widgets[row].set_title(self.playlists[row].name)
        self.selected_playlist_index = row
        tracks = self.get_sorted_experimental_tracks(self.playlists[row].tracks)
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
        row = self.add_playlist_list_item(playlist)
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

    def get_current_experimental_tracks(
        self,
    ) -> list[RemoteTrack] | list[LocalMusicTrack]:
        if self.experimental_source_mode == "all_music":
            return self.get_sorted_experimental_tracks(self.local_music_tracks)
        if (
            self.experimental_source_mode == "playlist"
            and self.selected_playlist_index is not None
            and 0 <= self.selected_playlist_index < len(self.playlists)
        ):
            return self.get_sorted_experimental_tracks(
                self.playlists[self.selected_playlist_index].tracks
            )
        return []

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

    def get_selected_experimental_tracks(self) -> list[RemoteTrack | LocalMusicTrack]:
        tracks = self.get_current_experimental_tracks()
        return [tracks[index] for index in self.get_selected_experimental_track_indexes()]

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

    def render_experimental_tracks(
        self,
        tracks: list[RemoteTrack] | list[LocalMusicTrack],
    ) -> None:
        while self.playlist_tracks_layout.count():
            item = self.playlist_tracks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

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
                track, track_index, self.status_icons, self.metadata_icon
            )
            card.apply_theme(self.is_dark_theme())
            card.selected.connect(self.on_remote_track_selected)
            card.context_requested.connect(self.on_remote_track_context_requested)
            card.delete_requested.connect(self.on_experimental_track_delete_requested)
            card.metadata_requested.connect(
                self.on_experimental_track_metadata_requested
            )
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

    def on_remote_track_context_requested(self, index: int, global_pos) -> None:
        if index not in self.selected_experimental_track_indexes:
            self.set_single_experimental_track_selection(index)

        menu = QMenu(self)
        selected_indexes = self.get_selected_experimental_track_indexes()
        is_single_selection = len(selected_indexes) == 1

        metadata_action = menu.addAction(
            "Изменить метаданные"
            if is_single_selection
            else "Совместные метаданные"
        )
        add_to_playlist_action = menu.addAction("Добавить в плейлист")
        delete_action = menu.addAction("Удалить")

        selected_action = menu.exec(global_pos)
        if selected_action == metadata_action:
            if is_single_selection:
                self.on_experimental_track_metadata_requested(selected_indexes[0])
            else:
                self.edit_shared_metadata_for_selected_tracks()
            return
        if selected_action == add_to_playlist_action:
            self.add_selected_tracks_to_manual_playlist()
            return
        if selected_action == delete_action:
            self.delete_selected_experimental_tracks()

    def on_experimental_track_delete_requested(self, index: int) -> None:
        if self.experimental_source_mode == "all_music":
            self.delete_track_from_all_music(index)
            return
        if self.experimental_source_mode == "playlist":
            self.delete_track_from_selected_playlist(index)

    def on_experimental_track_metadata_requested(self, index: int) -> None:
        if self.experimental_source_mode == "all_music":
            tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
        elif (
            self.experimental_source_mode == "playlist"
            and self.selected_playlist_index is not None
        ):
            tracks = self.get_sorted_experimental_tracks(
                self.playlists[self.selected_playlist_index].tracks
            )
        else:
            return

        if not (0 <= index < len(tracks)):
            return
        track = tracks[index]
        file_path = (
            track.file_path
            if isinstance(track, LocalMusicTrack)
            else track.local_file_path
        )
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
        dialog = MetadataDialog(
            self, dialog_task, self.cover_pick_icon, self.cover_reset_icon
        )
        dialog.url_edit.setReadOnly(True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values, cover_path, cover_mode = dialog.get_metadata_values()
        resolved_values = self.resolve_metadata_values_for_track(track, values)
        try:
            apply_mp3_metadata(
                file_path,
                title=resolved_values["title"],
                author=resolved_values["author"],
                group=resolved_values["group"],
                album=resolved_values["album"],
                cover_mode=cover_mode,
                cover_path=cover_path,
            )
        except Exception as exc:
            QMessageBox.warning(
                self, "Метаданные", f"Не удалось обновить mp3-метаданные:\n{exc}"
            )
            return

        try:
            final_file_path = self.relocate_music_file_after_metadata_edit(
                file_path,
                title=resolved_values["title"],
                author=resolved_values["author"],
                album=resolved_values["album"],
            )
        except Exception as exc:
            QMessageBox.warning(
                self, "Метаданные", f"Не удалось переместить mp3-файл:\n{exc}"
            )
            return

        self.refresh_experimental_track_sources_after_metadata_edit(final_file_path)

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
            "group": values["group"].strip(),
            "album": values["album"].strip() or track.album,
        }

    def refresh_experimental_track_sources_after_metadata_edit(
        self, file_path: str
    ) -> None:
        resolved_path = os.path.realpath(file_path)
        self.refresh_local_music_tracks()

        for playlist_index, playlist in enumerate(self.playlists):
            if playlist.source == "manual":
                self.playlists[playlist_index] = load_manual_playlist(
                    playlist.source_url,
                    self.music_library_dir,
                )
                continue

            if playlist.source != "youtube":
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
                if (
                    isinstance(track, RemoteTrack)
                    and track.local_file_path
                    and os.path.realpath(track.local_file_path) == resolved_path
                ):
                    track.title = refreshed.title
                    track.artists = refreshed.artists
                    track.album = refreshed.album
                    track.thumbnail_data = refreshed.thumbnail_data
                    changed = True
            if changed:
                self.persist_playlist(playlist_index)

        self.refresh_experimental_source_view()

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
        selected_tracks = self.get_selected_experimental_tracks()
        file_backed_tracks: list[tuple[RemoteTrack | LocalMusicTrack, str]] = []
        for track in selected_tracks:
            file_path = (
                track.file_path
                if isinstance(track, LocalMusicTrack)
                else track.local_file_path
            )
            if file_path and os.path.exists(file_path):
                file_backed_tracks.append((track, file_path))

        if not file_backed_tracks:
            QMessageBox.information(
                self,
                "Совместные метаданные",
                "Для выбранных треков не найдено доступных mp3-файлов.",
            )
            return

        def common_value(values: list[str]) -> str:
            normalized = [value.strip() for value in values]
            return normalized[0] if normalized and all(value == normalized[0] for value in normalized) else ""

        selected_count = len(file_backed_tracks)
        tracks_only = [track for track, _ in file_backed_tracks]
        first_track = tracks_only[0]
        dialog_task = DownloadTask(
            url=f"Выбрано треков: {selected_count}",
            title=common_value([track.title for track in tracks_only]),
            channel=common_value([track.artists for track in tracks_only]),
            thumbnail_data=first_track.thumbnail_data,
            meta_title=common_value([track.title for track in tracks_only]),
            meta_author=common_value([track.artists for track in tracks_only]),
            meta_group="",
            meta_album=common_value([track.album for track in tracks_only]),
        )
        dialog = MetadataDialog(
            self, dialog_task, self.cover_pick_icon, self.cover_reset_icon
        )
        dialog.setWindowTitle("Совместные метаданные")
        dialog.url_edit.setReadOnly(True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values, cover_path, cover_mode = dialog.get_metadata_values()
        updated_file_paths: list[str] = []
        for track, file_path in file_backed_tracks:
            resolved_values = self.resolve_metadata_values_for_track(track, values)
            try:
                apply_mp3_metadata(
                    file_path,
                    title=resolved_values["title"],
                    author=resolved_values["author"],
                    group=resolved_values["group"],
                    album=resolved_values["album"],
                    cover_mode=cover_mode,
                    cover_path=cover_path,
                )
                final_file_path = self.relocate_music_file_after_metadata_edit(
                    file_path,
                    title=resolved_values["title"],
                    author=resolved_values["author"],
                    album=resolved_values["album"],
                )
                updated_file_paths.append(final_file_path)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Совместные метаданные",
                    f"Не удалось обновить mp3-метаданные:\n{exc}",
                )
                return

        for file_path in updated_file_paths:
            self.refresh_experimental_track_sources_after_metadata_edit(file_path)

    def delete_selected_experimental_tracks(self) -> None:
        selected_indexes = self.get_selected_experimental_track_indexes()
        if not selected_indexes:
            return
        if self.experimental_source_mode == "all_music":
            self.delete_tracks_from_all_music(selected_indexes)
            return
        if self.experimental_source_mode == "playlist":
            self.delete_tracks_from_selected_playlist(selected_indexes)

    def delete_track_from_all_music(self, index: int) -> None:
        self.delete_tracks_from_all_music([index])

    def delete_tracks_from_all_music(self, indexes: list[int]) -> None:
        tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
        selected_tracks = [tracks[index] for index in indexes if 0 <= index < len(tracks)]
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
        refreshed_tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
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
        selected_tracks = [tracks[index] for index in indexes if 0 <= index < len(tracks)]
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
        if self.experimental_source_mode == "all_music":
            track = (
                self.get_sorted_experimental_tracks(self.local_music_tracks)[
                    self.selected_experimental_track_index
                ]
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
                if self.selected_playlist_index is not None
                and 0 <= self.selected_playlist_index < len(self.playlists)
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
                    track.source_url if isinstance(track, RemoteTrack) else track.file_path
                )
                if track
                else "—",
                "Автор": track.artists if track else "—",
                "Альбом": track.album if track else "—",
                "Статус": (
                    self.get_track_status_title(track)
                    if track
                    else (
                        "Подгрузка плейлиста"
                        if playlist and playlist.is_loading
                        else (playlist.note or "Нет треков")
                        if playlist
                        else "Нет треков"
                    )
                ),
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
        self.new_track_icon = self.add_playlist_icon
        self.import_icon = QIcon(self.themed_icon_path("file"))
        self.start_icon = QIcon(self.themed_icon_path("mass_download"))
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
        if hasattr(self, "new_track_button"):
            self.new_track_button.setIcon(self.new_track_icon)
            self.new_track_button.setIconSize(QSize(18, 18))
        if hasattr(self, "import_button"):
            self.import_button.setIcon(self.import_icon)
            self.import_button.setIconSize(QSize(18, 18))
        if hasattr(self, "start_button"):
            self.start_button.setIcon(self.start_icon)
            self.start_button.setIconSize(QSize(18, 18))
        if hasattr(self, "sort_date_button"):
            self.sort_date_button.setIcon(self.sort_date_icon)
            self.sort_date_button.setIconSize(QSize(18, 18))
        if hasattr(self, "sort_title_button"):
            self.sort_title_button.setIcon(self.sort_title_icon)
            self.sort_title_button.setIconSize(QSize(18, 18))
        for widget in self.playlist_item_widgets:
            widget.set_loading_icon(self.playlist_loading_icon)
            widget.set_ready_icon(self.playlist_ready_icon)
        for card in self.cards:
            card.set_metadata_icon(self.metadata_icon)
            card.set_status_icons(self.status_icons)
        for card in self.remote_track_cards:
            card.set_status_icons(self.status_icons)
            card.set_metadata_icon(self.metadata_icon)

    def on_single_track_download_finished(
        self, index: int, success: bool, error_text: str
    ) -> None:
        del index
        if success:
            self.refresh_local_music_tracks()
            if self.experimental_source_mode == "all_music":
                tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
                self.selected_experimental_track_index = 0 if tracks else None
                self.render_experimental_tracks(tracks)
                self.update_metadata_panel()
            return
        QMessageBox.warning(
            self,
            "Новый трек",
            error_text or "Не удалось сохранить mp3 в папку music.",
        )

    def on_single_track_download_thread_finished(self) -> None:
        self.download_thread = None
        self.download_worker = None
        self.new_track_button.setEnabled(True)
        self.import_button.setEnabled(True)
        self.update_start_button_state()

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
        if self.experimental_source_mode == "all_music":
            tracks = self.get_sorted_experimental_tracks(self.local_music_tracks)
            if tracks and (
                self.selected_experimental_track_index is None
                or self.selected_experimental_track_index >= len(tracks)
            ):
                self.selected_experimental_track_index = 0
            self.render_experimental_tracks(tracks)
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
            self, task, self.cover_pick_icon, self.cover_reset_icon
        )
        if metadata_dialog.exec() != QDialog.DialogCode.Accepted:
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

    def fetch_metadata_for_single_track(self, url: str) -> DownloadTask | None:
        task = DownloadTask(url=url)
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
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
        )
        thread = QThread(self)
        self.download_worker = worker
        self.download_thread = thread
        self.new_track_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.start_button.setEnabled(False)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.on_single_track_download_finished)
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
        task.meta_title = (
            task.meta_title or extracted_meta.get("title") or title
        ).strip()
        task.meta_author = (
            task.meta_author or extracted_meta.get("author") or channel
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
        self.start_button.setEnabled(
            any(task.status == STATUS_PENDING for task in self.tasks)
        )

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
            QMessageBox.information(
                self, "Старт", "Выберите плейлист в левой панели."
            )
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
        playlist.is_downloading = True
        self.playlist_item_widgets[self.selected_playlist_index].set_loading(True)

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
        )
        thread = QThread(self)
        self.youtube_download_worker = worker
        self.youtube_download_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.track_started.connect(self.on_remote_track_download_started)
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
        self.refresh_experimental_source_view()
        self.update_start_button_state()

    def on_youtube_track_download_failed(self, error_text: str) -> None:
        QMessageBox.warning(
            self,
            "YouTube",
            error_text or "Не удалось запустить загрузку YouTube-треков.",
        )
        self.update_start_button_state()

    def on_youtube_track_downloads_finished(self) -> None:
        summary_playlist = None
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
        self.create_playlist_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.refresh_local_music_tracks()
        self.refresh_experimental_source_view()
        self.update_start_button_state()
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
        for card in self.remote_track_cards:
            card.tick_status_icon_animation()

    def refresh_card(self, index: int, pulse: bool = False) -> None:
        self.cards[index].update_from_task(
            self.tasks[index], pulse and self.animation_phase
        )
