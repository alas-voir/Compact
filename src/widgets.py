from PyQt6.QtCore import QEvent, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
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


def build_center_cropped_pixmap(pixmap: QPixmap, size: QSize) -> QPixmap:
    scaled = pixmap.scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    centered = QPixmap(size)
    centered.fill(Qt.GlobalColor.transparent)
    painter = QPainter(centered)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    draw_x = (size.width() - scaled.width()) // 2
    draw_y = (size.height() - scaled.height()) // 2
    painter.drawPixmap(draw_x, draw_y, scaled)
    painter.end()
    return centered


def build_rounded_pixmap(pixmap: QPixmap, size: QSize, radius: int) -> QPixmap:
    centered = build_center_cropped_pixmap(pixmap, size)
    rounded = QPixmap(size)
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    path = QPainterPath()
    path.addRoundedRect(
        0.0,
        0.0,
        float(size.width()),
        float(size.height()),
        radius,
        radius,
    )
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, centered)
    painter.end()
    return rounded


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
        knob_x = (
            track_rect.right() - knob_diameter - 2
            if self.isChecked()
            else track_rect.x() + 2
        )
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_x, knob_y, knob_diameter, knob_diameter)
        painter.end()


class BackChevronButton(QToolButton):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.dark_theme = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(30, 30)
        self.setAutoRaise(True)
        self.setStyleSheet(
            "QToolButton { background:transparent; border:none; padding:0; }"
            "QToolButton:hover { background:transparent; }"
            "QToolButton:pressed { background:transparent; }"
        )

    def set_dark_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("#F2F5FA") if self.dark_theme else QColor("#1F2630")
        pen = QPen(
            color,
            2.5,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)
        mid_x = self.width() // 2
        mid_y = self.height() // 2
        painter.drawLine(mid_x + 4, mid_y - 6, mid_x - 2, mid_y)
        painter.drawLine(mid_x - 2, mid_y, mid_x + 4, mid_y + 6)
        painter.end()


