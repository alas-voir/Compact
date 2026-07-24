import os
import unittest
from unittest.mock import patch

from src.workers import build_app_ytdlp_options, download_progress_percent


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


if __name__ == "__main__":
    unittest.main()
