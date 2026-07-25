import os
import unittest
from unittest.mock import patch

from src.workers import (
    build_app_ytdlp_options,
    download_event_diagnostics,
    download_progress_percent,
)


class YtDlpRuntimeTests(unittest.TestCase):
    def test_bundled_runtime_is_passed_to_ytdlp(self) -> None:
        runtime_path = os.path.abspath("bin/deno")
        with patch(
            "src.workers.resolve_javascript_runtime",
            return_value=("deno", runtime_path),
        ):
            options = build_app_ytdlp_options(skip_download=True)

        self.assertEqual(options["js_runtimes"], {"deno": {"path": runtime_path}})
        self.assertTrue(options["skip_download"])
        self.assertEqual(options["socket_timeout"], 20)
        self.assertEqual(options["retries"], 2)
        self.assertEqual(options["fragment_retries"], 2)
        self.assertEqual(options["http_chunk_size"], 10 * 1024 * 1024)

    def test_runtime_network_defaults_can_be_overridden(self) -> None:
        with patch("src.workers.resolve_javascript_runtime", return_value=None):
            options = build_app_ytdlp_options(socket_timeout=15, retries=1)

        self.assertEqual(options["socket_timeout"], 15)
        self.assertEqual(options["retries"], 1)
        self.assertEqual(options["fragment_retries"], 2)

    def test_byte_progress(self) -> None:
        self.assertEqual(
            download_progress_percent(
                {"downloaded_bytes": 25, "total_bytes": 100}
            ),
            25.0,
        )

    def test_fragment_progress_fallback(self) -> None:
        self.assertEqual(
            download_progress_percent({"fragment_index": 3, "fragment_count": 4}),
            75.0,
        )

    def test_formatted_progress_fallback(self) -> None:
        self.assertEqual(
            download_progress_percent({"_percent_str": "\x1b[0;32m 42.5%\x1b[0m"}),
            42.5,
        )

    def test_download_diagnostics_omit_signed_media_url(self) -> None:
        diagnostics = download_event_diagnostics(
            {
                "status": "downloading",
                "downloaded_bytes": 2048,
                "total_bytes": 8192,
                "speed": 1024.5,
                "info_dict": {
                    "url": "https://media.example/video?token=secret",
                    "format_id": "251",
                    "protocol": "https",
                    "ext": "webm",
                },
            }
        )

        self.assertEqual(diagnostics["media_host"], "media.example")
        self.assertEqual(diagnostics["downloaded_bytes"], 2048)
        self.assertNotIn("secret", repr(diagnostics))


if __name__ == "__main__":
    unittest.main()
