import json
from pathlib import Path

from .paths import config_path


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as source:
            data = json.load(source)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json_file(path: Path, payload: dict, restrict_permissions: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as target:
        json.dump(payload, target, ensure_ascii=False, indent=2)
    if restrict_permissions:
        try:
            path.chmod(0o600)
        except Exception:
            pass


def load_app_settings() -> dict:
    path = Path(config_path("settings.json"))
    return _read_json_file(path)


def save_app_settings(settings: dict) -> None:
    path = Path(config_path("settings.json"))
    _write_json_file(path, settings)


def load_elenveil_root_dir() -> str:
    settings = load_app_settings()
    library = settings.get("library")
    if not isinstance(library, dict):
        return ""
    return str(library.get("elenveil_root_dir") or "").strip()


def save_elenveil_root_dir(path: str) -> None:
    settings = load_app_settings()
    library = settings.get("library")
    if not isinstance(library, dict):
        library = {}
    library["elenveil_root_dir"] = path.strip()
    settings["library"] = library
    save_app_settings(settings)


def load_theme_mode() -> str:
    settings = load_app_settings()
    appearance = settings.get("appearance")
    if not isinstance(appearance, dict):
        return ""
    mode = str(appearance.get("theme_mode") or "").strip().lower()
    return mode


def save_theme_mode(mode: str) -> None:
    normalized_mode = mode.strip().lower()
    if not normalized_mode:
        return
    settings = load_app_settings()
    appearance = settings.get("appearance")
    if not isinstance(appearance, dict):
        appearance = {}
    appearance["theme_mode"] = normalized_mode
    settings["appearance"] = appearance
    save_app_settings(settings)


def load_interface_font_family() -> str:
    settings = load_app_settings()
    appearance = settings.get("appearance")
    if not isinstance(appearance, dict):
        return ""
    return str(appearance.get("interface_font_family") or "").strip()


def save_interface_font_family(font_family: str) -> None:
    settings = load_app_settings()
    appearance = settings.get("appearance")
    if not isinstance(appearance, dict):
        appearance = {}
    appearance["interface_font_family"] = font_family.strip()
    settings["appearance"] = appearance
    save_app_settings(settings)


def load_language_code() -> str:
    settings = load_app_settings()
    appearance = settings.get("appearance")
    if not isinstance(appearance, dict):
        return "ru"
    return str(appearance.get("language") or "ru").strip().lower()


def save_language_code(language_code: str) -> None:
    settings = load_app_settings()
    appearance = settings.get("appearance")
    if not isinstance(appearance, dict):
        appearance = {}
    appearance["language"] = language_code.strip().lower()
    settings["appearance"] = appearance
    save_app_settings(settings)


def load_youtube_auth_settings() -> dict[str, str]:
    settings = load_app_settings()
    youtube = settings.get("youtube")
    if not isinstance(youtube, dict):
        return {"cookies_browser": "", "cookies_file": ""}
    return {
        "cookies_browser": str(youtube.get("cookies_browser") or "").strip(),
        "cookies_file": str(youtube.get("cookies_file") or "").strip(),
    }


def save_youtube_auth_settings(cookies_browser: str, cookies_file: str) -> None:
    settings = load_app_settings()
    youtube = settings.get("youtube")
    if not isinstance(youtube, dict):
        youtube = {}
    youtube["cookies_browser"] = cookies_browser.strip().lower()
    youtube["cookies_file"] = cookies_file.strip()
    settings["youtube"] = youtube
    save_app_settings(settings)


def load_playback_session() -> dict:
    settings = load_app_settings()
    playback = settings.get("playback_session")
    return playback if isinstance(playback, dict) else {}


def save_playback_session(session: dict) -> None:
    settings = load_app_settings()
    settings["playback_session"] = session
    save_app_settings(settings)


def load_audio_settings() -> tuple[bool, int, bool]:
    settings = load_app_settings()
    audio = settings.get("audio")
    if not isinstance(audio, dict):
        return False, 5, False
    try:
        seconds = max(1, min(30, int(audio.get("crossfade_seconds", 5))))
    except (TypeError, ValueError):
        seconds = 5
    return (
        bool(audio.get("crossfade_enabled", False)),
        seconds,
        bool(audio.get("volume_normalization_enabled", False)),
    )


def save_audio_settings(
    crossfade_enabled: bool,
    crossfade_seconds: int,
    volume_normalization_enabled: bool = False,
) -> None:
    settings = load_app_settings()
    audio = settings.get("audio")
    if not isinstance(audio, dict):
        audio = {}
    audio["crossfade_enabled"] = bool(crossfade_enabled)
    audio["crossfade_seconds"] = max(1, min(30, int(crossfade_seconds)))
    audio["volume_normalization_enabled"] = bool(volume_normalization_enabled)
    settings["audio"] = audio
    save_app_settings(settings)


def load_window_effect_settings() -> tuple[bool, bool, int, int, int]:
    settings = load_app_settings()
    appearance = settings.get("appearance")
    if not isinstance(appearance, dict):
        return True, True, 16, 20, 12
    try:
        transparency_percent = max(
            0, min(90, int(appearance.get("window_transparency_percent", 16)))
        )
    except (TypeError, ValueError):
        transparency_percent = 16
    try:
        blur_radius = max(
            0, min(50, int(appearance.get("window_blur_radius", 20)))
        )
    except (TypeError, ValueError):
        blur_radius = 20
    try:
        element_transparency_percent = max(
            0,
            min(
                90,
                int(appearance.get("element_transparency_percent", 12)),
            ),
        )
    except (TypeError, ValueError):
        element_transparency_percent = 12
    return (
        bool(appearance.get("window_transparency", True)),
        bool(appearance.get("window_blur", True)),
        transparency_percent,
        blur_radius,
        element_transparency_percent,
    )


def save_window_effect_settings(
    transparency_enabled: bool,
    blur_enabled: bool,
    transparency_percent: int,
    blur_radius: int,
    element_transparency_percent: int,
) -> None:
    settings = load_app_settings()
    appearance = settings.get("appearance")
    if not isinstance(appearance, dict):
        appearance = {}
    appearance["window_transparency"] = bool(transparency_enabled)
    appearance["window_blur"] = bool(blur_enabled)
    appearance["window_transparency_percent"] = max(
        0, min(90, int(transparency_percent))
    )
    appearance["window_blur_radius"] = max(0, min(50, int(blur_radius)))
    appearance["element_transparency_percent"] = max(
        0, min(90, int(element_transparency_percent))
    )
    settings["appearance"] = appearance
    save_app_settings(settings)
