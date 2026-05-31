import os
import re

from PyQt6.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import DownloadTask
from .widgets import DownloadCard
from .workers import DownloadWorker, MetadataWorker


class MetadataDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        task: DownloadTask,
        pick_cover_icon: QIcon,
        clear_cover_icon: QIcon,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Изменить метаданные")
        self.resize(700, 340)
        self.setMinimumWidth(700)

        self.cover_path = task.meta_cover_path
        self.thumbnail_data = task.thumbnail_data
        self.cover_mode = "keep"

        root = QVBoxLayout(self)
        content = QHBoxLayout()
        content.setSpacing(16)

        left = QVBoxLayout()
        left.addStretch(1)
        self.cover_label = QLabel("Нет\nобложки")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setFixedSize(170, 170)
        self.cover_label.setStyleSheet(
            "background:#303236; color:#aeb4bf; border-radius:10px; font-size:12px;"
        )
        left.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignRight)

        cover_buttons_row = QHBoxLayout()
        cover_buttons_row.setContentsMargins(0, 0, 0, 0)
        cover_buttons_row.setSpacing(10)

        self.pick_cover_button = QToolButton()
        self.pick_cover_button.setToolTip("Выбрать обложку")
        self.pick_cover_button.setAccessibleName("Выбрать обложку")
        self.pick_cover_button.setFixedSize(42, 42)
        self.pick_cover_button.setStyleSheet(
            "QToolButton {"
            "background:#32363d;"
            "border:1px solid #4a515c;"
            "border-radius:10px;"
            "}"
            "QToolButton:hover { background:#3b414b; }"
        )
        self.pick_cover_button.setIcon(pick_cover_icon)
        self.pick_cover_button.setIconSize(QSize(20, 20))
        self.pick_cover_button.clicked.connect(self.pick_cover)

        self.clear_cover_button = QToolButton()
        self.clear_cover_button.setToolTip("Сбросить обложку")
        self.clear_cover_button.setAccessibleName("Сбросить обложку")
        self.clear_cover_button.setFixedSize(42, 42)
        self.clear_cover_button.setStyleSheet(
            "QToolButton {"
            "background:#32363d;"
            "border:1px solid #4a515c;"
            "border-radius:10px;"
            "}"
            "QToolButton:hover { background:#3b414b; }"
        )
        self.clear_cover_button.setIcon(clear_cover_icon)
        self.clear_cover_button.setIconSize(QSize(20, 20))
        self.clear_cover_button.clicked.connect(self.clear_cover)

        cover_buttons_row.addWidget(self.pick_cover_button)
        cover_buttons_row.addWidget(self.clear_cover_button)

        cover_buttons_widget = QWidget()
        cover_buttons_widget.setFixedWidth(self.cover_label.width())
        cover_buttons_widget.setLayout(cover_buttons_row)
        left.addWidget(cover_buttons_widget, alignment=Qt.AlignmentFlag.AlignRight)
        left.addStretch(1)
        content.addLayout(left)

        right_panel = QVBoxLayout()
        right_panel.addStretch(1)
        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(16)
        self.url_edit = QLineEdit(task.url)
        self.title_edit = QLineEdit(task.meta_title)
        self.author_edit = QLineEdit(task.meta_author)
        self.group_edit = QLineEdit(task.meta_group)
        self.album_edit = QLineEdit(task.meta_album)
        for line_edit in [
            self.url_edit,
            self.title_edit,
            self.author_edit,
            self.group_edit,
            self.album_edit,
        ]:
            line_edit.setMinimumWidth(340)

        self.url_edit.setPlaceholderText("Ссылка")
        self.title_edit.setPlaceholderText(task.title or "Название")
        self.author_edit.setPlaceholderText(task.channel or "Автор")
        self.group_edit.setPlaceholderText("Группа")
        self.album_edit.setPlaceholderText("Альбом")

        form.addRow("Ссылка:", self.url_edit)
        form.addRow("Название:", self.title_edit)
        form.addRow("Автор:", self.author_edit)
        form.addRow("Группа:", self.group_edit)
        form.addRow("Альбом:", self.album_edit)
        form_container = QWidget()
        form_container.setLayout(form)
        right_panel.addWidget(form_container, alignment=Qt.AlignmentFlag.AlignLeft)
        right_panel.addStretch(1)
        content.addLayout(right_panel, 1)

        root.addLayout(content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.refresh_cover_preview()

    def pick_cover(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите обложку",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path:
            return
        self.cover_path = path
        self.cover_mode = "custom"
        self.refresh_cover_preview()

    def clear_cover(self) -> None:
        self.cover_path = ""
        self.cover_mode = "clear"
        self.refresh_cover_preview()

    def refresh_cover_preview(self) -> None:
        pixmap = QPixmap()
        loaded = False
        if self.cover_path and os.path.exists(self.cover_path):
            loaded = pixmap.load(self.cover_path)
        elif self.thumbnail_data:
            loaded = pixmap.loadFromData(self.thumbnail_data)

        if loaded:
            scaled = pixmap.scaled(
                self.cover_label.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.cover_label.setPixmap(scaled)
            self.cover_label.setText("")
        else:
            self.cover_label.clear()
            self.cover_label.setText("Нет\nобложки")

    def get_metadata_values(self) -> tuple[dict[str, str], str, str]:
        values = {
            "url": self.url_edit.text().strip(),
            "title": self.title_edit.text().strip(),
            "author": self.author_edit.text().strip(),
            "group": self.group_edit.text().strip(),
            "album": self.album_edit.text().strip(),
        }
        return values, self.cover_path, self.cover_mode


class SpotifyCredentialsDialog(QDialog):
    def __init__(
        self, parent: QWidget, client_id: str = "", client_secret: str = ""
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки Spotify")
        self.resize(640, 220)
        self.setMinimumWidth(640)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        description = QLabel(
            "Введите Spotify Client ID и Client Secret для чтения публичных Spotify-плейлистов."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size:13px; color:#eef2f7;")
        root.addWidget(description)

        form = QFormLayout()
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)

        self.client_id_edit = QLineEdit(client_id)
        self.client_secret_edit = QLineEdit(client_secret)
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_id_edit.setMinimumWidth(380)
        self.client_secret_edit.setMinimumWidth(380)
        self.client_id_edit.setPlaceholderText("Spotify Client ID")
        self.client_secret_edit.setPlaceholderText("Spotify Client Secret")

        form.addRow("Client ID:", self.client_id_edit)
        form.addRow("Client Secret:", self.client_secret_edit)

        form_widget = QWidget()
        form_widget.setLayout(form)
        root.addWidget(form_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def get_values(self) -> tuple[str, str]:
        return (
            self.client_id_edit.text().strip(),
            self.client_secret_edit.text().strip(),
        )


class ExperimentalImportDialog(QDialog):
    downloads_completed = pyqtSignal()

    def __init__(
        self,
        parent: QWidget,
        links: list[str],
        output_dir: str,
        ffmpeg_location: str,
        metadata_icon: QIcon,
        pick_cover_icon: QIcon,
        clear_cover_icon: QIcon,
        status_icons: dict[str, QIcon],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Импорт в Вся музыка")
        self.resize(600, 720)
        self.setMinimumWidth(600)

        self.output_dir = output_dir
        self.ffmpeg_location = ffmpeg_location
        self.metadata_icon = metadata_icon
        self.pick_cover_icon = pick_cover_icon
        self.clear_cover_icon = clear_cover_icon
        self.status_icons = status_icons

        self.tasks: list[DownloadTask] = [DownloadTask(url=link) for link in links]
        self.cards: list[DownloadCard] = []
        self.selected_task_index: int | None = 0 if self.tasks else None
        self.active_download_index: int | None = None
        self.metadata_thread: QThread | None = None
        self.metadata_worker: MetadataWorker | None = None
        self.download_thread: QThread | None = None
        self.download_worker: DownloadWorker | None = None
        self._should_close_after_workers = False
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(120)
        self.animation_timer.timeout.connect(self.animate_cards)
        self.animation_timer.start()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards_layout.setContentsMargins(4, 4, 4, 4)
        self.cards_layout.setSpacing(8)
        self.scroll_area.setWidget(self.cards_container)
        root.addWidget(self.scroll_area, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.start_button = QPushButton("Старт")
        self.start_button.setFixedHeight(38)
        self.start_button.setMinimumWidth(160)
        self.start_button.setStyleSheet(
            "QPushButton { background:#2e3136; border:1px solid #3b3f46; border-radius:10px; color:#eef2f7; font-size:13px; font-weight:700; padding:0 18px; }"
            "QPushButton:hover { background:#373b43; }"
            "QPushButton:disabled { background:#2a2d33; border-color:#353941; color:#8b93a0; }"
        )
        self.start_button.clicked.connect(self.start_downloads)
        bottom.addWidget(self.start_button)
        bottom.addStretch(1)
        root.addLayout(bottom)

        for index, task in enumerate(self.tasks):
            card = DownloadCard(task, index, self.metadata_icon, self.status_icons)
            card.metadata_requested.connect(self.on_card_metadata_requested)
            card.delete_requested.connect(self.on_card_delete_requested)
            card.selected.connect(self.on_card_selected)
            self.cards.append(card)
            self.cards_layout.addWidget(card)

        self.start_metadata_load()

    def animate_cards(self) -> None:
        for card in self.cards:
            card.tick_status_icon_animation()

    def start_metadata_load(self) -> None:
        if not self.tasks:
            self.update_start_button_state()
            return
        pairs = [(index, task.url) for index, task in enumerate(self.tasks)]
        worker = MetadataWorker(pairs)
        thread = QThread(self)
        self.metadata_worker = worker
        self.metadata_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.metadata_ready.connect(self.on_metadata_ready)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_metadata_finished)
        thread.start()
        self.update_start_button_state()

    def on_metadata_ready(
        self,
        index: int,
        title: str,
        channel: str,
        thumbnail_data: bytes | None,
        error_text: str,
        extracted_meta: dict[str, str],
    ) -> None:
        if not (0 <= index < len(self.tasks)):
            return
        task = self.tasks[index]
        task.title = title
        task.channel = channel
        task.thumbnail_data = thumbnail_data
        task.status = "pending"
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

    def on_metadata_finished(self) -> None:
        self.metadata_thread = None
        self.metadata_worker = None
        self.update_start_button_state()
        if self._should_close_after_workers:
            self.reject()

    def on_card_selected(self, index: int) -> None:
        self.selected_task_index = index if 0 <= index < len(self.tasks) else None
        for card_index, card in enumerate(self.cards):
            card.set_selected(card_index == self.selected_task_index)

    def on_card_metadata_requested(self, index: int) -> None:
        if self.metadata_thread is not None or self.download_thread is not None:
            return
        if not (0 <= index < len(self.tasks)):
            return
        task = self.tasks[index]
        dialog = MetadataDialog(self, task, self.pick_cover_icon, self.clear_cover_icon)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values, cover_path, cover_mode = dialog.get_metadata_values()
        new_url = values["url"]
        if not new_url:
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
            task.status = "meta_loading"
            task.progress = 0.0
            task.error = ""
            task.thumbnail_data = None
            task.meta_title = ""
            task.meta_author = ""
            task.meta_group = ""
            task.meta_album = ""
            task.meta_cover_path = ""
            self.refresh_card(index)
            self.restart_metadata_for_single_task(index, new_url)
            return
        self.refresh_card(index)

    def restart_metadata_for_single_task(self, index: int, url: str) -> None:
        if self.metadata_worker is not None:
            self.metadata_worker.cancel()
        worker = MetadataWorker([(index, url)])
        thread = QThread(self)
        self.metadata_worker = worker
        self.metadata_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.metadata_ready.connect(self.on_metadata_ready)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_metadata_finished)
        thread.start()
        self.update_start_button_state()

    def on_card_delete_requested(self, index: int) -> None:
        if self.metadata_thread is not None or self.download_thread is not None:
            return
        if not (0 <= index < len(self.tasks)):
            return
        self.tasks.pop(index)
        card = self.cards.pop(index)
        self.cards_layout.removeWidget(card)
        card.deleteLater()
        self.renumber_cards()
        if self.selected_task_index is None:
            self.selected_task_index = 0 if self.tasks else None
        elif not self.tasks:
            self.selected_task_index = None
        elif self.selected_task_index >= len(self.tasks):
            self.selected_task_index = len(self.tasks) - 1
        self.on_card_selected(
            self.selected_task_index if self.selected_task_index is not None else -1
        )
        self.update_start_button_state()

    def renumber_cards(self) -> None:
        for index, card in enumerate(self.cards):
            card.set_list_index(index)

    def refresh_card(self, index: int) -> None:
        if 0 <= index < len(self.cards):
            self.cards[index].update_from_task(self.tasks[index], False)

    def start_downloads(self) -> None:
        if self.metadata_thread is not None or self.download_thread is not None:
            return
        next_index = next(
            (
                index
                for index, task in enumerate(self.tasks)
                if task.status == "pending"
            ),
            None,
        )
        if next_index is None:
            return
        self.start_button.setEnabled(False)
        self.start_download_for_index(next_index)

    def start_download_for_index(self, index: int) -> None:
        task = self.tasks[index]
        metadata_overrides = {
            "title": task.meta_title,
            "artist": task.meta_author,
            "album_artist": task.meta_group,
            "album": task.meta_album,
        }
        output_template = os.path.join(
            self.output_dir,
            f"{self._sanitize_filename_part(task.meta_author or task.channel)} – {self._sanitize_filename_part(task.meta_title or task.title)}.%(ext)s",
        )
        worker = DownloadWorker(
            index,
            task.url,
            self.output_dir,
            metadata_overrides,
            task.meta_cover_path,
            self.ffmpeg_location,
            output_template=output_template,
        )
        thread = QThread(self)
        self.download_worker = worker
        self.download_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.started.connect(self.on_download_started)
        worker.progress_changed.connect(self.on_download_progress)
        worker.finished.connect(self.on_download_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.on_download_thread_finished)
        thread.start()

    def on_download_started(self, index: int) -> None:
        self.active_download_index = index
        task = self.tasks[index]
        task.status = "downloading"
        task.progress = 0.0
        self.refresh_card(index)

    def on_download_progress(self, index: int, percent: float) -> None:
        if not (0 <= index < len(self.tasks)):
            return
        self.tasks[index].progress = percent
        self.refresh_card(index)

    def on_download_finished(self, index: int, success: bool, error_text: str) -> None:
        if not (0 <= index < len(self.tasks)):
            return
        task = self.tasks[index]
        task.status = "done" if success else "error"
        task.progress = 100.0 if success else task.progress
        task.error = error_text
        self.refresh_card(index)

    def on_download_thread_finished(self) -> None:
        self.download_thread = None
        self.download_worker = None
        next_index = next(
            (
                index
                for index, task in enumerate(self.tasks)
                if task.status == "pending"
            ),
            None,
        )
        if next_index is None:
            self.start_button.setEnabled(
                any(task.status == "pending" for task in self.tasks)
            )
            self.downloads_completed.emit()
            return
        self.start_download_for_index(next_index)

    def update_start_button_state(self) -> None:
        self.start_button.setEnabled(
            self.metadata_thread is None
            and self.download_thread is None
            and any(task.status == "pending" for task in self.tasks)
        )

    def closeEvent(self, event) -> None:
        if self.download_thread is not None:
            event.ignore()
            return
        if self.metadata_worker is not None:
            self.metadata_worker.cancel()
        if self.metadata_thread is not None:
            self._should_close_after_workers = True
            event.ignore()
            return
        super().closeEvent(event)

    def _sanitize_filename_part(self, value: str) -> str:
        text = (value or "").strip() or "Неизвестно"
        text = re.sub(r'[<>:"/\\\\|?*]+', "_", text)
        text = re.sub(r"\\s+", " ", text).strip()
        return text.rstrip(".") or "Неизвестно"
