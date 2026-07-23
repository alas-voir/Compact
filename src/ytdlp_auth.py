import os
import sys
from pathlib import Path


ZEN_BROWSER_KEYS = {"zen", "twilight"}


def _zen_data_roots() -> list[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        return [home / "Library" / "Application Support" / "zen"]
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        return [Path(appdata) / "zen"] if appdata else []
    return [home / ".zen", home / ".config" / "zen"]


def _zen_profile_path(browser: str) -> str:
    """Return the most recently used matching Zen/Zen Twilight profile."""
    candidates: list[Path] = []
    for root in _zen_data_roots():
        for cookie_db in root.glob("Profiles/*/cookies.sqlite"):
            is_twilight = "twilight" in cookie_db.parent.name.casefold()
            if (browser == "twilight") == is_twilight:
                candidates.append(cookie_db)

    if not candidates:
        roots = _zen_data_roots()
        for root in roots:
            if any(root.glob("Profiles/*/cookies.sqlite")):
                # Do not silently use cookies from the other Zen channel.
                return str(root / "Profiles" / f"__{browser}_profile_not_found__")
        existing_root = next((root for root in roots if root.exists()), None)
        return str(existing_root or roots[0]) if roots else ""

    newest_cookie_db = max(candidates, key=lambda path: path.stat().st_mtime)
    return str(newest_cookie_db.parent)


def build_ytdlp_auth_options(cookies_browser: str = "", cookies_file: str = "") -> dict:
    cookie_file = cookies_file.strip()
    if cookie_file:
        cookie_file_path = os.path.abspath(os.path.expanduser(cookie_file))
        if os.path.exists(cookie_file_path):
            return {"cookiefile": cookie_file_path}

    browser = cookies_browser.strip().lower()
    if browser in ZEN_BROWSER_KEYS:
        profile_path = _zen_profile_path(browser)
        if profile_path:
            # Zen and its Twilight channel use Firefox's cookie database
            # format, but yt-dlp does not expose either as a browser name.
            return {"cookiesfrombrowser": ("firefox", profile_path)}
    if browser:
        return {"cookiesfrombrowser": (browser,)}

    return {}
