import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ytdlp_auth import build_ytdlp_auth_options


class YtdlpAuthOptionsTests(unittest.TestCase):
    def test_zen_uses_newest_non_twilight_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            zen_profile = root / "Profiles" / "Default"
            twilight_profile = root / "Profiles" / "Default (twilight)"
            zen_profile.mkdir(parents=True)
            twilight_profile.mkdir(parents=True)
            (zen_profile / "cookies.sqlite").touch()
            (twilight_profile / "cookies.sqlite").touch()

            with patch("src.ytdlp_auth._zen_data_roots", return_value=[root]):
                options = build_ytdlp_auth_options("zen")

            self.assertEqual(
                options["cookiesfrombrowser"], ("firefox", str(zen_profile))
            )

    def test_twilight_uses_twilight_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile = root / "Profiles" / "Default (twilight)"
            profile.mkdir(parents=True)
            (profile / "cookies.sqlite").touch()

            with patch("src.ytdlp_auth._zen_data_roots", return_value=[root]):
                options = build_ytdlp_auth_options("twilight")

            self.assertEqual(
                options["cookiesfrombrowser"], ("firefox", str(profile))
            )


if __name__ == "__main__":
    unittest.main()
