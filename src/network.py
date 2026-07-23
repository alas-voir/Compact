import os
import ssl
from pathlib import Path

import certifi


def configure_network_security() -> Path:
    """Use the bundled CA store for yt-dlp, urllib, and other HTTPS clients."""
    ca_bundle = Path(certifi.where()).resolve()
    os.environ["SSL_CERT_FILE"] = str(ca_bundle)
    os.environ["REQUESTS_CA_BUNDLE"] = str(ca_bundle)
    ssl._create_default_https_context = lambda: ssl.create_default_context(
        cafile=str(ca_bundle)
    )
    return ca_bundle
