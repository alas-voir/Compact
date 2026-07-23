import os

from PyQt6.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFontDatabase, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models import DownloadTask
from .i18n import available_languages
from .music_paths import build_music_output_template
from .themes import available_themes, theme_colors, theme_is_dark
from .widgets import DownloadCard, ToggleSwitch, build_rounded_pixmap
from .workers import DownloadWorker, MetadataWorker


def dialog_theme_colors(is_dark: bool) -> dict[str, str]:
    if theme_is_dark() == is_dark:
        return theme_colors("dialog")
    return theme_colors("dialog", "dark" if is_dark else "light")


class SettingsDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        *,
        version_text: str,
        active_folder_path: str,
        theme_mode: str,
        interface_font_family: str,
        language_code: str,
        open_folder_icon: QIcon,
        choose_folder_icon: QIcon,
        update_icon: QIcon,
        youtube_cookies_browser: str = "",
        youtube_cookies_file: str = "",
        crossfade_enabled: bool = False,
        crossfade_seconds: int = 5,
        volume_normalization_enabled: bool = False,
        window_transparency: bool = True,
        window_blur: bool = True,
        window_transparency_percent: int = 16,
        window_blur_radius: int = 20,
        element_transparency_percent: int = 12,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(700, 600)
        self.setMinimumWidth(700)
        theme_ids = {theme["id"] for theme in available_themes()}
        self.theme_mode = theme_mode if theme_mode in theme_ids else "dark"
        self.youtube_cookies_file_path = youtube_cookies_file.strip()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        github_row = QHBoxLayout()
        github_row.addStretch(1)
        self.github_button = QPushButton("Открыть Github проекта")
        self.github_button.setFixedHeight(30)
        github_row.addWidget(self.github_button)
        self.update_button = QPushButton("Обновить")
        self.update_button.setIcon(update_icon)
        self.update_button.setIconSize(QSize(16, 16))
        self.update_button.setFixedHeight(30)
        github_row.addWidget(self.update_button)
        github_row.addStretch(1)
        root.addLayout(github_row)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(1, 1)

        version_title = QLabel("Версия проекта")
        self.version_value = QLabel(version_text)
        self.version_value.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        grid.addWidget(version_title, 0, 0)
        grid.addWidget(self.version_value, 0, 1)

        folder_title = QLabel("Расположение активной папки")
        folder_panel = QWidget()
        folder_layout = QVBoxLayout(folder_panel)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(8)
        self.active_folder_value = QLabel(active_folder_path)
        self.active_folder_value.setWordWrap(True)
        folder_layout.addWidget(self.active_folder_value)
        folder_buttons = QHBoxLayout()
        folder_buttons.setContentsMargins(0, 0, 0, 0)
        folder_buttons.setSpacing(8)
        self.open_folder_button = QToolButton()
        self.open_folder_button.setToolTip("Открыть расположение")
        self.open_folder_button.setFixedSize(36, 36)
        self.open_folder_button.setIcon(open_folder_icon)
        self.open_folder_button.setIconSize(QSize(18, 18))
        self.choose_folder_button = QToolButton()
        self.choose_folder_button.setToolTip("Выбрать другую активную папку")
        self.choose_folder_button.setFixedSize(36, 36)
        self.choose_folder_button.setIcon(choose_folder_icon)
        self.choose_folder_button.setIconSize(QSize(18, 18))
        folder_buttons.addWidget(self.open_folder_button)
        folder_buttons.addWidget(self.choose_folder_button)
        folder_buttons.addStretch(1)
        folder_layout.addLayout(folder_buttons)
        grid.addWidget(folder_title, 1, 0)
        grid.addWidget(folder_panel, 1, 1)

        theme_title = QLabel("Выбор темы приложения")
        self.theme_combo = QComboBox()
        for theme in available_themes():
            self.theme_combo.addItem(theme["name"], theme["id"])
        current_index = max(0, self.theme_combo.findData(theme_mode))
        self.theme_combo.setCurrentIndex(current_index)
        grid.addWidget(theme_title, 2, 0)
        grid.addWidget(self.theme_combo, 2, 1)

        font_title = QLabel("Шрифт интерфейса")
        self.interface_font_combo = QComboBox()
        self.interface_font_combo.addItem("Системный", "")
        for font_family in QFontDatabase.families():
            self.interface_font_combo.addItem(font_family, font_family)
        font_index = self.interface_font_combo.findData(
            interface_font_family.strip()
        )
        self.interface_font_combo.setCurrentIndex(max(0, font_index))
        grid.addWidget(font_title, 3, 0)
        grid.addWidget(self.interface_font_combo, 3, 1)

        language_title = QLabel("Язык приложения")
        self.language_combo = QComboBox()
        for language in available_languages(refresh=True):
            self.language_combo.addItem(language["name"], language["code"])
        language_index = self.language_combo.findData(language_code)
        self.language_combo.setCurrentIndex(max(0, language_index))
        grid.addWidget(language_title, 4, 0)
        grid.addWidget(self.language_combo, 4, 1)

        youtube_title = QLabel("YouTube cookies")
        youtube_panel = QWidget()
        youtube_layout = QVBoxLayout(youtube_panel)
        youtube_layout.setContentsMargins(0, 0, 0, 0)
        youtube_layout.setSpacing(8)
        self.youtube_browser_combo = QComboBox()
        self.youtube_browser_combo.addItem("Не использовать", "")
        for browser_name, browser_key in [
            ("Safari", "safari"),
            ("Chrome", "chrome"),
            ("Firefox", "firefox"),
            ("Edge", "edge"),
            ("Brave", "brave"),
            ("Chromium", "chromium"),
            ("Zen", "zen"),
            ("Twilight", "twilight"),
        ]:
            self.youtube_browser_combo.addItem(browser_name, browser_key)
        browser_index = self.youtube_browser_combo.findData(
            youtube_cookies_browser.strip().lower()
        )
        self.youtube_browser_combo.setCurrentIndex(max(0, browser_index))
        youtube_layout.addWidget(self.youtube_browser_combo)

        youtube_file_row = QHBoxLayout()
        youtube_file_row.setContentsMargins(0, 0, 0, 0)
        youtube_file_row.setSpacing(8)
        self.youtube_cookies_file_value = QLabel(
            self.youtube_cookies_file_path or "Файл cookies не выбран"
        )
        self.youtube_cookies_file_value.setWordWrap(True)
        self.choose_youtube_cookies_button = QToolButton()
        self.choose_youtube_cookies_button.setToolTip("Выбрать cookies.txt")
        self.choose_youtube_cookies_button.setFixedSize(36, 36)
        self.choose_youtube_cookies_button.setIcon(choose_folder_icon)
        self.choose_youtube_cookies_button.setIconSize(QSize(18, 18))
        self.choose_youtube_cookies_button.clicked.connect(
            self.choose_youtube_cookies_file
        )
        youtube_file_row.addWidget(self.youtube_cookies_file_value, 1)
        youtube_file_row.addWidget(self.choose_youtube_cookies_button)
        youtube_layout.addLayout(youtube_file_row)
        grid.addWidget(youtube_title, 5, 0)
        grid.addWidget(youtube_panel, 5, 1)

        sound_title = QLabel("Звук")
        sound_panel = QWidget()
        sound_layout = QVBoxLayout(sound_panel)
        sound_layout.setContentsMargins(0, 0, 0, 0)
        sound_layout.setSpacing(10)
        crossfade_row = QHBoxLayout()
        crossfade_row.addWidget(QLabel("Cross-fade"))
        crossfade_row.addStretch(1)
        self.crossfade_switch = ToggleSwitch()
        self.crossfade_switch.setChecked(crossfade_enabled)
        crossfade_row.addWidget(self.crossfade_switch)
        sound_layout.addLayout(crossfade_row)
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Время перехода"))
        duration_row.addStretch(1)
        self.crossfade_seconds_spin = QSpinBox()
        self.crossfade_seconds_spin.setRange(1, 30)
        self.crossfade_seconds_spin.setSuffix(" сек.")
        self.crossfade_seconds_spin.setValue(crossfade_seconds)
        duration_row.addWidget(self.crossfade_seconds_spin)
        sound_layout.addLayout(duration_row)
        self.crossfade_seconds_spin.setEnabled(crossfade_enabled)
        self.crossfade_switch.toggled.connect(
            self.crossfade_seconds_spin.setEnabled
        )
        normalization_row = QHBoxLayout()
        normalization_row.addWidget(QLabel("Нормализация громкости"))
        normalization_row.addStretch(1)
        self.volume_normalization_switch = ToggleSwitch()
        self.volume_normalization_switch.setChecked(volume_normalization_enabled)
        normalization_row.addWidget(self.volume_normalization_switch)
        sound_layout.addLayout(normalization_row)
        grid.addWidget(sound_title, 6, 0)
        grid.addWidget(sound_panel, 6, 1)

        window_title = QLabel("Окно")
        window_panel = QWidget()
        window_layout = QVBoxLayout(window_panel)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(10)
        transparency_row = QHBoxLayout()
        transparency_row.addWidget(QLabel("Прозрачность"))
        transparency_row.addStretch(1)
        self.window_transparency_switch = ToggleSwitch()
        self.window_transparency_switch.setChecked(window_transparency)
        transparency_row.addWidget(self.window_transparency_switch)
        window_layout.addLayout(transparency_row)
        transparency_value_row = QHBoxLayout()
        transparency_value_row.addWidget(QLabel("Процент прозрачности"))
        transparency_value_row.addStretch(1)
        self.window_transparency_percent_spin = QSpinBox()
        self.window_transparency_percent_spin.setRange(0, 90)
        self.window_transparency_percent_spin.setSuffix(" %")
        self.window_transparency_percent_spin.setValue(
            window_transparency_percent
        )
        self.window_transparency_percent_spin.setEnabled(window_transparency)
        transparency_value_row.addWidget(self.window_transparency_percent_spin)
        window_layout.addLayout(transparency_value_row)
        blur_row = QHBoxLayout()
        blur_row.addWidget(QLabel("Размытие фона"))
        blur_row.addStretch(1)
        self.window_blur_switch = ToggleSwitch()
        self.window_blur_switch.setChecked(window_blur)
        blur_row.addWidget(self.window_blur_switch)
        window_layout.addLayout(blur_row)
        blur_value_row = QHBoxLayout()
        blur_value_row.addWidget(QLabel("Радиус размытия"))
        blur_value_row.addStretch(1)
        self.window_blur_radius_spin = QSpinBox()
        self.window_blur_radius_spin.setRange(0, 50)
        self.window_blur_radius_spin.setSuffix(" px")
        self.window_blur_radius_spin.setValue(window_blur_radius)
        self.window_blur_radius_spin.setEnabled(window_blur)
        blur_value_row.addWidget(self.window_blur_radius_spin)
        window_layout.addLayout(blur_value_row)
        element_transparency_row = QHBoxLayout()
        element_transparency_row.addWidget(QLabel("Прозрачность элементов"))
        element_transparency_row.addStretch(1)
        self.element_transparency_percent_spin = QSpinBox()
        self.element_transparency_percent_spin.setRange(0, 90)
        self.element_transparency_percent_spin.setSuffix(" %")
        self.element_transparency_percent_spin.setValue(
            element_transparency_percent
        )
        element_transparency_row.addWidget(
            self.element_transparency_percent_spin
        )
        window_layout.addLayout(element_transparency_row)
        self.window_transparency_switch.toggled.connect(
            self.window_transparency_percent_spin.setEnabled
        )
        self.window_blur_switch.toggled.connect(
            self.window_blur_radius_spin.setEnabled
        )
        grid.addWidget(window_title, 7, 0)
        grid.addWidget(window_panel, 7, 1)

        root.addLayout(grid)
        root.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setText("Закрыть")
        root.addWidget(buttons)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.apply_theme()

    def selected_theme_mode(self) -> str:
        return str(self.theme_combo.currentData() or "dark")

    def selected_interface_font_family(self) -> str:
        return str(self.interface_font_combo.currentData() or "").strip()

    def selected_language_code(self) -> str:
        return str(self.language_combo.currentData() or "ru").strip().lower()

    def youtube_auth_values(self) -> tuple[str, str]:
        return (
            str(self.youtube_browser_combo.currentData() or "").strip(),
            self.youtube_cookies_file_path,
        )

    def audio_values(self) -> tuple[bool, int, bool]:
        return (
            self.crossfade_switch.isChecked(),
            self.crossfade_seconds_spin.value(),
            self.volume_normalization_switch.isChecked(),
        )

    def window_effect_values(self) -> tuple[bool, bool, int, int, int]:
        return (
            self.window_transparency_switch.isChecked(),
            self.window_blur_switch.isChecked(),
            self.window_transparency_percent_spin.value(),
            self.window_blur_radius_spin.value(),
            self.element_transparency_percent_spin.value(),
        )

    def choose_youtube_cookies_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите cookies.txt",
            os.path.expanduser("~"),
            "Cookies (*.txt);;Все файлы (*)",
        )
        if not file_path:
            return
        self.youtube_cookies_file_path = file_path
        self.youtube_cookies_file_value.setText(file_path)

    def set_theme_mode(self, mode: str) -> None:
        normalized_mode = str(mode or "").strip().lower()
        if normalized_mode in {theme["id"] for theme in available_themes()}:
            self.theme_mode = normalized_mode

    def set_active_folder_path(self, path: str) -> None:
        self.active_folder_value.setText(path)

    def set_icons(self, open_folder_icon: QIcon, choose_folder_icon: QIcon) -> None:
        self.open_folder_button.setIcon(open_folder_icon)
        self.choose_folder_button.setIcon(choose_folder_icon)

    def is_dark_theme(self) -> bool:
        return theme_is_dark(self.theme_mode)

    def apply_theme(self) -> None:
        colors = dialog_theme_colors(self.is_dark_theme())
        panel_bg = colors["panel_bg"]
        panel_hover = colors["panel_hover"]
        panel_border = colors["panel_border"]
        input_bg = colors["input_bg"]
        input_border = colors["input_border"]
        text_primary = colors["text_primary"]
        text_secondary = colors["text_secondary"]
        self.setStyleSheet(
            "QDialog {"
            f"background:{colors['dialog_bg']};"
            f"color:{text_primary};"
            "}"
            "QDialogButtonBox QPushButton {"
            f"background:{panel_bg};"
            f"border:1px solid {panel_border};"
            "border-radius:8px;"
            f"color:{text_primary};"
            "padding:6px 14px;"
            "min-height:18px;"
            "font-size:12px;"
            "font-weight:600;"
            "}"
            f"QDialogButtonBox QPushButton:hover {{ background:{panel_hover}; }}"
        )

        repository_button_style = (
            "QPushButton {"
            f"background:{panel_bg};"
            f"border:1px solid {panel_border};"
            "border-radius:8px;"
            f"color:{text_primary};"
            "padding:0 14px;"
            "font-size:12px;"
            "font-weight:600;"
            "}"
            f"QPushButton:hover {{ background:{panel_hover}; }}"
        )
        self.github_button.setStyleSheet(repository_button_style)
        self.update_button.setStyleSheet(repository_button_style)
        tool_style = (
            "QToolButton {"
            f"background:{panel_bg};"
            f"border:1px solid {panel_border};"
            "border-radius:8px;"
            "}"
            f"QToolButton:hover {{ background:{panel_hover}; }}"
        )
        self.open_folder_button.setStyleSheet(tool_style)
        self.choose_folder_button.setStyleSheet(tool_style)
        self.choose_youtube_cookies_button.setStyleSheet(tool_style)
        for label in self.findChildren(QLabel):
            label.setStyleSheet(
                f"color:{text_secondary}; font-size:12px; font-weight:700; background:transparent; border:none;"
            )
        for label in [self.version_value, self.active_folder_value]:
            label.setStyleSheet(
                f"color:{text_primary}; font-size:12px; font-weight:500; background:transparent; border:none;"
            )
        self.youtube_cookies_file_value.setStyleSheet(
            f"color:{text_primary}; font-size:12px; font-weight:500; background:transparent; border:none;"
        )
        self.theme_combo.setStyleSheet(
            "QComboBox {"
            f"background:{input_bg};"
            f"border:1px solid {input_border};"
            "border-radius:8px;"
            f"color:{text_primary};"
            "padding:6px 10px;"
            "min-height:22px;"
            "}"
            "QComboBox::drop-down { border:none; width:28px; }"
            "QComboBox QAbstractItemView {"
            f"background:{input_bg};"
            f"border:1px solid {input_border};"
            f"color:{text_primary};"
            "selection-background-color:"
            f"{panel_hover};"
            "}"
        )
        self.youtube_browser_combo.setStyleSheet(self.theme_combo.styleSheet())
        self.interface_font_combo.setStyleSheet(self.theme_combo.styleSheet())
        self.language_combo.setStyleSheet(self.theme_combo.styleSheet())
        self.crossfade_switch.set_dark_theme(self.is_dark_theme())
        self.volume_normalization_switch.set_dark_theme(self.is_dark_theme())
        self.window_transparency_switch.set_dark_theme(self.is_dark_theme())
        self.window_blur_switch.set_dark_theme(self.is_dark_theme())
        spin_style = (
            "QSpinBox {"
            f"background:{input_bg};"
            f"border:1px solid {input_border};"
            "border-radius:8px;"
            f"color:{text_primary};"
            "padding:6px 24px 6px 10px;"
            "min-height:22px;"
            "}"
            "QSpinBox::up-button, QSpinBox::down-button {"
            "background:transparent;"
            "border:none;"
            "width:20px;"
            "}"
        )
        for spin_box in (
            self.crossfade_seconds_spin,
            self.window_transparency_percent_spin,
            self.window_blur_radius_spin,
            self.element_transparency_percent_spin,
        ):
            spin_box.setStyleSheet(spin_style)


