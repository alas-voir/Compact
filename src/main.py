import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from .logger import get_logger, setup_app_logging
from .main_window import MainWindow
from .paths import resource_path


def main() -> None:
    log_path = setup_app_logging()
    logger = get_logger("elenveil.main")
    logger.info("Application startup requested")
    QApplication.setAttribute(
        Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Compact")
    app.setApplicationDisplayName("Compact")
    app_icon_path = resource_path("assets", "icons", "Compact.icns")
    app_icon = QIcon(app_icon_path)
    logger.info("Application icon path: %s | exists=%s", app_icon_path, not app_icon.isNull())
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()
    logger.info("Main window shown | log_path=%s", log_path)
    sys.exit(app.exec())
