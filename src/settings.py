import json
import os
from pathlib import Path

from .paths import config_path, project_data_path


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


def load_app_secrets() -> dict:
    _migrate_project_secrets()
    path = Path(project_data_path("secrets.json"))
    return _read_json_file(path)


def save_app_secrets(secrets: dict) -> None:
    path = Path(project_data_path("secrets.json"))
    _write_json_file(path, secrets, restrict_permissions=True)


def _legacy_secrets_path() -> Path:
    return Path(config_path("secrets.json"))


def _project_secrets_path() -> Path:
    return Path(project_data_path("secrets.json"))


def _migrate_project_secrets() -> None:
    project_path = _project_secrets_path()
    if project_path.exists():
        return

    legacy_path = _legacy_secrets_path()
    legacy_secrets = _read_json_file(legacy_path)
    if legacy_secrets:
        save_app_secrets(legacy_secrets)


def _migrate_spotify_credentials_from_settings() -> None:
    settings = load_app_settings()
    spotify = settings.get("spotify")
    if not isinstance(spotify, dict):
        return

    client_id = str(spotify.get("client_id") or "").strip()
    client_secret = str(spotify.get("client_secret") or "").strip()
    if not client_id and not client_secret:
        return

    secrets = load_app_secrets()
    secrets["spotify"] = {
        "client_id": client_id,
        "client_secret": client_secret,
    }
    save_app_secrets(secrets)

    settings.pop("spotify", None)
    save_app_settings(settings)


def load_spotify_credentials() -> dict[str, str]:
    _migrate_spotify_credentials_from_settings()
    secrets = load_app_secrets()
    spotify = secrets.get("spotify")
    if not isinstance(spotify, dict):
        spotify = {}
    return {
        "client_id": str(spotify.get("client_id") or os.environ.get("SPOTIPY_CLIENT_ID") or "").strip(),
        "client_secret": str(spotify.get("client_secret") or os.environ.get("SPOTIPY_CLIENT_SECRET") or "").strip(),
    }


def save_spotify_credentials(client_id: str, client_secret: str) -> None:
    secrets = load_app_secrets()
    secrets["spotify"] = {
        "client_id": client_id.strip(),
        "client_secret": client_secret.strip(),
    }
    save_app_secrets(secrets)


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
