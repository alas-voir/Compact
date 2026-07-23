import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QDialog, QWidget

from src.app_shortcuts import ApplicationWindowShortcutFilter


class ApplicationWindowShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.shortcut_filter = ApplicationWindowShortcutFilter(cls.app)
        cls.app.installEventFilter(cls.shortcut_filter)

    def test_command_w_rejects_active_modal_dialog(self) -> None:
        dialog = QDialog()
        dialog.setModal(True)
        dialog.show()
        dialog.activateWindow()
        self.app.processEvents()

        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_W,
            Qt.KeyboardModifier.MetaModifier,
        )
        QApplication.sendEvent(dialog, event)
        self.app.processEvents()

        self.assertFalse(dialog.isVisible())
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)

    def test_native_macos_command_modifier_is_accepted(self) -> None:
        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_W,
            Qt.KeyboardModifier.ControlModifier,
        )

        self.assertTrue(self.shortcut_filter._command_modifier_active(event))

    def test_quit_rejects_dialogs_and_closes_windows(self) -> None:
        window = QWidget()
        dialog = QDialog(window)
        window.show()
        dialog.show()
        self.app.processEvents()

        self.shortcut_filter.quit_application()
        self.app.processEvents()

        self.assertFalse(dialog.isVisible())
        self.assertFalse(window.isVisible())


if __name__ == "__main__":
    unittest.main()
