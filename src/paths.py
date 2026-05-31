from pathlib import Path
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
    return app_base_dir() / ".elenveil"


def user_config_dir() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Elenveil"
    if sys.platform.startswith("win"):
        appdata = Path.home()
        return appdata / "AppData" / "Roaming" / "Elenveil"
    return home / ".config" / "elenveil"


def config_path(*parts: str) -> str:
    return str(user_config_dir().joinpath(*parts))


def project_data_path(*parts: str) -> str:
    return str(project_data_dir().joinpath(*parts))