class MetadataDialog(QDialog):
    SLICE_REQUESTED = 2

    def __init__(
        self,
        parent: QWidget,
        task: DownloadTask,
        pick_cover_icon: QIcon,
        clear_cover_icon: QIcon,
        allow_slicing: bool = False,
        initial_title: str | None = None,
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
            "border:1px solid #555555;"
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
            "border:1px solid #555555;"
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
        self.title_edit = QLineEdit(
            initial_title if initial_title is not None else (task.meta_title or task.title)
        )
        self.author_edit = QLineEdit(task.meta_author or task.channel)
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
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("Сохранить")
        if allow_slicing:
            slice_button = buttons.addButton("Нарезка", QDialogButtonBox.ButtonRole.ActionRole)
            slice_button.clicked.connect(self.request_slicing)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.refresh_cover_preview()
        self.apply_theme()

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
            self.cover_label.setPixmap(
                build_rounded_pixmap(
                    pixmap,
                    self.cover_label.size(),
                    10,
                )
            )
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

    def request_slicing(self) -> None:
        self.done(self.SLICE_REQUESTED)

    def is_dark_theme(self) -> bool:
        return self.palette().color(self.backgroundRole()).lightness() < 128

    def apply_theme(self) -> None:
        colors = dialog_theme_colors(self.is_dark_theme())
        self.setStyleSheet(
            "QDialog {"
            f"background:{colors['dialog_bg']};"
            f"color:{colors['text_primary']};"
            "}"
            "QLabel {"
            f"color:{colors['text_primary']};"
            "background:transparent;"
            "font-size:12px;"
            "font-weight:700;"
            "}"
            "QLineEdit {"
            f"background:{colors['input_bg']};"
            f"border:1px solid {colors['input_border']};"
            "border-radius:8px;"
            f"color:{colors['text_primary']};"
            "padding:6px 8px;"
            "selection-background-color:#4e88d9;"
            "}"
            "QToolButton {"
            f"background:{colors['panel_bg']};"
            f"border:1px solid {colors['panel_border']};"
            "border-radius:10px;"
            "}"
            f"QToolButton:hover {{ background:{colors['panel_hover']}; }}"
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
        self.cover_label.setStyleSheet(
            f"background:{colors['panel_bg']}; color:{colors['text_muted']}; border-radius:10px; font-size:12px;"
        )


class SliceSegmentsDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Нарезка")
        self.resize(560, 420)
        self.setMinimumWidth(560)
        self.segment_rows: list[tuple[QLineEdit, QLineEdit]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        header_label = QLabel("Количество фрагментов")
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 99)
        self.count_spin.setValue(1)
        self.count_spin.valueChanged.connect(self.sync_segment_rows)
        header_layout.addWidget(header_label)
        header_layout.addWidget(self.count_spin)
        header_layout.addStretch(1)
        root.addLayout(header_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(10)
        self.scroll_area.setWidget(self.rows_container)
        root.addWidget(self.scroll_area, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText("Сохранить")
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setText("Отмена")
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.sync_segment_rows(self.count_spin.value())
        self.apply_theme()

    def sync_segment_rows(self, count: int) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.segment_rows = []

        for index in range(count):
            row_widget = QWidget()
            row_layout = QGridLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setHorizontalSpacing(10)
            row_layout.setVerticalSpacing(6)

            title_label = QLabel(f"Фрагмент {index + 1}")
            start_label = QLabel("Начало")
            end_label = QLabel("Конец")
            start_edit = QLineEdit()
            end_edit = QLineEdit()
            start_edit.setPlaceholderText("00:00")
            end_edit.setPlaceholderText("00:30")

            row_layout.addWidget(title_label, 0, 0, 1, 2)
            row_layout.addWidget(start_label, 1, 0)
            row_layout.addWidget(end_label, 1, 1)
            row_layout.addWidget(start_edit, 2, 0)
            row_layout.addWidget(end_edit, 2, 1)
            self.rows_layout.addWidget(row_widget)
            self.segment_rows.append((start_edit, end_edit))

        self.rows_layout.addStretch(1)

    def validate_and_accept(self) -> None:
        for index, (start_edit, end_edit) in enumerate(self.segment_rows, start=1):
            if not start_edit.text().strip() or not end_edit.text().strip():
                QMessageBox.warning(
                    self,
                    "Нарезка",
                    f"Заполните начало и конец для фрагмента {index}.",
                )
                return
        self.accept()

    def get_segments(self) -> list[tuple[str, str]]:
        return [
            (start_edit.text().strip(), end_edit.text().strip())
            for start_edit, end_edit in self.segment_rows
        ]

    def is_dark_theme(self) -> bool:
        return self.palette().color(self.backgroundRole()).lightness() < 128

    def apply_theme(self) -> None:
        colors = dialog_theme_colors(self.is_dark_theme())
        self.setStyleSheet(
            "QDialog {"
            f"background:{colors['dialog_bg']};"
            f"color:{colors['text_primary']};"
            "}"
            "QLabel {"
            f"color:{colors['text_primary']};"
            "background:transparent;"
            "font-size:12px;"
            "font-weight:700;"
            "}"
            "QLineEdit, QSpinBox {"
            f"background:{colors['input_bg']};"
            f"border:1px solid {colors['input_border']};"
            "border-radius:8px;"
            f"color:{colors['text_primary']};"
            "padding:6px 8px;"
            "selection-background-color:#4e88d9;"
            "}"
            "QScrollArea { background:transparent; border:1px solid "
            f"{colors['panel_border']};"
            " border-radius:8px; }"
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
        ytdlp_options: dict | None = None,
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
        self.ytdlp_options = dict(ytdlp_options or {})

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
            "QPushButton { background:#303030; border:1px solid #464646; border-radius:10px; color:#eef2f7; font-size:13px; font-weight:700; padding:0 18px; }"
            "QPushButton:hover { background:#3a3a3a; }"
            "QPushButton:disabled { background:#292929; border-color:#383838; color:#929292; }"
        )
        self.start_button.clicked.connect(self.start_downloads)
        bottom.addWidget(self.start_button)
        bottom.addStretch(1)
        root.addLayout(bottom)

        for index, task in enumerate(self.tasks):
            card = DownloadCard(task, index, self.metadata_icon, self.status_icons)
            card.apply_theme(self.is_dark_theme())
            card.metadata_requested.connect(self.on_card_metadata_requested)
            card.delete_requested.connect(self.on_card_delete_requested)
            card.selected.connect(self.on_card_selected)
            self.cards.append(card)
            self.cards_layout.addWidget(card)

        self.apply_theme()
        self.start_metadata_load()

    def is_dark_theme(self) -> bool:
        return self.palette().color(self.backgroundRole()).lightness() < 128

    def apply_theme(self) -> None:
        colors = dialog_theme_colors(self.is_dark_theme())
        self.scroll_area.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }"
        )
        self.cards_container.setStyleSheet("background:transparent; border:none;")
        self.setStyleSheet(
            f"QDialog {{ background:{colors['dialog_bg']}; color:{colors['text_primary']}; }}"
        )
        self.start_button.setStyleSheet(
            "QPushButton {"
            f"background:{colors['panel_bg']};"
            f"border:1px solid {colors['panel_border']};"
            "border-radius:10px;"
            f"color:{colors['text_primary']};"
            "font-size:13px;"
            "font-weight:700;"
            "padding:0 18px; }"
            f"QPushButton:hover {{ background:{colors['panel_hover']}; }}"
            "QPushButton:disabled {"
            f"background:{colors['panel_bg']};"
            f"border-color:{colors['panel_border']};"
            f"color:{colors['text_muted']}; }}"
        )

    def animate_cards(self) -> None:
        for card in self.cards:
            card.tick_status_icon_animation()

    def start_metadata_load(self) -> None:
        if not self.tasks:
            self.update_start_button_state()
            return
        pairs = [(index, task.url) for index, task in enumerate(self.tasks)]
        worker = MetadataWorker(pairs, self.ytdlp_options)
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
        worker = MetadataWorker([(index, url)], self.ytdlp_options)
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
        output_template = build_music_output_template(
            self.output_dir,
            title=task.meta_title or task.title,
            artist=task.meta_author,
            album=task.meta_album,
            separator=" - ",
        )
        worker = DownloadWorker(
            index,
            task.url,
            self.output_dir,
            metadata_overrides,
            task.meta_cover_path,
            self.ffmpeg_location,
            output_template=output_template,
            ytdlp_options=self.ytdlp_options,
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
