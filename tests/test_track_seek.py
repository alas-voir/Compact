import unittest

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication

from src.models import LocalMusicTrack
from src.widgets import RemoteTrackCard


class TrackSeekPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_release_clears_stationary_seek_preview_handle(self) -> None:
        track = LocalMusicTrack(
            title="Track",
            artists="Artist",
            album="Album",
            file_path="/tmp/track.mp3",
            added_at=0.0,
        )
        card = RemoteTrackCard(
            track,
            0,
            {},
            QIcon(),
            compact=False,
        )
        card.resize(600, card.height())
        card.update_playback_state(False, 0.2, is_current=True)
        card.show()
        self.app.processEvents()

        seek_spy = QSignalSpy(card.playback_seek_requested)
        release_position = QPoint(card.width() // 2, card.height() - 2)
        QTest.mousePress(card, Qt.MouseButton.LeftButton, pos=release_position)
        QTest.mouseRelease(card, Qt.MouseButton.LeftButton, pos=release_position)
        self.app.processEvents()

        self.assertEqual(len(seek_spy), 1)
        self.assertFalse(card.playback_seek_dragging)
        self.assertIsNone(card.playback_hover_position)
        self.assertAlmostEqual(card.playback_progress, 0.5, delta=0.01)
        card.close()


if __name__ == "__main__":
    unittest.main()
