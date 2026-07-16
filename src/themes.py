import json
import sys
from pathlib import Path

from .paths import resource_path


REQUIRED_MAIN_COLORS = {
    "app_bg", "button_bg", "button_hover", "button_border",
    "button_disabled_bg", "button_disabled_border", "button_disabled_text",
    "panel_bg", "panel_border", "list_bg", "text_primary",
    "text_secondary", "text_muted", "checkbox_bg", "checkbox_border",
    "checkbox_checked", "progress_bg", "progress_border", "footer_text",
}
REQUIRED_DIALOG_COLORS = {
    "dialog_bg", "panel_bg", "panel_hover", "panel_border", "input_bg",
    "input_border", "text_primary", "text_secondary", "text_muted", "accent",
}

_active_theme_id = "dark"
_theme_catalog_cache: dict[str, dict] | None = None


def theme_directories() -> tuple[Path, Path]:
    home = Path.home()
    if sys.platform == "darwin":
        custom_dir = home / "Library" / "Application Support" / "Compact" / "themes"
    elif sys.platform.startswith("win"):
        custom_dir = home / "AppData" / "Roaming" / "Compact" / "themes"
    else:
        custom_dir = home / ".config" / "compact" / "themes"
    return Path(resource_path("assets", "themes")), custom_dir


def _read_theme(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    theme_id = str(data.get("id") or path.stem).strip().lower()
    base = str(data.get("base") or "dark").strip().lower()
    colors = data.get("colors")
    if not theme_id or base not in {"dark", "light"} or not isinstance(colors, dict):
        return None
    if not isinstance(colors.get("main"), dict) or not isinstance(colors.get("dialog"), dict):
        return None
    data["id"] = theme_id
    data["name"] = str(data.get("name") or theme_id).strip()
    data["base"] = base
    data["path"] = str(path)
    return data


def available_themes() -> list[dict]:
    global _theme_catalog_cache
    if _theme_catalog_cache is not None:
        themes = dict(_theme_catalog_cache)
        ordered = []
        for built_in_id in ("light", "dark"):
            if built_in_id in themes:
                ordered.append(themes.pop(built_in_id))
        ordered.extend(sorted(themes.values(), key=lambda item: item["name"].casefold()))
        return ordered
    themes: dict[str, dict] = {}
    bundled_dir, custom_dir = theme_directories()
    try:
        custom_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    for directory in (bundled_dir, custom_dir):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            theme = _read_theme(path)
            if theme is not None:
                themes[theme["id"]] = theme
    _theme_catalog_cache = dict(themes)
    ordered = []
    for built_in_id in ("light", "dark"):
        if built_in_id in themes:
            ordered.append(themes.pop(built_in_id))
    ordered.extend(sorted(themes.values(), key=lambda item: item["name"].casefold()))
    return ordered


def load_theme(theme_id: str) -> dict:
    normalized = str(theme_id or "").strip().lower()
    themes = {theme["id"]: theme for theme in available_themes()}
    theme = themes.get(normalized) or themes.get("dark")
    if theme is None:
        raise RuntimeError("Built-in dark theme is missing")
    base_theme = themes.get(theme["base"], theme)
    merged = {
        "id": theme["id"],
        "name": theme["name"],
        "base": theme["base"],
        "path": theme["path"],
        "colors": {
            "main": dict(base_theme["colors"]["main"]),
            "dialog": dict(base_theme["colors"]["dialog"]),
            "palette": dict(base_theme["colors"].get("palette", {})),
        },
    }
    for group in ("main", "dialog", "palette"):
        values = theme["colors"].get(group, {})
        if isinstance(values, dict):
            merged["colors"][group].update(
                {str(key): str(value) for key, value in values.items()}
            )
    return merged


def set_active_theme(theme_id: str) -> dict:
    global _active_theme_id
    theme = load_theme(theme_id)
    _active_theme_id = theme["id"]
    return theme


def active_theme() -> dict:
    return load_theme(_active_theme_id)


def theme_is_dark(theme_id: str | None = None) -> bool:
    return load_theme(theme_id or _active_theme_id)["base"] == "dark"


def theme_colors(group: str, theme_id: str | None = None) -> dict[str, str]:
    return dict(load_theme(theme_id or _active_theme_id)["colors"][group])
