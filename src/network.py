import os
import socket
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path

import certifi
from PyQt6.QtCore import QObject, pyqtSignal


CONNECTIVITY_ENDPOINTS = (
    ("www.youtube.com", "https://www.youtube.com/generate_204", "метаданные YouTube"),
    ("i.ytimg.com", "https://i.ytimg.com/generate_204", "обложки треков"),
    (
        "redirector.googlevideo.com",
        "https://redirector.googlevideo.com/",
        "медиапотоки YouTube",
    ),
)


def configure_network_security() -> Path:
    """Use the bundled CA store for yt-dlp, urllib, and other HTTPS clients."""
    ca_bundle = Path(certifi.where()).resolve()
    os.environ["SSL_CERT_FILE"] = str(ca_bundle)
    os.environ["REQUESTS_CA_BUNDLE"] = str(ca_bundle)
    ssl._create_default_https_context = lambda: ssl.create_default_context(
        cafile=str(ca_bundle)
    )
    return ca_bundle


def check_https_endpoint(
    domain: str,
    url: str,
    purpose: str,
    *,
    timeout: float = 5.0,
) -> dict[str, object]:
    """Probe DNS, TLS, and HTTP without downloading response content."""
    started_at = time.monotonic()
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "Compact connectivity check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
        return {
            "domain": domain,
            "purpose": purpose,
            "available": True,
            "status": status,
            "error": "",
            "elapsed_seconds": time.monotonic() - started_at,
        }
    except urllib.error.HTTPError as exc:
        # Any HTTP response proves that DNS, TCP, and TLS are working.  Some
        # CDN roots intentionally answer HEAD with 403 or 404.
        return {
            "domain": domain,
            "purpose": purpose,
            "available": True,
            "status": int(exc.code),
            "error": "",
            "elapsed_seconds": time.monotonic() - started_at,
        }
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.gaierror):
            error = "ошибка DNS"
        elif isinstance(reason, (TimeoutError, socket.timeout)):
            error = "тайм-аут подключения"
        elif isinstance(reason, ssl.SSLError):
            error = "ошибка TLS/сертификата"
        else:
            error = str(reason or exc)
    except (TimeoutError, socket.timeout):
        error = "тайм-аут подключения"
    except Exception as exc:
        error = str(exc)
    return {
        "domain": domain,
        "purpose": purpose,
        "available": False,
        "status": 0,
        "error": error,
        "elapsed_seconds": time.monotonic() - started_at,
    }


class ConnectivityCheckWorker(QObject):
    finished = pyqtSignal(object)

    def run(self) -> None:
        results = [
            check_https_endpoint(domain, url, purpose)
            for domain, url, purpose in CONNECTIVITY_ENDPOINTS
        ]
        self.finished.emit(results)
