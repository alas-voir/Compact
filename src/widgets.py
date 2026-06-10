from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)

from .models import (
    LocalMusicTrack,
    PlaylistEntry,
    RemoteTrack,
    STATUS_DONE,
    STATUS_DOWNLOADING,
    STATUS_ERROR,
    STATUS_META_LOADING,
    STATUS_PENDING,
    STATUS_SKIPPED,
    DownloadTask,
)


class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(42, 24)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.dark_theme = True

    def sizeHint(self) -> QSize:
        return QSize(42, 24)

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def set_dark_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        track_rect = self.rect().adjusted(1, 3, -1, -3)
        radius = track_rect.height() / 2
        if self.dark_theme:
            track_color = QColor("#5f9ee6") if self.isChecked() else QColor("#454b55")
            knob_color = QColor("#f2f5fa")
        else:
            track_color = QColor("#4e88d9") if self.isChecked() else QColor("#b8c0cc")
            knob_color = QColor("#ffffff")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, radius, radius)

        knob_diameter = track_rect.height() - 4
        knob_y = track_rect.y() + 2
        knob_x = track_rect.right() - knob_diameter - 2 if self.isChecked() else track_rect.x() + 2
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_x, knob_y, knob_diameter, knob_diameter)
        painter.end()


class PlaylistListItemWidget(QFrame):
    clicked = pyqtSignal()
    delete_requested = pyqtSignal()

    def __init__(self, title: str, loading_icon: QIcon, ready_icon: QIcon) -> None:
        super().__init__()
        self.loading_icon = loading_icon
        self.ready_icon = ready_icon
        self.rotation_angle = 0
        self.is_loading = False
        self.is_selected = False
        self.dark_theme = True
        self.setObjectName("playlist_item")
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-size:13px; font-weight:700; color:#eef2f7; background:transparent; border:none;"
        )
        layout.addWidget(self.title_label, 1)

        self.status_icon_label = QLabel()
        self.status_icon_label.setFixedSize(18, 18)
        self.status_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon_label.setStyleSheet("background:transparent; border:none;")
        layout.addWidget(self.status_icon_label, 0, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.delete_button = QToolButton()
        self.delete_button.setText("●")
        self.delete_button.setToolTip("Удалить плейлист")
        self.delete_button.setFixedSize(18, 18)
        self.delete_button.setStyleSheet(
            "QToolButton {"
            "background:transparent;"
            "color:#ff4d5a;"
            "border:none;"
            "font-size:14px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            "QToolButton:hover { color:#ff6570; }"
        )
        self.delete_button.clicked.connect(self.delete_requested.emit)
        layout.addWidget(self.delete_button, 0, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.apply_theme(True)
        self.set_loading(False)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_loading_icon(self, icon: QIcon) -> None:
        self.loading_icon = icon
        self.update_status_icon()

    def set_ready_icon(self, icon: QIcon) -> None:
        self.ready_icon = icon
        self.update_status_icon()

    def set_loading(self, is_loading: bool) -> None:
        self.is_loading = is_loading
        if not is_loading:
            self.rotation_angle = 0
        self.update_status_icon()

    def set_selected(self, is_selected: bool) -> None:
        self.is_selected = is_selected
        self.update_style()

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        title_color = "#eef2f7" if is_dark else "#1e2630"
        self.title_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{title_color}; background:transparent; border:none;"
        )
        self.delete_button.setStyleSheet(
            "QToolButton {"
            "background:transparent;"
            "color:#ff4d5a;"
            "border:none;"
            "font-size:14px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            "QToolButton:hover { color:#ff6570; }"
        )
        self.update_style()

    def update_style(self) -> None:
        if self.dark_theme:
            background = "#355680" if self.is_selected else "#252a31"
            border = "#4b74a7" if self.is_selected else "#30353d"
        else:
            background = "#d9e8fb" if self.is_selected else "#ffffff"
            border = "#6e99d8" if self.is_selected else "#d0d7e2"
        self.setStyleSheet(
            f"#playlist_item {{ background:{background}; border:1px solid {border}; border-radius:8px; }}"
        )

    def update_status_icon(self) -> None:
        icon = self.loading_icon if self.is_loading else self.ready_icon
        if icon.isNull():
            self.status_icon_label.clear()
            return
        pixmap = icon.pixmap(QSize(16, 16))
        if self.is_loading and self.rotation_angle:
            size = 16
            rotated = QPixmap(size, size)
            rotated.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rotated)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.translate(size / 2, size / 2)
            painter.rotate(self.rotation_angle)
            painter.translate(-size / 2, -size / 2)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            pixmap = rotated
        self.status_icon_label.setPixmap(pixmap)

    def tick_animation(self) -> None:
        if self.is_loading:
            self.rotation_angle = (self.rotation_angle + 30) % 360
            self.update_status_icon()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class RemoteTrackCard(QFrame):
    selected = pyqtSignal(int, int)
    context_requested = pyqtSignal(int, object)
    delete_requested = pyqtSignal(int)
    metadata_requested = pyqtSignal(int)

    def __init__(
        self,
        track: RemoteTrack | LocalMusicTrack,
        track_index: int,
        status_icons: dict[str, QIcon],
        metadata_icon: QIcon,
    ) -> None:
        super().__init__()
        self.track_index = track_index
        self.is_selected = False
        self.status_icons = status_icons
        self.current_status = STATUS_PENDING
        self.status_rotation_angle = 0
        self.dark_theme = True
        self.setObjectName("remote_track_card")
        self.setFixedHeight(108)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        self.position_label = QLabel(str(track_index + 1))
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position_label.setFixedWidth(26)
        self.position_label.setStyleSheet(
            "font-size:13px; font-weight:700; color:#7f8794; background:transparent; border:none;"
        )
        layout.addWidget(self.position_label, 0, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.status_icon_label = QLabel()
        self.status_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon_label.setFixedSize(18, 18)
        self.status_icon_label.setStyleSheet("background:transparent; border:none;")
        self.status_icon_label.setParent(self)

        self.preview_label = QLabel("Нет\nобложки")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(78, 78)
        self.preview_label.setStyleSheet(
            "background:#303236; color:#aeb4bf; border-radius:8px; font-size:11px;"
        )
        layout.addWidget(self.preview_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        self.title_label = QLabel(track.title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            "font-size:14px; font-weight:700; color:#eef2f7; background:transparent; border:none;"
        )
        self.artist_label = QLabel(track.artists)
        self.artist_label.setWordWrap(True)
        self.artist_label.setStyleSheet(
            "font-size:12px; color:#b4bcc9; background:transparent; border:none;"
        )
        self.album_label = QLabel(track.album or "Без альбома")
        self.album_label.setWordWrap(True)
        self.album_label.setStyleSheet(
            "font-size:12px; color:#8f98a6; background:transparent; border:none;"
        )
        text_layout.addStretch(1)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.artist_label)
        text_layout.addWidget(self.album_label)
        text_layout.addStretch(1)
        layout.addLayout(text_layout, 1)

        self.delete_button = QToolButton()
        self.delete_button.setText("●")
        self.delete_button.setToolTip("Удалить трек")
        self.delete_button.setFixedSize(20, 20)
        self.delete_button.setStyleSheet(
            "QToolButton {"
            "background:transparent;"
            "color:#ff4d5a;"
            "border:none;"
            "font-size:15px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            "QToolButton:hover { color:#ff6570; }"
        )
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self.track_index))
        self.delete_button.setParent(self)

        self.metadata_button = QToolButton()
        self.metadata_button.setToolTip("Изменить метаданные")
        self.metadata_button.setAccessibleName("Изменить метаданные")
        self.metadata_button.setFixedSize(28, 28)
        self.metadata_button.setStyleSheet(
            "QToolButton {"
            "background:#32363d;"
            "border:1px solid #4a515c;"
            "border-radius:7px;"
            "}"
            "QToolButton:hover { background:#3b414b; }"
        )
        self.metadata_button.setIconSize(QSize(16, 16))
        self.set_metadata_icon(metadata_icon)
        self.metadata_button.clicked.connect(lambda: self.metadata_requested.emit(self.track_index))
        self.metadata_button.setParent(self)

        self.apply_theme(True)
        self.update_from_track(track)
        self.position_overlay_controls()

    def update_from_track(self, track: RemoteTrack | LocalMusicTrack) -> None:
        self.title_label.setText(track.title)
        self.artist_label.setText(track.artists)
        self.album_label.setText(track.album or "Без альбома")
        self.current_status = getattr(track, "status", STATUS_PENDING)
        self.update_status_icon(self.current_status)
        if track.thumbnail_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(track.thumbnail_data):
                scaled = pixmap.scaled(
                    self.preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)
                self.preview_label.setText("")
                return
        self.preview_label.clear()
        self.preview_label.setText("Нет\nобложки")

    def set_selected(self, is_selected: bool) -> None:
        self.is_selected = is_selected
        self.update_card_style()

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        primary = "#eef2f7" if is_dark else "#1e2630"
        secondary = "#b4bcc9" if is_dark else "#556170"
        tertiary = "#8f98a6" if is_dark else "#788292"
        preview_bg = "#303236" if is_dark else "#e5eaf0"
        preview_fg = "#aeb4bf" if is_dark else "#6d7785"
        metadata_bg = "#32363d" if is_dark else "#eef2f6"
        metadata_border = "#4a515c" if is_dark else "#c8d0dc"
        metadata_hover = "#3b414b" if is_dark else "#e3e8ef"
        self.position_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{tertiary}; background:transparent; border:none;"
        )
        self.preview_label.setStyleSheet(
            f"background:{preview_bg}; color:{preview_fg}; border-radius:8px; font-size:11px;"
        )
        self.title_label.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{primary}; background:transparent; border:none;"
        )
        self.artist_label.setStyleSheet(
            f"font-size:12px; color:{secondary}; background:transparent; border:none;"
        )
        self.album_label.setStyleSheet(
            f"font-size:12px; color:{tertiary}; background:transparent; border:none;"
        )
        self.metadata_button.setStyleSheet(
            "QToolButton {"
            f"background:{metadata_bg};"
            f"border:1px solid {metadata_border};"
            "border-radius:7px;"
            "}"
            f"QToolButton:hover {{ background:{metadata_hover}; }}"
        )
        self.delete_button.setStyleSheet(
            "QToolButton {"
            "background:transparent;"
            "color:#ff4d5a;"
            "border:none;"
            "font-size:15px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            "QToolButton:hover { color:#ff6570; }"
        )
        self.update_card_style()

    def update_card_style(self) -> None:
        if self.dark_theme:
            background = "#2a2d33"
            border_color = "#5f9ee6" if self.is_selected else "#3a3f48"
        else:
            background = "#ffffff"
            border_color = "#6e99d8" if self.is_selected else "#d0d7e2"
        self.setStyleSheet(
            f"#remote_track_card {{ background:{background}; border:1px solid {border_color}; border-radius:10px; }}"
        )

    def set_status_icons(self, status_icons: dict[str, QIcon]) -> None:
        self.status_icons = status_icons
        self.update_status_icon(self.current_status)

    def set_metadata_icon(self, icon: QIcon) -> None:
        if icon.isNull():
            self.metadata_button.setText("✎")
            self.metadata_button.setIcon(QIcon())
            return
        self.metadata_button.setText("")
        self.metadata_button.setIcon(icon)

    def update_status_icon(self, status: str | None = None) -> None:
        state = status if status is not None else STATUS_PENDING
        icon = self.status_icons.get(state) or self.status_icons.get(STATUS_PENDING)
        if icon is None or icon.isNull():
            self.status_icon_label.clear()
            return
        if state not in (STATUS_DOWNLOADING, STATUS_META_LOADING):
            self.status_rotation_angle = 0
        pixmap = icon.pixmap(QSize(16, 16))
        if state in (STATUS_DOWNLOADING, STATUS_META_LOADING) and self.status_rotation_angle:
            size = 16
            rotated = QPixmap(size, size)
            rotated.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rotated)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.translate(size / 2, size / 2)
            painter.rotate(self.status_rotation_angle)
            painter.translate(-size / 2, -size / 2)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            pixmap = rotated
        self.status_icon_label.setPixmap(pixmap)

    def tick_status_icon_animation(self) -> None:
        if self.current_status in (STATUS_DOWNLOADING, STATUS_META_LOADING):
            self.status_rotation_angle = (self.status_rotation_angle + 30) % 360
            self.update_status_icon(self.current_status)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.track_index, int(event.modifiers().value))
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(self.track_index, event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_overlay_controls()

    def position_overlay_controls(self) -> None:
        bottom_margin = 10
        status_x = 12 + (self.position_label.width() - self.status_icon_label.width()) // 2
        status_y = self.height() - self.status_icon_label.height() - bottom_margin
        self.status_icon_label.move(status_x, status_y)
        self.delete_button.move(self.width() - self.delete_button.width() - 12, 8)
        self.metadata_button.move(
            self.width() - self.metadata_button.width() - 12,
            self.height() - self.metadata_button.height() - 10,
        )


class DownloadCard(QFrame):
    metadata_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    selected = pyqtSignal(int)

    def __init__(
        self,
        task: DownloadTask,
        list_index: int,
        metadata_icon: QIcon,
        status_icons: dict[str, QIcon],
    ) -> None:
        super().__init__()
        self.list_index = list_index
        self.current_status = STATUS_META_LOADING
        self.status_icons = status_icons
        self.status_rotation_angle = 0
        self.is_selected = False
        self.dark_theme = True
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("card")
        self.setFixedHeight(132)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        left_layout.addStretch(1)

        self.position_label = QLabel(str(list_index + 1))
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position_label.setFixedWidth(26)
        self.position_label.setStyleSheet("font-size:13px; font-weight:700; color:#7f8794;")
        left_layout.addWidget(self.position_label, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        left_layout.addStretch(1)

        self.status_icon_label = QLabel()
        self.status_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon_label.setFixedSize(18, 18)
        layout.addLayout(left_layout)

        self.preview_label = QLabel("Нет\nпревью")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(92, 92)
        self.preview_label.setStyleSheet(
            "background:#303236; color:#aeb4bf; border-radius:6px; font-size:11px;"
        )
        layout.addWidget(self.preview_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)
        self.title_label = QLabel(task.title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size:15px; font-weight:700; color:#eef2f7;")
        self.channel_label = QLabel(task.channel)
        self.channel_label.setStyleSheet("font-size:12px; color:#b4bcc9;")
        self.channel_label.setWordWrap(True)
        info_layout.addStretch(1)
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.channel_label)
        info_layout.addStretch(1)
        layout.addLayout(info_layout, 1)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(0)

        self.metadata_button = QToolButton()
        self.metadata_button.setToolTip("Изменить метаданные")
        self.metadata_button.setAccessibleName("Изменить метаданные")
        self.metadata_button.setFixedSize(28, 28)
        self.metadata_button.setStyleSheet(
            "QToolButton {"
            "background:#32363d;"
            "border:1px solid #4a515c;"
            "border-radius:7px;"
            "}"
            "QToolButton:hover { background:#3b414b; }"
        )
        self.metadata_button.setIconSize(QSize(16, 16))
        self.set_metadata_icon(metadata_icon)
        self.metadata_button.clicked.connect(self.on_metadata_clicked)

        self.delete_button = QToolButton()
        self.delete_button.setText("●")
        self.delete_button.setToolTip("Удалить ссылку")
        self.delete_button.setFixedSize(20, 20)
        self.delete_button.setStyleSheet(
            "QToolButton {"
            "background:transparent;"
            "color:#ff4d5a;"
            "border:none;"
            "font-size:15px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            "QToolButton:hover { color:#ff6570; }"
        )
        self.delete_button.clicked.connect(self.on_delete_clicked)

        self.metadata_button.setParent(self)
        self.delete_button.setParent(self)
        self.status_icon_label.setParent(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("0%")
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "background:#1f232a;"
            "border:1px solid #3a404a;"
            "border-radius:9px;"
            "text-align:center;"
            "color:#eef2f7;"
            "font-weight:700;"
            "}"
            "QProgressBar::chunk {"
            "background:#5f9ee6;"
            "border-radius:9px;"
            "}"
        )
        right_layout.addStretch(1)
        right_layout.addWidget(
            self.progress_bar,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        right_layout.addStretch(1)
        layout.addLayout(right_layout)

        self.apply_theme(True)
        self.position_action_buttons()
        self.update_from_task(task, False)

    def update_from_task(self, task: DownloadTask, pulse: bool) -> None:
        self.current_status = task.status
        self.title_label.setText(task.title)
        self.channel_label.setText(task.channel)
        self.progress_bar.setValue(int(task.progress))
        self.update_status_icon(task.status)

        if task.thumbnail_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(task.thumbnail_data):
                scaled = pixmap.scaled(
                    self.preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)
                self.preview_label.setText("")
        else:
            self.preview_label.clear()
            self.preview_label.setText("Нет\nпревью")

        if task.status == STATUS_DONE:
            self.progress_bar.setFormat("100%")
            return

        if task.status == STATUS_DOWNLOADING:
            self.progress_bar.setFormat(f"{int(task.progress)}%")
            return

        if task.status == STATUS_ERROR:
            self.progress_bar.setFormat(f"{int(task.progress)}%")
            return

        if task.status == STATUS_META_LOADING:
            self.progress_bar.setFormat("0%")
            return

        self.progress_bar.setFormat("0%")

    def set_selected(self, is_selected: bool) -> None:
        self.is_selected = is_selected
        self.update_card_style()

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        primary = "#eef2f7" if is_dark else "#1e2630"
        secondary = "#b4bcc9" if is_dark else "#556170"
        tertiary = "#7f8794" if is_dark else "#788292"
        preview_bg = "#303236" if is_dark else "#e5eaf0"
        preview_fg = "#aeb4bf" if is_dark else "#6d7785"
        button_bg = "#32363d" if is_dark else "#eef2f6"
        button_border = "#4a515c" if is_dark else "#c8d0dc"
        button_hover = "#3b414b" if is_dark else "#e3e8ef"
        progress_bg = "#1f232a" if is_dark else "#eef2f6"
        progress_border = "#3a404a" if is_dark else "#d0d7e2"
        progress_text = "#eef2f7" if is_dark else "#1e2630"
        self.position_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{tertiary}; background:transparent; border:none;"
        )
        self.preview_label.setStyleSheet(
            f"background:{preview_bg}; color:{preview_fg}; border-radius:6px; font-size:11px;"
        )
        self.title_label.setStyleSheet(
            f"font-size:15px; font-weight:700; color:{primary};"
        )
        self.channel_label.setStyleSheet(f"font-size:12px; color:{secondary};")
        self.metadata_button.setStyleSheet(
            "QToolButton {"
            f"background:{button_bg};"
            f"border:1px solid {button_border};"
            "border-radius:7px;"
            "}"
            f"QToolButton:hover {{ background:{button_hover}; }}"
        )
        self.delete_button.setStyleSheet(
            "QToolButton {"
            "background:transparent;"
            "color:#ff4d5a;"
            "border:none;"
            "font-size:15px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            "QToolButton:hover { color:#ff6570; }"
        )
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            f"background:{progress_bg};"
            f"border:1px solid {progress_border};"
            "border-radius:9px;"
            "text-align:center;"
            f"color:{progress_text};"
            "font-weight:700;"
            "}"
            "QProgressBar::chunk {"
            "background:#5f9ee6;"
            "border-radius:9px;"
            "}"
        )
        self.update_card_style()

    def update_card_style(self) -> None:
        if self.dark_theme:
            background = "#2a2d33"
            border_color = "#5f9ee6" if self.is_selected else "#3a3f48"
        else:
            background = "#ffffff"
            border_color = "#6e99d8" if self.is_selected else "#d0d7e2"
        self.setStyleSheet(
            f"#card {{ background:{background}; border:1px solid {border_color}; border-radius:8px; }}"
        )

    def set_list_index(self, list_index: int) -> None:
        self.list_index = list_index
        self.position_label.setText(str(list_index + 1))

    def set_metadata_icon(self, icon: QIcon) -> None:
        if icon.isNull():
            self.metadata_button.setText("✎")
            self.metadata_button.setIcon(QIcon())
            return
        self.metadata_button.setText("")
        self.metadata_button.setIcon(icon)

    def set_status_icons(self, status_icons: dict[str, QIcon]) -> None:
        self.status_icons = status_icons
        self.update_status_icon(self.current_status)

    def update_status_icon(self, status: str | None = None) -> None:
        state = status if status is not None else STATUS_PENDING
        icon = self.status_icons.get(state)
        if icon is None or icon.isNull():
            self.status_icon_label.clear()
            self.status_icon_label.setText("•")
            self.status_icon_label.setStyleSheet("color:#7f8794; font-size:14px; font-weight:700;")
            return
        if state not in (STATUS_DOWNLOADING, STATUS_META_LOADING):
            self.status_rotation_angle = 0
        self.status_icon_label.setText("")
        pixmap = icon.pixmap(QSize(16, 16))
        if state in (STATUS_DOWNLOADING, STATUS_META_LOADING) and self.status_rotation_angle:
            size = 16
            rotated = QPixmap(size, size)
            rotated.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rotated)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.translate(size / 2, size / 2)
            painter.rotate(self.status_rotation_angle)
            painter.translate(-size / 2, -size / 2)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            pixmap = rotated
        self.status_icon_label.setPixmap(pixmap)

    def tick_status_icon_animation(self) -> None:
        if self.current_status in (STATUS_DOWNLOADING, STATUS_META_LOADING):
            self.status_rotation_angle = (self.status_rotation_angle + 30) % 360
            self.update_status_icon(self.current_status)

    def on_metadata_clicked(self) -> None:
        self.metadata_requested.emit(self.list_index)

    def on_delete_clicked(self) -> None:
        self.delete_requested.emit(self.list_index)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.list_index)
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_action_buttons()

    def position_action_buttons(self) -> None:
        right_margin = 12
        top_margin = 8
        bottom_margin = 8
        self.delete_button.move(self.width() - self.delete_button.width() - right_margin, top_margin)
        self.metadata_button.move(
            self.width() - self.metadata_button.width() - right_margin,
            self.height() - self.metadata_button.height() - bottom_margin,
        )
        status_x = 10 + (self.position_label.width() - self.status_icon_label.width()) // 2
        status_y = self.height() - self.status_icon_label.height() - bottom_margin
        self.status_icon_label.move(status_x, status_y)


class AddCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("add_card")
        self.setFixedHeight(110)
        self.dark_theme = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.title_label = QLabel("Добавить")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.title_label.setStyleSheet("font-size:14px; font-weight:700; color:#b7bfcb;")
        layout.addWidget(self.title_label)

        self.plus_label = QLabel("+")
        self.plus_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plus_label.setFixedSize(40, 40)
        layout.addWidget(self.plus_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        self.apply_theme(True)

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        if is_dark:
            card_bg = "rgba(255, 255, 255, 0.02)"
            card_border = "#4a515c"
            text_color = "#b7bfcb"
            plus_bg = "#262a31"
            plus_border = "#5a6270"
        else:
            card_bg = "#f5f7fa"
            card_border = "#c8d0dc"
            text_color = "#667283"
            plus_bg = "#ffffff"
            plus_border = "#b7c1ce"
        self.setStyleSheet(
            "#add_card {"
            f"background: {card_bg};"
            f"border: 1px dashed {card_border};"
            "border-radius: 8px;"
            "}"
        )
        self.title_label.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{text_color};"
        )
        self.plus_label.setStyleSheet(
            f"border:1px solid {plus_border};"
            "border-radius:8px;"
            "font-size:24px;"
            "font-weight:700;"
            f"color:{text_color};"
            f"background:{plus_bg};"
        )

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)
