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
