import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from .main_window import MainWindow
from .paths import resource_path


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Elenveil")
    app.setApplicationDisplayName("Elenveil")
    app_icon_path = resource_path("assets", "icons", "Elenveil.icns")
    app_icon = QIcon(app_icon_path)
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()
    sys.exit(app.exec())
