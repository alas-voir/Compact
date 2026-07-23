from PyQt6.QtCore import QEvent, QObject, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QDialog


class ApplicationWindowShortcutFilter(QObject):
    """Provide native close/quit shortcuts even inside modal event loops."""

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() != QEvent.Type.KeyPress
            or event.isAutoRepeat()
            or not self._command_modifier_active(event)
        ):
            return super().eventFilter(watched, event)

        if event.key() == Qt.Key.Key_W:
            self.close_active_window()
            event.accept()
            return True
        if event.key() == Qt.Key.Key_Q:
            self.quit_application()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    @staticmethod
    def _command_modifier_active(event) -> bool:
        command_modifiers = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        return bool(event.modifiers() & command_modifiers)

    @staticmethod
    def close_active_window() -> None:
        active_window = (
            QApplication.activeModalWidget()
            or QApplication.activeWindow()
        )
        if isinstance(active_window, QDialog):
            active_window.reject()
        elif active_window is not None:
            active_window.close()

    @staticmethod
    def quit_application() -> None:
        app = QApplication.instance()
        if app is None:
            return

        # reject() explicitly terminates each nested QDialog.exec() event loop.
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog):
                widget.reject()
        for widget in QApplication.topLevelWidgets():
            if not isinstance(widget, QDialog):
                widget.close()
        QTimer.singleShot(0, lambda: app.exit(0))
