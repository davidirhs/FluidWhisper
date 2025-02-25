import sys
import os
import logging
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu ,QMessageBox
from PySide6.QtGui import QIcon, QAction
from recorder import AudioRecorder
from config_manager import load_config

def setup_logging(log_level):
    level = getattr(logging, log_level.upper(), logging.WARNING)
    logger = logging.getLogger()
    logger.setLevel(level)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    setup_logging(config.get('log_level', 'WARNING'))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "assets", "FluidWhisper.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        logging.warning(f"Icon not found at {icon_path}")
    
    try:
        recorder = AudioRecorder(config, app)
    except RuntimeError as e:
        logging.error(f"Initialization failed: {e}")
        QMessageBox.critical(None, "Error", f"Failed to initialize FluidWhisper:\n{e}")
        sys.exit(1)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()