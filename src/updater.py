import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


GITHUB_REPOSITORY = "ZERv3/Compact"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"


def version_tuple(version: str) -> tuple[int, ...]:
    normalized = str(version).strip().lower().lstrip("v")
    parts = []
    for component in normalized.split("."):
        digits = "".join(character for character in component if character.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts or [0])


def is_newer_version(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def select_release_asset(release: dict) -> dict | None:
    assets = [asset for asset in release.get("assets", []) if isinstance(asset, dict)]
    system = sys.platform
    machine = platform.machine().lower()
    if system == "darwin":
        platform_words = ("mac", "macos", "darwin", "osx")
        extensions = (".zip", ".dmg")
    elif system.startswith("win"):
        platform_words = ("win", "windows")
        extensions = (".exe", ".msi", ".zip")
    else:
        platform_words = ("linux",)
        extensions = (".appimage", ".deb", ".rpm", ".zip")
    architecture_words = (
        ("arm64", "aarch64", "universal")
        if machine in {"arm64", "aarch64"}
        else ("x64", "x86_64", "amd64", "universal")
    )

    def score(asset: dict) -> int:
        name = str(asset.get("name") or "").lower()
        if not name.endswith(extensions):
            return -1
        has_platform_name = any(word in name for word in platform_words)
        if name.endswith(".zip") and not has_platform_name:
            return -1
        value = 0
        if "compact" in name:
            value += 8
        if has_platform_name:
            value += 6
        if any(word in name for word in architecture_words):
            value += 4
        if name.endswith(".zip"):
            value += 2
        return value

    ranked = sorted(((score(asset), asset) for asset in assets), key=lambda item: item[0], reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] >= 0 else None


class ReleaseCheckWorker(QThread):
    update_available = pyqtSignal(object)
    no_update = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, current_version: str) -> None:
        super().__init__()
        self.current_version = current_version

    def run(self) -> None:
        request = urllib.request.Request(
            LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Compact-Updater",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                release = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                self.no_update.emit("")
            else:
                self.failed.emit(str(error))
            return
        except Exception as error:
            self.failed.emit(str(error))
            return
        tag = str(release.get("tag_name") or "").strip()
        if not tag:
            self.failed.emit("GitHub release does not contain a version tag")
            return
        if not is_newer_version(tag, self.current_version):
            self.no_update.emit(tag)
            return
        asset = select_release_asset(release)
        if asset is None:
            self.failed.emit("The latest release has no compatible application package")
            return
        release["selected_asset"] = asset
        self.update_available.emit(release)


class ReleaseDownloadWorker(QThread):
    progress_changed = pyqtSignal(int)
    downloaded = pyqtSignal(str, object)
    failed = pyqtSignal(str)

    def __init__(self, release: dict) -> None:
        super().__init__()
        self.release = release

    def run(self) -> None:
        asset = self.release["selected_asset"]
        url = str(asset.get("browser_download_url") or "")
        name = Path(str(asset.get("name") or "Compact-update")).name
        if not url.startswith("https://github.com/"):
            self.failed.emit("GitHub returned an invalid download address")
            return
        output_dir = Path(tempfile.mkdtemp(prefix="compact-update-"))
        output_path = output_dir / name
        request = urllib.request.Request(url, headers={"User-Agent": "Compact-Updater"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response, output_path.open("wb") as target:
                total = int(response.headers.get("Content-Length") or 0)
                downloaded = 0
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    target.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self.progress_changed.emit(min(100, downloaded * 100 // total))
            digest = str(asset.get("digest") or "")
            if digest.startswith("sha256:"):
                actual = hashlib.sha256(output_path.read_bytes()).hexdigest()
                if actual.casefold() != digest.split(":", 1)[1].casefold():
                    raise ValueError("SHA-256 checksum mismatch")
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.progress_changed.emit(100)
        self.downloaded.emit(str(output_path), self.release)


def launch_downloaded_update(package_path: str) -> tuple[bool, str]:
    package = Path(package_path)
    if sys.platform == "darwin" and package.suffix.lower() == ".zip" and getattr(sys, "frozen", False):
        current_app = Path(sys.executable).resolve().parents[2]
        if current_app.suffix.lower() != ".app":
            return False, "Could not locate the current application bundle"
        if not os.access(current_app.parent, os.W_OK):
            subprocess.Popen(["/usr/bin/open", "-R", str(package)])
            return False, "The update was downloaded. Move it to Applications manually."
        work_dir = package.parent / "install"
        work_dir.mkdir(exist_ok=True)
        script = package.parent / "install-update.command"
        quoted = {key: shlex.quote(str(value)) for key, value in {
            "package": package, "work": work_dir, "app": current_app,
            "backup": current_app.with_name(current_app.name + ".previous"),
        }.items()}
        script.write_text(
            "#!/bin/sh\n"
            f"while kill -0 {os.getpid()} 2>/dev/null; do sleep 1; done\n"
            f"rm -rf {quoted['work']} && mkdir -p {quoted['work']}\n"
            f"/usr/bin/unzip -q {quoted['package']} -d {quoted['work']} || exit 1\n"
            f"NEW_APP=$(find {quoted['work']} -maxdepth 3 -name 'Compact.app' -print -quit)\n"
            "[ -n \"$NEW_APP\" ] || exit 1\n"
            f"rm -rf {quoted['backup']}\n"
            f"mv {quoted['app']} {quoted['backup']} || exit 1\n"
            f"mv \"$NEW_APP\" {quoted['app']} || {{ mv {quoted['backup']} {quoted['app']}; exit 1; }}\n"
            f"/usr/bin/open {quoted['app']}\n",
            encoding="utf-8",
        )
        script.chmod(0o700)
        subprocess.Popen(["/bin/sh", str(script)], start_new_session=True)
        return True, ""
    if package.suffix.lower() in {".dmg", ".exe", ".msi", ".appimage", ".deb", ".rpm"}:
        if sys.platform == "darwin":
            subprocess.Popen(["/usr/bin/open", str(package)])
        elif sys.platform.startswith("win"):
            os.startfile(str(package))
        else:
            subprocess.Popen(["xdg-open", str(package)])
        return False, "The downloaded installer has been opened"
    return False, "The update was downloaded, but must be installed manually"
