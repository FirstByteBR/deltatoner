import sys
from PyQt6 import QtWidgets, QtGui
from gui_manager import CustomWindow
from audio_manager import AudioManager
from settings_manager import SettingsManager
from logger_config import logger

def main():
    logger.info("Starting Application with PyQt6 UI...")

    try:
        app = QtWidgets.QApplication(sys.argv)

        # Load custom font after QApplication is created
        font_id = QtGui.QFontDatabase.addApplicationFont("assets/determination.ttf")
        if font_id != -1:
            family = QtGui.QFontDatabase.applicationFontFamilies(font_id)[0]
            app_font = QtGui.QFont(family)
            app.setFont(app_font)
        else:
            print("Failed to load custom font.")

        settings_manager = SettingsManager()
        audio_manager = AudioManager(settings_manager)

        window = CustomWindow(audio_manager, settings_manager)
        window.show()
        sys.exit(app.exec())

    except Exception as e:
        logger.critical(f"An unhandled exception occurred: {e}", exc_info=True)
    finally:
        logger.info("Application closed.")

if __name__ == "__main__":
    main()