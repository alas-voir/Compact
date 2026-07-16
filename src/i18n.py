import json
import re
import sys
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from .paths import resource_path


_active_language = "ru"
_event_filter = None
_packs_cache = None


def language_directories() -> tuple[Path, Path]:
    home = Path.home()
    if sys.platform == "darwin":
        custom = home / "Library" / "Application Support" / "Compact" / "languages"
    elif sys.platform.startswith("win"):
        custom = home / "AppData" / "Roaming" / "Compact" / "languages"
    else:
        custom = home / ".config" / "compact" / "languages"
    return Path(resource_path("assets", "languages")), custom


def _read_pack(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("translations", {}), dict):
        return None
    code = str(data.get("code") or path.stem).strip().lower()
    if not code:
        return None
    return {
        "code": code,
        "name": str(data.get("name") or code),
        "translations": {
            str(source): str(target)
            for source, target in data.get("translations", {}).items()
        },
        "path": str(path),
    }


def available_languages(refresh: bool = False) -> list[dict]:
    global _packs_cache
    if _packs_cache is not None and not refresh:
        return list(_packs_cache)
    packs = {}
    bundled, custom = language_directories()
    try:
        custom.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    for directory in (bundled, custom):
        if directory.exists():
            for path in sorted(directory.glob("*.json")):
                pack = _read_pack(path)
                if pack:
                    packs[pack["code"]] = pack
    ordered = []
    for code in ("ru", "en"):
        if code in packs:
            ordered.append(packs.pop(code))
    ordered.extend(sorted(packs.values(), key=lambda item: item["name"].casefold()))
    _packs_cache = ordered
    return list(ordered)


def language_pack(code: str) -> dict:
    packs = {pack["code"]: pack for pack in available_languages()}
    return packs.get(str(code).lower()) or packs.get("ru") or {
        "code": "ru", "name": "Русский", "translations": {}
    }


def set_language(code: str) -> str:
    global _active_language
    _active_language = language_pack(code)["code"]
    return _active_language


def current_language() -> str:
    return _active_language


def _format_pattern(pattern: str) -> re.Pattern:
    parts = re.split(r"(\{[^{}]+\})", pattern)
    expression = ""
    for part in parts:
        expression += r"(.+?)" if part.startswith("{") else re.escape(part)
    return re.compile(f"^{expression}$")


def tr(text: str, language: str | None = None) -> str:
    if not text:
        return text
    target_pack = language_pack(language or _active_language)
    if target_pack["code"] == "ru":
        # Restore exact English strings when switching back without restarting.
        reverse = {value: key for key, value in language_pack("en")["translations"].items()}
        exact = reverse.get(text)
        if exact is not None:
            return exact
        translations = reverse
    else:
        translations = target_pack["translations"]
    exact = translations.get(text)
    if exact is not None:
        return exact
    for source, target in translations.items():
        if "{" not in source:
            continue
        match = _format_pattern(source).match(text)
        if match:
            result = target
            placeholders = re.findall(r"\{([^{}]+)\}", source)
            for name, value in zip(placeholders, match.groups()):
                result = result.replace("{" + name + "}", value)
            return result
    return text


def translate_object(obj: QObject) -> None:
    if isinstance(obj, QWidget):
        if obj.windowTitle():
            translated = tr(obj.windowTitle())
            if translated != obj.windowTitle():
                obj.setWindowTitle(translated)
        if obj.toolTip():
            translated = tr(obj.toolTip())
            if translated != obj.toolTip():
                obj.setToolTip(translated)
        if obj.accessibleName():
            translated = tr(obj.accessibleName())
            if translated != obj.accessibleName():
                obj.setAccessibleName(translated)
        for action in obj.actions():
            translate_object(action)
    if isinstance(obj, QLabel) and obj.text():
        translated = tr(obj.text())
        if translated != obj.text():
            obj.setText(translated)
    if isinstance(obj, QAbstractButton) and obj.text():
        translated = tr(obj.text())
        if translated != obj.text():
            obj.setText(translated)
    if isinstance(obj, QLineEdit) and obj.placeholderText():
        translated = tr(obj.placeholderText())
        if translated != obj.placeholderText():
            obj.setPlaceholderText(translated)
    if isinstance(obj, QSpinBox) and obj.suffix():
        translated = tr(obj.suffix())
        if translated != obj.suffix():
            obj.setSuffix(translated)
    if isinstance(obj, QComboBox):
        for index in range(obj.count()):
            translated = tr(obj.itemText(index))
            if translated != obj.itemText(index):
                obj.setItemText(index, translated)
    if isinstance(obj, QAction):
        translated = tr(obj.text())
        if translated != obj.text():
            obj.setText(translated)
        translated = tr(obj.toolTip())
        if translated != obj.toolTip():
            obj.setToolTip(translated)


def retranslate_all() -> None:
    app = QApplication.instance()
    if app is None:
        return
    for widget in app.allWidgets():
        translate_object(widget)
        for action in widget.actions():
            translate_object(action)


class LanguageEventFilter(QObject):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.busy = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if not self.busy and event.type() in {
            QEvent.Type.Show,
            QEvent.Type.Paint,
            QEvent.Type.ToolTipChange,
        }:
            self.busy = True
            try:
                translate_object(watched)
            finally:
                self.busy = False
        return False


def install_language_event_filter() -> None:
    global _event_filter
    app = QApplication.instance()
    if app is None or _event_filter is not None:
        return
    _event_filter = LanguageEventFilter(app)
    app.installEventFilter(_event_filter)