class PlaylistListItemWidget(QFrame):
    clicked = pyqtSignal()
    context_requested = pyqtSignal(object)
    reveal_requested = pyqtSignal()
    delete_requested = pyqtSignal()

    def __init__(
        self,
        title: str,
        loading_icon: QIcon,
        ready_icon: QIcon,
        reveal_icon: QIcon | None = None,
    ) -> None:
        super().__init__()
        self.loading_icon = loading_icon
        self.ready_icon = ready_icon
        self.reveal_icon = reveal_icon or QIcon()
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
        layout.addWidget(
            self.status_icon_label, 0, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        self.reveal_button = QToolButton()
        self.reveal_button.setToolTip("Открыть расположение")
        self.reveal_button.setFixedSize(18, 18)
        self.reveal_button.setIconSize(QSize(16, 16))
        self.reveal_button.clicked.connect(self.reveal_requested.emit)
        layout.addWidget(
            self.reveal_button, 0, alignment=Qt.AlignmentFlag.AlignVCenter
        )

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
        self.set_reveal_icon(self.reveal_icon)
        self.set_loading(False)
        self.set_status_visible(True)
        self.set_reveal_visible(True)
        self.set_delete_visible(True)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_loading_icon(self, icon: QIcon) -> None:
        self.loading_icon = icon
        self.update_status_icon()

    def set_ready_icon(self, icon: QIcon) -> None:
        self.ready_icon = icon
        self.update_status_icon()

    def set_reveal_icon(self, icon: QIcon) -> None:
        self.reveal_icon = icon
        if icon.isNull():
            self.reveal_button.setIcon(QIcon())
            self.reveal_button.setText("↗")
            return
        self.reveal_button.setText("")
        self.reveal_button.setIcon(icon)

    def set_loading(self, is_loading: bool) -> None:
        self.is_loading = is_loading
        if not is_loading:
            self.rotation_angle = 0
        self.update_status_icon()

    def set_status_visible(self, visible: bool) -> None:
        self.status_icon_label.setVisible(visible)

    def set_delete_visible(self, visible: bool) -> None:
        self.delete_button.setVisible(visible)

    def set_reveal_visible(self, visible: bool) -> None:
        self.reveal_button.setVisible(visible)

    def set_selected(self, is_selected: bool) -> None:
        self.is_selected = is_selected
        self.update_style()

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        title_color = "#eef2f7" if is_dark else "#1e2630"
        self.title_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{title_color}; background:transparent; border:none;"
        )
        self.reveal_button.setStyleSheet(
            "QToolButton { background:transparent; border:none; padding:0; }"
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
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(event.globalPosition().toPoint())
        super().mousePressEvent(event)


class SearchAlbumCard(QFrame):
    clicked = pyqtSignal(str, str)
    delete_requested = pyqtSignal(str, str)

    def __init__(
        self,
        album_name: str,
        author_name: str,
        track_count: int,
        thumbnail_data: bytes | None = None,
    ) -> None:
        super().__init__()
        self.album_name = album_name
        self.author_name = author_name
        self.track_count = track_count
        self.thumbnail_data = thumbnail_data
        self.dark_theme = True
        self.setObjectName("search_album_card")
        self.setFixedSize(176, 264)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.cover_label = QLabel("Нет\nобложки")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setFixedSize(152, 152)
        layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.album_label = QLabel(album_name)
        self.album_label.setWordWrap(True)
        layout.addWidget(self.album_label)

        self.author_label = QLabel(author_name)
        self.author_label.setWordWrap(True)
        layout.addWidget(self.author_label)

        self.count_label = QLabel(f"Треки: {track_count}")
        layout.addWidget(self.count_label)
        layout.addStretch(1)

        self.delete_button = self.create_delete_button("Удалить альбом")
        self.delete_button.clicked.connect(
            lambda: self.delete_requested.emit(self.album_name, self.author_name)
        )

        self.apply_theme(True)
        self.refresh_cover()
        self.position_delete_button()

    def refresh_cover(self) -> None:
        if self.thumbnail_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(self.thumbnail_data):
                scaled = pixmap.scaled(
                    self.cover_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.cover_label.setPixmap(
                    build_rounded_pixmap(scaled, self.cover_label.size(), 10)
                )
                self.cover_label.setText("")
                return
        self.cover_label.clear()
        self.cover_label.setText("Нет\nобложки")

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        background = "#303030" if is_dark else "#ffffff"
        border = "#3a3f48" if is_dark else "#d0d7e2"
        preview_bg = "#20242a" if is_dark else "#eef2f6"
        preview_fg = "#8f98a6" if is_dark else "#788292"
        primary = "#eef2f7" if is_dark else "#1e2630"
        secondary = "#b4bcc9" if is_dark else "#556170"
        tertiary = "#8f98a6" if is_dark else "#788292"
        self.setStyleSheet(
            f"#search_album_card {{ background:{background}; border:1px solid {border}; border-radius:10px; }}"
        )
        self.cover_label.setStyleSheet(
            f"background:{preview_bg}; color:{preview_fg}; border-radius:10px; font-size:11px;"
        )
        self.album_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{primary}; background:transparent; border:none;"
        )
        self.author_label.setStyleSheet(
            f"font-size:12px; color:{secondary}; background:transparent; border:none;"
        )
        self.count_label.setStyleSheet(
            f"font-size:12px; color:{tertiary}; background:transparent; border:none;"
        )
        self.apply_delete_button_style()

    def create_delete_button(self, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setText("●")
        button.setToolTip(tooltip)
        button.setFixedSize(24, 24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def apply_delete_button_style(self) -> None:
        bg = "rgba(31, 35, 42, 0.78)" if self.dark_theme else "rgba(255, 255, 255, 0.86)"
        border = "rgba(255, 255, 255, 0.12)" if self.dark_theme else "rgba(145, 154, 168, 0.28)"
        hover_bg = "rgba(45, 50, 58, 0.92)" if self.dark_theme else "rgba(245, 247, 250, 0.96)"
        self.delete_button.setStyleSheet(
            "QToolButton {"
            f"background:{bg};"
            "color:#ff4d5a;"
            f"border:1px solid {border};"
            "border-radius:12px;"
            "font-size:15px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            f"QToolButton:hover {{ background:{hover_bg}; color:#ff6570; }}"
        )

    def position_delete_button(self) -> None:
        self.delete_button.move(self.width() - self.delete_button.width() - 10, 8)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.album_name, self.author_name)
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_delete_button()


class SearchAuthorCard(QFrame):
    clicked = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(
        self,
        author_name: str,
        track_count: int,
        album_count: int,
    ) -> None:
        super().__init__()
        self.author_name = author_name
        self.dark_theme = True
        self.setObjectName("search_author_card")
        self.setFixedSize(192, 128)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.name_label = QLabel(author_name)
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)

        layout.addStretch(1)
        self.track_count_label = QLabel(f"Треки: {track_count}")
        self.track_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.track_count_label)
        self.album_count_label = QLabel(f"Альбомы: {album_count}")
        self.album_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.album_count_label)
        layout.addStretch(1)

        self.delete_button = self.create_delete_button("Удалить автора")
        self.delete_button.clicked.connect(
            lambda: self.delete_requested.emit(self.author_name)
        )

        self.apply_theme(True)
        self.position_delete_button()

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        background = "#303030" if is_dark else "#ffffff"
        border = "#3a3f48" if is_dark else "#d0d7e2"
        name_bg = "#20242a" if is_dark else "#eef2f6"
        primary = "#eef2f7" if is_dark else "#1e2630"
        secondary = "#b4bcc9" if is_dark else "#556170"
        self.setStyleSheet(
            f"#search_author_card {{ background:{background}; border:1px solid {border}; border-radius:10px; }}"
        )
        self.name_label.setStyleSheet(
            f"background:{name_bg}; color:{primary}; border-radius:8px; font-size:13px; font-weight:700; padding:6px 8px;"
        )
        self.track_count_label.setStyleSheet(
            f"font-size:12px; color:{secondary}; background:transparent; border:none;"
        )
        self.album_count_label.setStyleSheet(
            f"font-size:12px; color:{secondary}; background:transparent; border:none;"
        )
        self.apply_delete_button_style()

    def create_delete_button(self, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setText("●")
        button.setToolTip(tooltip)
        button.setFixedSize(24, 24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def apply_delete_button_style(self) -> None:
        bg = "rgba(31, 35, 42, 0.78)" if self.dark_theme else "rgba(255, 255, 255, 0.86)"
        border = "rgba(255, 255, 255, 0.12)" if self.dark_theme else "rgba(145, 154, 168, 0.28)"
        hover_bg = "rgba(45, 50, 58, 0.92)" if self.dark_theme else "rgba(245, 247, 250, 0.96)"
        self.delete_button.setStyleSheet(
            "QToolButton {"
            f"background:{bg};"
            "color:#ff4d5a;"
            f"border:1px solid {border};"
            "border-radius:12px;"
            "font-size:15px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            f"QToolButton:hover {{ background:{hover_bg}; color:#ff6570; }}"
        )

    def position_delete_button(self) -> None:
        self.delete_button.move(self.width() - self.delete_button.width() - 10, 8)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.author_name)
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_delete_button()


class HomeAuthorCard(QFrame):
    clicked = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(
        self,
        author_name: str,
        track_count: int,
        album_count: int,
    ) -> None:
        super().__init__()
        self.author_name = author_name
        self.dark_theme = True
        self.setObjectName("home_author_card")
        self.setFixedSize(176, 116)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.name_label = QLabel(author_name)
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)

        layout.addStretch(1)
        self.track_count_label = QLabel(f"Треки: {track_count}")
        self.track_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.track_count_label)
        self.album_count_label = QLabel(f"Альбомы: {album_count}")
        self.album_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.album_count_label)

        self.delete_button = self.create_delete_button("Удалить автора")
        self.delete_button.clicked.connect(
            lambda: self.delete_requested.emit(self.author_name)
        )

        self.apply_theme(True)
        self.position_delete_button()

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        background = "#303030" if is_dark else "#ffffff"
        border = "#3a3f48" if is_dark else "#d0d7e2"
        primary = "#eef2f7" if is_dark else "#1e2630"
        secondary = "#b4bcc9" if is_dark else "#556170"
        self.setStyleSheet(
            f"#home_author_card {{ background:{background}; border:1px solid {border}; border-radius:10px; }}"
        )
        self.name_label.setStyleSheet(
            f"font-size:14px; font-weight:700; color:{primary}; background:transparent; border:none;"
        )
        self.track_count_label.setStyleSheet(
            f"font-size:12px; color:{secondary}; background:transparent; border:none;"
        )
        self.album_count_label.setStyleSheet(
            f"font-size:12px; color:{secondary}; background:transparent; border:none;"
        )
        self.apply_delete_button_style()

    def create_delete_button(self, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setText("●")
        button.setToolTip(tooltip)
        button.setFixedSize(24, 24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def apply_delete_button_style(self) -> None:
        bg = "rgba(31, 35, 42, 0.78)" if self.dark_theme else "rgba(255, 255, 255, 0.86)"
        border = "rgba(255, 255, 255, 0.12)" if self.dark_theme else "rgba(145, 154, 168, 0.28)"
        hover_bg = "rgba(45, 50, 58, 0.92)" if self.dark_theme else "rgba(245, 247, 250, 0.96)"
        self.delete_button.setStyleSheet(
            "QToolButton {"
            f"background:{bg};"
            "color:#ff4d5a;"
            f"border:1px solid {border};"
            "border-radius:12px;"
            "font-size:15px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            f"QToolButton:hover {{ background:{hover_bg}; color:#ff6570; }}"
        )

    def position_delete_button(self) -> None:
        self.delete_button.move(self.width() - self.delete_button.width() - 10, 8)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.author_name)
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_delete_button()


class SearchPlaylistCard(QFrame):
    clicked = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(
        self,
        playlist_index: int,
        playlist_name: str,
        track_count: int,
        author_count: int,
        cover_items: list[bytes],
    ) -> None:
        super().__init__()
        self.playlist_index = playlist_index
        self.playlist_name = playlist_name
        self.track_count = track_count
        self.author_count = author_count
        self.cover_items = cover_items
        self.dark_theme = True
        self.setObjectName("search_playlist_card")
        self.setFixedSize(176, 264)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.cover_label = QLabel("Нет\nобложки")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setFixedSize(152, 152)
        layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.title_label = QLabel(playlist_name)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.authors_label = QLabel(f"Авторы: {author_count}")
        layout.addWidget(self.authors_label)

        self.count_label = QLabel(f"Треки: {track_count}")
        layout.addWidget(self.count_label)
        layout.addStretch(1)

        self.delete_button = self.create_delete_button("Удалить плейлист")
        self.delete_button.clicked.connect(
            lambda: self.delete_requested.emit(self.playlist_index)
        )

        self.apply_theme(True)
        self.refresh_cover()
        self.position_delete_button()

    def refresh_cover(self) -> None:
        valid_pixmaps: list[QPixmap] = []
        for cover_data in self.cover_items[:4]:
            pixmap = QPixmap()
            if cover_data and pixmap.loadFromData(cover_data):
                valid_pixmaps.append(pixmap)

        if not valid_pixmaps:
            self.cover_label.clear()
            self.cover_label.setText("Нет\nобложки")
            return

        canvas_size = self.cover_label.size()
        half_width = canvas_size.width() // 2
        half_height = canvas_size.height() // 2
        collage = QPixmap(canvas_size)
        collage.fill(Qt.GlobalColor.transparent)
        painter = QPainter(collage)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        cells = [
            (0, 0),
            (half_width, 0),
            (0, half_height),
            (half_width, half_height),
        ]
        fallback = valid_pixmaps[-1]
        cell_size = QSize(half_width, half_height)
        for index, (x_pos, y_pos) in enumerate(cells):
            source = valid_pixmaps[index] if index < len(valid_pixmaps) else fallback
            cropped = build_center_cropped_pixmap(source, cell_size)
            painter.drawPixmap(x_pos, y_pos, cropped)
        painter.end()
        self.cover_label.setPixmap(
            build_rounded_pixmap(collage, self.cover_label.size(), 10)
        )
        self.cover_label.setText("")

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        background = "#303030" if is_dark else "#ffffff"
        border = "#3a3f48" if is_dark else "#d0d7e2"
        preview_bg = "#20242a" if is_dark else "#eef2f6"
        preview_fg = "#8f98a6" if is_dark else "#788292"
        primary = "#eef2f7" if is_dark else "#1e2630"
        secondary = "#b4bcc9" if is_dark else "#556170"
        tertiary = "#8f98a6" if is_dark else "#788292"
        self.setStyleSheet(
            f"#search_playlist_card {{ background:{background}; border:1px solid {border}; border-radius:10px; }}"
        )
        self.cover_label.setStyleSheet(
            f"background:{preview_bg}; color:{preview_fg}; border-radius:10px; font-size:11px;"
        )
        self.title_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{primary}; background:transparent; border:none;"
        )
        self.authors_label.setStyleSheet(
            f"font-size:12px; color:{secondary}; background:transparent; border:none;"
        )
        self.count_label.setStyleSheet(
            f"font-size:12px; color:{tertiary}; background:transparent; border:none;"
        )
        self.apply_delete_button_style()

    def create_delete_button(self, tooltip: str) -> QToolButton:
        button = QToolButton(self)
        button.setText("●")
        button.setToolTip(tooltip)
        button.setFixedSize(24, 24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def apply_delete_button_style(self) -> None:
        bg = "rgba(31, 35, 42, 0.78)" if self.dark_theme else "rgba(255, 255, 255, 0.86)"
        border = "rgba(255, 255, 255, 0.12)" if self.dark_theme else "rgba(145, 154, 168, 0.28)"
        hover_bg = "rgba(45, 50, 58, 0.92)" if self.dark_theme else "rgba(245, 247, 250, 0.96)"
        self.delete_button.setStyleSheet(
            "QToolButton {"
            f"background:{bg};"
            "color:#ff4d5a;"
            f"border:1px solid {border};"
            "border-radius:12px;"
            "font-size:15px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            f"QToolButton:hover {{ background:{hover_bg}; color:#ff6570; }}"
        )

    def position_delete_button(self) -> None:
        self.delete_button.move(self.width() - self.delete_button.width() - 10, 8)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.playlist_index)
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_delete_button()


class RemoteTrackCard(QFrame):
    selected = pyqtSignal(int, int)
    context_requested = pyqtSignal(int, object)
    reveal_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(
        self,
        track: RemoteTrack | LocalMusicTrack,
        track_index: int,
        status_icons: dict[str, QIcon],
        metadata_icon: QIcon,
        reveal_icon: QIcon | None = None,
        show_preview: bool = True,
        display_number: int | None = None,
        show_artist_album: bool = True,
        compact: bool = False,
        preview_size: int = 78,
    ) -> None:
        super().__init__()
        self.track_index = track_index
        self.display_number = display_number if display_number is not None else track_index + 1
        self.is_selected = False
        self.status_icons = status_icons
        self.reveal_icon = reveal_icon or QIcon()
        self.current_status = STATUS_PENDING
        self.status_rotation_angle = 0
        self.dark_theme = True
        self.show_preview = show_preview
        self.show_artist_album = show_artist_album
        self.compact = compact
        self.preview_size = preview_size
        self.setObjectName("remote_track_card")
        self.setFixedHeight(68 if compact else 126)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 8 if compact else 10, 12, 8 if compact else 10)
        root_layout.setSpacing(4 if compact else 8)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.position_label = QLabel(str(self.display_number))
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position_label.setFixedWidth(26)
        self.position_label.setStyleSheet(
            "font-size:13px; font-weight:700; color:#7f8794; background:transparent; border:none;"
        )
        content_layout.addWidget(
            self.position_label, 0, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        self.status_icon_label = QLabel()
        self.status_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon_label.setFixedSize(18, 18)
        self.status_icon_label.setStyleSheet("background:transparent; border:none;")
        self.status_icon_label.setParent(self)

        self.duration_label = QLabel()
        self.duration_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.duration_label.setFixedWidth(44)
        self.duration_label.setStyleSheet(
            "font-size:11px; font-weight:600; color:#8f98a6; background:transparent; border:none;"
        )
        self.duration_label.setParent(self)

        self.preview_label = QLabel("Нет\nобложки")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(self.preview_size, self.preview_size)
        self.preview_label.setStyleSheet(
            "background:#303236; color:#aeb4bf; border-radius:8px; font-size:11px;"
        )
        content_layout.addWidget(self.preview_label)

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
        content_layout.addLayout(text_layout, 1)
        content_layout.addSpacing(128 if compact else 136)

        root_layout.addLayout(content_layout, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setFixedHeight(10 if compact else 14)
        self.progress_bar.setVisible(False)
        root_layout.addWidget(self.progress_bar)

        self.reveal_button = QToolButton()
        self.reveal_button.setToolTip("Открыть расположение")
        self.reveal_button.setFixedSize(20, 20)
        self.reveal_button.setIconSize(QSize(16, 16))
        self.reveal_button.clicked.connect(
            lambda: self.reveal_requested.emit(self.track_index)
        )
        self.reveal_button.setParent(self)

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
        self.delete_button.clicked.connect(
            lambda: self.delete_requested.emit(self.track_index)
        )
        self.delete_button.setParent(self)

        self.apply_theme(True)
        self.set_reveal_icon(self.reveal_icon)
        self.set_preview_visible(show_preview)
        self.set_artist_album_visible(show_artist_album)
        self.update_from_track(track)
        self.position_overlay_controls()

    def update_from_track(
        self,
        track: RemoteTrack | LocalMusicTrack,
        display_number: int | None = None,
    ) -> None:
        if display_number is not None:
            self.display_number = display_number
        self.position_label.setText(str(self.display_number))
        self.title_label.setText(track.title)
        self.artist_label.setText(track.artists)
        self.album_label.setText(track.album or "Без альбома")
        self.duration_label.setText(getattr(track, "duration_text", "") or "")
        self.duration_label.setVisible(bool(self.duration_label.text()))
        self.current_status = getattr(track, "status", STATUS_PENDING)
        self.update_status_icon(self.current_status)
        progress = int(max(0.0, min(100.0, getattr(track, "progress", 0.0))))
        self.progress_bar.setValue(progress)
        self.progress_bar.setFormat(f"{progress}%")
        self.progress_bar.setVisible(self.current_status == STATUS_DOWNLOADING)
        if not self.show_preview:
            self.preview_label.clear()
            self.preview_label.setText("")
            return
        if track.thumbnail_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(track.thumbnail_data):
                scaled = pixmap.scaled(
                    self.preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(self.rounded_preview_pixmap(scaled))
                self.preview_label.setText("")
                return
        self.preview_label.clear()
        self.preview_label.setText("Нет\nобложки")

    def set_preview_visible(self, visible: bool) -> None:
        self.show_preview = visible
        self.preview_label.setVisible(visible)
        if visible:
            self.preview_label.setFixedSize(self.preview_size, self.preview_size)
        else:
            self.preview_label.setFixedSize(0, 0)

    def set_artist_album_visible(self, visible: bool) -> None:
        self.show_artist_album = visible
        self.artist_label.setVisible(visible)
        self.album_label.setVisible(visible)

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
        progress_bg = "#1f232a" if is_dark else "#eef2f6"
        progress_border = "#3a404a" if is_dark else "#d0d7e2"
        progress_text = "#eef2f7" if is_dark else "#1e2630"
        self.position_label.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{tertiary}; background:transparent; border:none;"
        )
        self.duration_label.setStyleSheet(
            f"font-size:{10 if self.compact else 11}px; font-weight:600; color:{tertiary}; background:transparent; border:none;"
        )
        self.preview_label.setStyleSheet(
            f"background:{preview_bg}; color:{preview_fg}; border-radius:{max(8, self.preview_size // 7)}px; font-size:11px;"
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
        self.reveal_button.setStyleSheet(
            "QToolButton { background:transparent; border:none; padding:0; }"
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
            f"border-radius:{5 if self.compact else 7}px;"
            "text-align:center;"
            f"color:{progress_text};"
            f"font-size:{9 if self.compact else 11}px;"
            "font-weight:700;"
            "padding:0;"
            "}"
            "QProgressBar::chunk {"
            "background:#5f9ee6;"
            f"border-radius:{4 if self.compact else 6}px;"
            "}"
        )
        self.update_card_style()

    def update_card_style(self) -> None:
        if self.dark_theme:
            background = "#303030"
            border_color = "#606060" if self.is_selected else "#3a3f48"
        else:
            background = "#ffffff"
            border_color = "#6e99d8" if self.is_selected else "#d0d7e2"
        self.setStyleSheet(
            f"#remote_track_card {{ background:{background}; border:1px solid {border_color}; border-radius:10px; }}"
        )

    def set_status_icons(self, status_icons: dict[str, QIcon]) -> None:
        self.status_icons = status_icons
        self.update_status_icon(self.current_status)

    def set_reveal_icon(self, icon: QIcon) -> None:
        self.reveal_icon = icon
        if icon.isNull():
            self.reveal_button.setIcon(QIcon())
            self.reveal_button.setText("↗")
            return
        self.reveal_button.setText("")
        self.reveal_button.setIcon(icon)

    def update_status_icon(self, status: str | None = None) -> None:
        state = status if status is not None else STATUS_PENDING
        icon = self.status_icons.get(state) or self.status_icons.get(STATUS_PENDING)
        if icon is None or icon.isNull():
            self.status_icon_label.clear()
            return
        if state not in (STATUS_DOWNLOADING, STATUS_META_LOADING):
            self.status_rotation_angle = 0
        pixmap = icon.pixmap(QSize(16, 16))
        if (
            state in (STATUS_DOWNLOADING, STATUS_META_LOADING)
            and self.status_rotation_angle
        ):
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
            self.context_requested.emit(
                self.track_index, event.globalPosition().toPoint()
            )
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_overlay_controls()

    def position_overlay_controls(self) -> None:
        delete_x = self.width() - self.delete_button.width() - 12
        reveal_x = delete_x - self.reveal_button.width() - 12
        status_x = reveal_x - self.status_icon_label.width() - 12
        duration_x = status_x - self.duration_label.width() - 12
        status_y = (self.height() - self.status_icon_label.height()) // 2
        self.status_icon_label.move(status_x, status_y)
        duration_y = (self.height() - self.duration_label.height()) // 2
        self.duration_label.move(duration_x, duration_y)
        reveal_y = (self.height() - self.reveal_button.height()) // 2
        self.reveal_button.move(reveal_x, reveal_y)
        delete_y = (self.height() - self.delete_button.height()) // 2
        self.delete_button.move(delete_x, delete_y)

    def rounded_preview_pixmap(self, pixmap: QPixmap) -> QPixmap:
        size = self.preview_label.size()
        radius = max(8, self.preview_size // 7)
        return build_rounded_pixmap(pixmap, size, radius)


class HoverCoverLabel(QLabel):
    pick_requested = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self, text: str = "Нет\nобложки") -> None:
        super().__init__(text)
        self.background_color = QColor("#171717")
        self.border_color = QColor("#303030")
        self.text_color = QColor("#8f98a6")
        self.corner_radius = 12
        self._syncing_size = False
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)

        self.pick_button = QToolButton(self)
        self.pick_button.setToolTip("Выбрать обложку")
        self.pick_button.setFixedSize(36, 36)
        self.pick_button.setIconSize(QSize(18, 18))
        self.pick_button.clicked.connect(self.pick_requested.emit)

        self.clear_button = QToolButton(self)
        self.clear_button.setToolTip("Сбросить обложку")
        self.clear_button.setFixedSize(36, 36)
        self.clear_button.setIconSize(QSize(18, 18))
        self.clear_button.clicked.connect(self.clear_requested.emit)

        self.pick_button.installEventFilter(self)
        self.clear_button.installEventFilter(self)
        self.update_overlay_visibility()

    def set_theme_colors(
        self,
        *,
        is_dark: bool,
        background: str,
        border: str,
        text: str,
    ) -> None:
        del is_dark
        self.background_color = QColor(background)
        self.border_color = QColor(border)
        self.text_color = QColor(text)
        button_bg = "#2e3136" if QColor(background).lightness() < 128 else "#eef2f6"
        button_hover = "#373b43" if QColor(background).lightness() < 128 else "#e4e9f0"
        button_border = "#3b3f46" if QColor(background).lightness() < 128 else "#cad2de"
        style = (
            "QToolButton {"
            f"background:{button_bg};"
            f"border:1px solid {button_border};"
            "border-radius:8px;"
            "}"
            f"QToolButton:hover {{ background:{button_hover}; }}"
            "QToolButton:disabled { background:transparent; border-color:transparent; }"
        )
        self.pick_button.setStyleSheet(style)
        self.clear_button.setStyleSheet(style)
        self.update()

    def set_overlay_icons(self, pick_icon: QIcon, clear_icon: QIcon) -> None:
        self.pick_button.setIcon(pick_icon)
        self.clear_button.setIcon(clear_icon)

    def sizeHint(self) -> QSize:
        side = self.width() or self.height() or 220
        return QSize(220, side)

    def minimumSizeHint(self) -> QSize:
        side = min(self.width() or self.height() or 220, 220)
        return QSize(120, side)

    def eventFilter(self, watched, event) -> bool:
        if watched in {self.pick_button, self.clear_button} and event.type() in {
            QEvent.Type.Enter,
            QEvent.Type.Leave,
            QEvent.Type.EnabledChange,
        }:
            self.update_overlay_visibility()
        return super().eventFilter(watched, event)

    def enterEvent(self, event) -> None:
        self.update_overlay_visibility()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update_overlay_visibility()
        super().leaveEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._syncing_size and self.width() > 0 and self.height() != self.width():
            self._syncing_size = True
            self.setFixedHeight(self.width())
            self._syncing_size = False
        bottom = self.height() - self.pick_button.height() - 8
        self.pick_button.move(8, bottom)
        self.clear_button.move(
            self.width() - self.clear_button.width() - 8,
            bottom,
        )

    def update_overlay_visibility(self) -> None:
        hovered = self.underMouse() or self.pick_button.underMouse() or self.clear_button.underMouse()
        self.pick_button.setVisible(hovered and self.pick_button.isEnabled())
        self.clear_button.setVisible(hovered and self.clear_button.isEnabled())

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(
            float(rect.x()),
            float(rect.y()),
            float(rect.width()),
            float(rect.height()),
            self.corner_radius,
            self.corner_radius,
        )
        painter.fillPath(path, self.background_color)

        pixmap = self.pixmap()
        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            draw_x = rect.x() + (rect.width() - scaled.width()) // 2
            draw_y = rect.y() + (rect.height() - scaled.height()) // 2
            painter.save()
            painter.setClipPath(path)
            painter.drawPixmap(draw_x, draw_y, scaled)
            painter.restore()
        else:
            painter.setPen(self.text_color)
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), self.text())

        painter.setPen(self.border_color)
        painter.drawPath(path)


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
        self.position_label.setStyleSheet(
            "font-size:13px; font-weight:700; color:#7f8794;"
        )
        left_layout.addWidget(
            self.position_label,
            alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        )
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
        self.title_label.setStyleSheet(
            "font-size:15px; font-weight:700; color:#eef2f7;"
        )
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
                self.preview_label.setPixmap(
                    build_rounded_pixmap(
                        pixmap,
                        self.preview_label.size(),
                        6,
                    )
                )
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
            self.status_icon_label.setStyleSheet(
                "color:#7f8794; font-size:14px; font-weight:700;"
            )
            return
        if state not in (STATUS_DOWNLOADING, STATUS_META_LOADING):
            self.status_rotation_angle = 0
        self.status_icon_label.setText("")
        pixmap = icon.pixmap(QSize(16, 16))
        if (
            state in (STATUS_DOWNLOADING, STATUS_META_LOADING)
            and self.status_rotation_angle
        ):
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
        self.delete_button.move(
            self.width() - self.delete_button.width() - right_margin, top_margin
        )
        self.metadata_button.move(
            self.width() - self.metadata_button.width() - right_margin,
            self.height() - self.metadata_button.height() - bottom_margin,
        )
        status_x = (
            10 + (self.position_label.width() - self.status_icon_label.width()) // 2
        )
        status_y = self.height() - self.status_icon_label.height() - bottom_margin
        self.status_icon_label.move(status_x, status_y)


class DownloadQueueCard(QFrame):
    def __init__(
        self,
        title: str,
        progress: float,
        status: str,
        thumbnail_data: bytes | None,
        status_icons: dict[str, QIcon],
    ) -> None:
        super().__init__()
        self.current_status = status
        self.status_icons = status_icons
        self.status_rotation_angle = 0
        self.dark_theme = True
        self.setObjectName("download_queue_card")
        self.setFixedHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        self.preview_label = QLabel("Нет\nобложки")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(52, 52)
        layout.addWidget(self.preview_label)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(False)
        self.title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setFixedHeight(14)
        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.progress_bar)
        layout.addLayout(info_layout, 1)

        self.status_icon_label = QLabel()
        self.status_icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon_label.setFixedSize(20, 20)
        layout.addWidget(self.status_icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.apply_theme(True)
        self.update_content(title, progress, status, thumbnail_data)

    def update_content(
        self,
        title: str,
        progress: float,
        status: str,
        thumbnail_data: bytes | None,
    ) -> None:
        self.current_status = status
        self.title_label.setText(title or "Без названия")
        normalized_progress = int(max(0.0, min(100.0, progress)))
        self.progress_bar.setValue(normalized_progress)
        self.progress_bar.setFormat(f"{normalized_progress}%")
        self.update_status_icon(status)

        if thumbnail_data:
            pixmap = QPixmap()
            if pixmap.loadFromData(thumbnail_data):
                self.preview_label.setPixmap(
                    build_rounded_pixmap(pixmap, self.preview_label.size(), 7)
                )
                self.preview_label.setText("")
                return
        self.preview_label.clear()
        self.preview_label.setText("Нет\nобложки")

    def apply_theme(self, is_dark: bool) -> None:
        self.dark_theme = is_dark
        background = "#2a2d33" if is_dark else "#ffffff"
        border = "#3a3f48" if is_dark else "#d0d7e2"
        primary = "#eef2f7" if is_dark else "#1e2630"
        preview_bg = "#303236" if is_dark else "#e5eaf0"
        preview_fg = "#aeb4bf" if is_dark else "#6d7785"
        progress_bg = "#1f232a" if is_dark else "#eef2f6"
        progress_border = "#3a404a" if is_dark else "#d0d7e2"
        progress_text = "#eef2f7" if is_dark else "#1e2630"
        self.setStyleSheet(
            f"#download_queue_card {{ background:{background}; border:1px solid {border}; border-radius:10px; }}"
        )
        self.preview_label.setStyleSheet(
            f"background:{preview_bg}; color:{preview_fg}; border-radius:7px; font-size:9px;"
        )
        self.title_label.setStyleSheet(
            f"font-size:12px; font-weight:700; color:{primary}; background:transparent; border:none;"
        )
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            f"background:{progress_bg};"
            f"border:1px solid {progress_border};"
            "border-radius:7px;"
            "text-align:center;"
            f"color:{progress_text};"
            "font-size:10px;"
            "font-weight:700;"
            "}"
            "QProgressBar::chunk {"
            "background:#5f9ee6;"
            "border-radius:6px;"
            "}"
        )

    def set_status_icons(self, status_icons: dict[str, QIcon]) -> None:
        self.status_icons = status_icons
        self.update_status_icon(self.current_status)

    def update_status_icon(self, status: str | None = None) -> None:
        state = status if status is not None else STATUS_PENDING
        icon = self.status_icons.get(state)
        if icon is None or icon.isNull():
            self.status_icon_label.clear()
            self.status_icon_label.setText("•")
            self.status_icon_label.setStyleSheet(
                "color:#7f8794; font-size:14px; font-weight:700; background:transparent;"
            )
            return
        if state not in (STATUS_DOWNLOADING, STATUS_META_LOADING):
            self.status_rotation_angle = 0
        self.status_icon_label.setText("")
        pixmap = icon.pixmap(QSize(18, 18))
        if (
            state in (STATUS_DOWNLOADING, STATUS_META_LOADING)
            and self.status_rotation_angle
        ):
            size = 18
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
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        )
        self.title_label.setStyleSheet(
            "font-size:14px; font-weight:700; color:#b7bfcb;"
        )
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
