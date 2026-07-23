from pathlib import Path
import shutil
import sys


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> str:
    return str(app_base_dir().joinpath(*parts))


def project_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return user_config_dir()
    return app_base_dir() / ".compact"


def user_config_dir() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        current = home / "Library" / "Application Support" / "Compact"
        legacy = home / "Library" / "Application Support" / "Elenveil"
    elif sys.platform.startswith("win"):
        appdata = home / "AppData" / "Roaming"
        current = appdata / "Compact"
        legacy = appdata / "Elenveil"
    else:
        current = home / ".config" / "compact"
        legacy = home / ".config" / "elenveil"

    if legacy.is_dir():
        for source in legacy.rglob("*"):
            if not source.is_file() or source.name == ".DS_Store":
                continue
            relative_path = source.relative_to(legacy)
            if relative_path == Path("logs", "elenveil.log"):
                relative_path = Path("logs", "compact-legacy.log")
            target = current / relative_path
            if target.exists():
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            except OSError:
                pass
    return current


def config_path(*parts: str) -> str:
    return str(user_config_dir().joinpath(*parts))


def project_data_path(*parts: str) -> str:
    return str(project_data_dir().joinpath(*parts))
