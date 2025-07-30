from PyQt6 import QtCore, QtGui, QtWidgets
import os

from audio_manager import AudioManager
from settings_manager import SettingsManager
from logger_config import logger
from hotkeyer import PhraseDetector


class CustomWindow(QtWidgets.QWidget):
    def __init__(self, audio_manager, settings_manager):
        super().__init__()
        self.audio_manager = audio_manager
        self.settings = settings_manager
        self.phrase_detector = PhraseDetector()
        self.mode = "merged"  # Default mode

        assets = "assets"
        def img(name): return os.path.join(assets, name)

        self.sans_pixmap = QtGui.QPixmap(img("sans.png"))
        self.spamton_pixmap = QtGui.QPixmap(img("spamton.png"))
        self.tenna_pixmap = QtGui.QPixmap(img("tenna.png"))
        
        self.auto_tts_thread = None
        self.auto_tts_worker = None

        self.setWindowTitle(self.settings.get("app_name"))
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Window)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(940, 530)
        self.is_hidden = False

        self.bg_label = QtWidgets.QLabel(self)
        self.bg_label.setPixmap(QtGui.QPixmap(img("window_frame.png")))
        self.bg_label.setGeometry(0, 0, 940, 530)

        self.topbar_label = QtWidgets.QLabel(self)
        self.topbar_label.setPixmap(QtGui.QPixmap(img("window_topbar.png")))
        self.topbar_label.setGeometry(0, 0, 940, 23)
        self.topbar_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self.min_btn = QtWidgets.QPushButton(self)
        self.min_btn.setGeometry(800, 0, 44, 28)
        self.min_btn.setFlat(True)
        self.min_btn.setStyleSheet("background: transparent; border: none;")
        self.min_img, self.min_hover_img, self.min_press_img = QtGui.QIcon(img("minimize2.png")), QtGui.QIcon(img("minimize2_hover.png")), QtGui.QIcon(img("minimize2_press.png"))
        self.min_btn.setIcon(self.min_img)
        self.min_btn.setIconSize(QtCore.QSize(44, 28))

        self.close_btn = QtWidgets.QPushButton(self)
        self.close_btn.setGeometry(850, 0, 44, 28)
        self.close_btn.setFlat(True)
        self.close_btn.setStyleSheet("background: transparent; border: none;")
        self.close_img, self.close_hover_img, self.close_press_img = QtGui.QIcon(img("close2.png")), QtGui.QIcon(img("close2_hover.png")), QtGui.QIcon(img("close2_press.png"))
        self.close_btn.setIcon(self.close_img)
        self.close_btn.setIconSize(QtCore.QSize(44, 28))

        self.topbar_label.mousePressEvent = self._start_move
        self.topbar_label.mouseMoveEvent = self._do_move

        self.min_btn.enterEvent = lambda e: self.min_btn.setIcon(self.min_hover_img)
        self.min_btn.leaveEvent = lambda e: self.min_btn.setIcon(self.min_img)
        self.min_btn.pressed.connect(lambda: self.min_btn.setIcon(self.min_press_img))
        self.min_btn.released.connect(self._on_minimize_release)

        self.close_btn.enterEvent = lambda e: self.close_btn.setIcon(self.close_hover_img)
        self.close_btn.leaveEvent = lambda e: self.close_btn.setIcon(self.close_img)
        self.close_btn.pressed.connect(lambda: self.close_btn.setIcon(self.close_press_img))
        self.close_btn.released.connect(self._on_close_release)

        self._moving = False
        self._move_offset = QtCore.QPoint()

        # --- Main UI Layout ---
        self.content_frame = QtWidgets.QWidget(self)
        self.content_frame.setGeometry(40, 50, 860, 420)  # Smaller and more centered
        main_layout = QtWidgets.QVBoxLayout(self.content_frame)
        controls_layout = QtWidgets.QGridLayout()
        sound_effects_layout = QtWidgets.QVBoxLayout()
        tts_layout = QtWidgets.QGridLayout()

        # Status Indicator (centered at top of content area)
        self.status_label = QtWidgets.QLabel("Idle", self.content_frame)
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setFixedHeight(32)
        # Softer colors for status bar
        self.status_label.setStyleSheet("background: none; color: #333; background-color: #e6e6b3; font-weight: bold; font-size: 18px; border-radius: 8px; border: 1px solid #bbb;")
        main_layout.addWidget(self.status_label)
        
        # Character indicator
        self.indicator = QtWidgets.QLabel()
        self.indicator.setScaledContents(True)
        self.indicator.setFixedSize(48, 48)
        controls_layout.addWidget(self.indicator, 0, 0)

        # Auto TTS Button
        self.auto_tts_img = QtGui.QIcon(img("KeyerIdle.png"))
        self.auto_tts_img_hover = QtGui.QIcon(img("KeyerHover.png"))
        self.auto_tts_img_press = QtGui.QIcon(img("KeyerPress.png"))
        self.auto_tts_img_active = QtGui.QIcon(img("KeyerIdleAlt.png"))
        self.auto_tts_img_active_hover = QtGui.QIcon(img("KeyerHoverAlt.png"))
        self.auto_tts_img_active_press = QtGui.QIcon(img("KeyerPressAlt.png"))
        
        self.auto_tts_btn = QtWidgets.QPushButton()
        self.auto_tts_btn.setCheckable(True)  # Make the button toggleable
        self.auto_tts_btn.setChecked(False)   # Initial state: off
        self.auto_tts_btn.setIcon(self.auto_tts_img)
        self.auto_tts_btn.enterEvent = lambda e: self.auto_tts_btn.setIcon(self.auto_tts_img_hover)
        self.auto_tts_btn.leaveEvent = lambda e: self.auto_tts_btn.setIcon(self.auto_tts_img)
        self.auto_tts_btn.pressed.connect(lambda: self.auto_tts_btn.setIcon(self.auto_tts_img_press))
        self.auto_tts_btn.setIconSize(QtCore.QSize(48, 48))
        self.auto_tts_btn.setStyleSheet("border: none; background: transparent;")
        self.auto_tts_btn.toggled.connect(self._toggle_auto_tts)
        controls_layout.addWidget(self.auto_tts_btn, 0, 3)

        # Preview Button
        self.preview_btn = QtWidgets.QPushButton()
        self.preview_btn.setCheckable(True)  # Make the button toggleable
        self.preview_btn.setChecked(False)   # Initial state: off
        pv_unactive_icon = QtGui.QIcon(img("mic_off.png"))
        pv_active_icon = QtGui.QIcon(img("mic_on.png"))
        self.preview_btn.setIcon(pv_unactive_icon)
        self.preview_btn.setIconSize(QtCore.QSize(48, 48))
        self.preview_btn.setStyleSheet("border: none; background: transparent;")
        self.preview_btn.toggled.connect(lambda checked: self.preview_btn.setIcon(pv_active_icon if checked else pv_unactive_icon))
        controls_layout.addWidget(self.preview_btn, 0, 4)
        self.preview_btn.toggled.connect(self._toggle_preview)


        # Settings Button
        settings_button = QtWidgets.QPushButton(self)
        settings_button.clicked.connect(self.open_settings)
        settings_button.setStyleSheet("background: transparent; border: none;")
        settings_button.setIcon(QtGui.QIcon(img("gear.png")))
        settings_button.setIconSize(QtCore.QSize(48, 48))
        controls_layout.addWidget(settings_button, 0, 5)

        # Device Controls
        self.mic_menu = QtWidgets.QComboBox()
        self.output_menu = QtWidgets.QComboBox()
        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.clicked.connect(self._start_processing)
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.clicked.connect(self._stop_processing)
        self.stop_button.setEnabled(False)
        controls_layout.addWidget(self.mic_menu, 1, 0, 1, 1)
        controls_layout.addWidget(self.output_menu, 1, 1, 1, 1)
        controls_layout.addWidget(self.start_button, 1, 4)
        controls_layout.addWidget(self.stop_button, 1, 5)

        self.speakers_menu = QtWidgets.QComboBox()
        controls_layout.addWidget(self.speakers_menu, 1, 2, 1, 1)  # Adjust grid position

        # Mode and Volume Controls
        self.mode_menu = QtWidgets.QComboBox()
        self.mode_menu.addItems(["Merged", "Effects Only", "Pass-through"])
        self.mode_menu.currentTextChanged.connect(self._change_mode)
        self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.volume_slider.setRange(-60, 6)
        self.volume_slider.valueChanged.connect(self._update_volume_display)
        self.volume_display_label = QtWidgets.QLabel("-12.0")
        self.stop_all_button = QtWidgets.QPushButton("Stop All Sounds")
        self.stop_all_button.setStyleSheet("""
            QPushButton {
                background-color: #AA0000;
            }
            QPushButton:hover {
                background-color: #E04747; 
            }
            QPushButton:pressed {
                background-color: #FF9191; 
            }
        """)
        self.stop_all_button.clicked.connect(self.audio_manager.stop_all_sounds)
        controls_layout.addWidget(self.mode_menu, 2, 0, 1, 2)
        controls_layout.addWidget(QtWidgets.QLabel("Effects Vol (dB):"), 2, 1)
        controls_layout.addWidget(self.volume_slider, 2, 2)
        controls_layout.addWidget(self.volume_display_label, 2, 4)
        controls_layout.addWidget(self.stop_all_button, 2, 5)

        # Sound Effects Area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        self.sound_grid = QtWidgets.QGridLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        sound_effects_layout.addWidget(QtWidgets.QLabel("Sound Effects"))
        sound_effects_layout.addWidget(scroll_area)

        # TTS Area
        self.tts_input = QtWidgets.QLineEdit()
        self.tts_input.setPlaceholderText("Enter text for TTS...")
        self.generate_tts_button = QtWidgets.QPushButton("Generate TTS")
        self.generate_tts_button.clicked.connect(self._generate_tts)
        self.play_tts_button = QtWidgets.QPushButton("Play TTS")
        self.play_tts_button.clicked.connect(self._play_tts)
        self.play_tts_button.setEnabled(False)
        tts_layout.addWidget(self.tts_input, 0, 0, 1, 4)
        tts_layout.addWidget(self.generate_tts_button, 1, 0, 1, 2)
        tts_layout.addWidget(self.play_tts_button, 1, 2, 1, 2)

        main_layout.addLayout(controls_layout)
        main_layout.addLayout(sound_effects_layout)
        main_layout.addLayout(tts_layout)

        self.populate_devices()
        self.apply_settings(self.settings.config)

        self.content_frame.setStyleSheet("""
            QWidget {
                background-color: transparent;
                color: #eee;
                border-radius: 0px;
            }
            QLineEdit, QComboBox, QSlider, QScrollArea, QScrollBar, QLabel {
                background-color: #222;
                color: #eee;
                border-radius: 0px;
            }
            QPushButton {
                background-color: #111;
                color: #eee;
                border-radius: 0px;
                border: 1px solid #fff;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #333;
                color: #fff;
            }
            QPushButton:pressed {
                background-color: #444;
            }
            QPushButton:disabled {
                background-color: #444;
                color: #888;
                border: 1px solid #888;
            }
            QComboBox QAbstractItemView {
                background-color: #222;
                color: #eee;
                border-radius: 0px;
            }
        """)

    # --- Window management methods ---
    def _start_move(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._moving = True
            self._move_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def _do_move(self, event):
        if self._moving and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._move_offset)
    def mouseReleaseEvent(self, event):
        self._moving = False
    def _on_minimize_release(self):
        if self._is_mouse_over(self.min_btn): self.showMinimized()
        self.min_btn.setIcon(self.min_img)
    def _on_close_release(self):
        if self._is_mouse_over(self.close_btn): self.close()
        self.close_btn.setIcon(self.close_img)
    def _is_mouse_over(self, widget):
        return widget.rect().contains(widget.mapFromGlobal(QtGui.QCursor.pos()))
    def closeEvent(self, event):
        if self.audio_manager.is_running: self._stop_processing()
        QtWidgets.QApplication.quit()

    # --- App widgets ---
    def apply_settings(self, config):
        self.audio_manager.reload_config()
        if hasattr(self, 'mic_menu'):
            self.populate_devices()
            initial_db = self.settings.get("effects_volume_db")
            self.volume_slider.setValue(int(initial_db))
            self._update_volume_display(initial_db)
        self.setWindowTitle(config.get("app_name", "DeltaToner"))

    def populate_devices(self):
        input_devs, output_devs = self.audio_manager.get_audio_devices()

        self.mic_menu.clear()
        self.mic_menu.addItems(input_devs or ["No Mic Found"])

        self.output_menu.clear()
        self.output_menu.addItems(output_devs or ["No Output Found"])

        self.speakers_menu.clear()
        self.speakers_menu.addItems(output_devs or ["No Speakers Found"])

        saved_mic = self.settings.get("default_mic_name")
        if saved_mic in input_devs:
            self.mic_menu.setCurrentText(saved_mic)

        saved_output = self.settings.get("virtual_cable_name")
        if saved_output in output_devs:
            self.output_menu.setCurrentText(saved_output)

        saved_speakers = self.settings.get("speakers_name")
        if saved_speakers in output_devs:
            self.speakers_menu.setCurrentText(saved_speakers)

        self._populate_sound_effects()

    def _populate_sound_effects(self):
        sound_path = self.settings.get("sound_effects_path")
        if not os.path.exists(sound_path): os.makedirs(sound_path)
        import re
        # Updated regex for Name#--VSpeakTone.ext
        vspeak_pattern = re.compile(r"^(.*)--VSpeakTone(\d+)\.(ogg|wav|mp3)$", re.IGNORECASE)
        speak_pattern = re.compile(r"^(.*)-SpeakTone\.(ogg|wav|mp3)$", re.IGNORECASE)

        for i in reversed(range(self.sound_grid.count())): 
            self.sound_grid.itemAt(i).widget().setParent(None)
            
        row, col = 0, 0
        for sound_file in os.listdir(sound_path):
            if sound_file.endswith((".ogg", ".wav", ".mp3")) \
                and not speak_pattern.match(sound_file) \
                and not vspeak_pattern.match(sound_file):
                button = QtWidgets.QPushButton(os.path.splitext(sound_file)[0])
                button.clicked.connect(lambda _, sf=sound_file: self.audio_manager.play_sound_effect(sf))
                self.sound_grid.addWidget(button, row, col)
                col += 1
                if col >= 5: row, col = row + 1, 0

    def _toggle_preview(self, checked):
        logger.info(f"Preview toggled: {'ON' if checked else 'OFF'}")
        self.audio_manager.update_preview_enabled(checked)

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        if dlg.exec():
            self.apply_settings(self.settings.config)

    # --- Methods to connect UI to backend logic ---
    def _start_processing(self):
        import sounddevice as sd
        mic_name, output_name = self.mic_menu.currentText(), self.output_menu.currentText()
        speakers_name = self.speakers_menu.currentText()
        try:
            mic_id = sd.query_devices(mic_name, 'input')['index']
            output_id = sd.query_devices(output_name, 'output')['index']
            speakers_id = sd.query_devices(speakers_name, 'output')['index']
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Device Error", f"Could not open selected devices:\n{e}")
            return
        
        preview_enabled = self.preview_btn.isChecked()
        if self.audio_manager.start_audio_processing(mic_id, output_id, preview_output_device_id=speakers_id, preview_enabled=preview_enabled):
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.mic_menu.setEnabled(False)
            self.output_menu.setEnabled(False)
            self.speakers_menu.setEnabled(False)
            self.preview_btn.setEnabled(False)
            self.status_label.setText(f"Running [{self.mode}]")
            self.status_label.setStyleSheet("background: none; color: #222; background-color: #b6e6b3; font-weight: bold; font-size: 18px; border-radius: 8px; border: 1px solid #bbb;")
            self.character = self.settings.get("speaktone_file")[:-4]
            if self.character == "sans-SpeakTone":
                indicator_pixmap = self.sans_pixmap
            elif self.character == "spamton-SpeakTone":
                indicator_pixmap = self.spamton_pixmap
            elif self.character == "tenna--VSpeakTone1":
                indicator_pixmap = self.tenna_pixmap
            self.indicator.setPixmap(indicator_pixmap)

    def _stop_processing(self):
        self.audio_manager.stop_audio_processing()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.mic_menu.setEnabled(True)
        self.output_menu.setEnabled(True)
        self.speakers_menu.setEnabled(True)
        self.preview_btn.setEnabled(True)
        self.status_label.setText("Idle")
        self.status_label.setStyleSheet("background: none; color: #333; background-color: #e6e6b3; font-weight: bold; font-size: 18px; border-radius: 8px; border: 1px solid #bbb;")

    def _change_mode(self, mode_text):
        logger.info(f"Mode: {mode_text}")
        self.mode = mode_text.lower().replace(" ", "_")
        self.audio_manager.mode = mode_text.lower().replace(" ", "_")

    def _update_volume_display(self, value):
        self.volume_display_label.setText(f"{float(value):.1f}")
        self.audio_manager.set_effects_volume(float(value))

    def _generate_tts(self):
        text = self.tts_input.text()
        if text and self.audio_manager.generate_tts_audio(text):
            self.play_tts_button.setEnabled(True)

    def _play_tts(self):
        self.audio_manager.play_generated_tts()


    # Auto TTS
    def closeEvent(self, event):
        # Stop the worker thread if it's running
        if self.auto_tts_thread and self.auto_tts_thread.isRunning():
            self.stop_auto_tts()
        
        if self.audio_manager.is_running: self._stop_processing()
        QtWidgets.QApplication.quit()
    def _toggle_auto_tts(self, checked):
        if checked:
            self.start_auto_tts()
            if self.audio_manager.is_running:
                self.auto_tts_btn.setIcon(self.auto_tts_img_active)
                self.auto_tts_btn.enterEvent = lambda e: self.auto_tts_btn.setIcon(self.auto_tts_img_active_hover)
                self.auto_tts_btn.leaveEvent = lambda e: self.auto_tts_btn.setIcon(self.auto_tts_img_active)
                self.auto_tts_btn.pressed.connect(lambda: self.auto_tts_btn.setIcon(self.auto_tts_img_active_press))
        else:
            self.stop_auto_tts()
            self.auto_tts_btn.setIcon(self.auto_tts_img)
            self.auto_tts_btn.enterEvent = lambda e: self.auto_tts_btn.setIcon(self.auto_tts_img_hover)
            self.auto_tts_btn.leaveEvent = lambda e: self.auto_tts_btn.setIcon(self.auto_tts_img)
            self.auto_tts_btn.pressed.connect(lambda: self.auto_tts_btn.setIcon(self.auto_tts_img_press))
    
    @QtCore.pyqtSlot(str)
    def _on_phrase_detected(self, phrase):
        """This slot is executed in the main thread when the worker emits a signal."""
        if phrase == "exit":
            self.auto_tts_btn.setChecked(False) # This will trigger stop_auto_tts
        elif phrase:
            logger.info(f"Auto TTS generating for phrase: {phrase}")
            if self.audio_manager.generate_tts_audio(phrase):
                self.audio_manager.play_generated_tts()

    def start_auto_tts(self):
        """Starts the background thread for phrase detection."""
        if not self.audio_manager.is_running:
            QtWidgets.QMessageBox.warning(self, "Audio Not Running", "Please start audio processing before using Auto TTS.")
            self.auto_tts_btn.setChecked(False)
            return

        if self.auto_tts_thread is None:
            self.auto_tts_thread = QtCore.QThread()
            self.auto_tts_worker = AutoTTSWorker(self.phrase_detector)
            self.auto_tts_worker.moveToThread(self.auto_tts_thread)

            # Connect signals and slots
            self.auto_tts_thread.started.connect(self.auto_tts_worker.run)
            self.auto_tts_worker.finished.connect(self.auto_tts_thread.quit)
            self.auto_tts_worker.finished.connect(self.auto_tts_worker.deleteLater)
            self.auto_tts_thread.finished.connect(self.auto_tts_thread.deleteLater)
            self.auto_tts_worker.phrase_detected.connect(self._on_phrase_detected)

            self.auto_tts_thread.start()
            logger.info("Auto TTS started.")

    def stop_auto_tts(self):
        """Stops the background thread."""
        if self.auto_tts_worker:
            self.auto_tts_worker.stop()
        if self.auto_tts_thread:
            self.auto_tts_thread.quit()
            self.auto_tts_thread.wait() # Wait for the thread to finish
        
        self.auto_tts_thread = None
        self.auto_tts_worker = None
        logger.info("Auto TTS stopped.")

# --- Worker class to handle blocking tasks in a separate thread ---
class AutoTTSWorker(QtCore.QObject):
    phrase_detected = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, phrase_detector: PhraseDetector):
        super().__init__()
        self.phrase_detector = phrase_detector
        self._is_running = True

    @QtCore.pyqtSlot()
    def run(self):
        """ Main work loop for the thread. """
        logger.info("Auto TTS worker thread started.")
        while self._is_running:
            # listen_for_phrase will block until enter is pressed or stop() is called
            phrase = self.phrase_detector.listen_for_phrase()
            if self._is_running and phrase:
                self.phrase_detected.emit(phrase)
        self.finished.emit()
        logger.info("Auto TTS worker thread finished.")

    def stop(self):
        """ Stops the listener and the loop. """
        self._is_running = False
        self.phrase_detector.stop()

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.settings_manager = settings_manager
        self.config = self.settings_manager.config.copy()
        self.resize(400, 250)

        layout = QtWidgets.QFormLayout(self)

        # App Name
        self.title_entry = QtWidgets.QLineEdit(self.config.get("app_name"))
        layout.addRow("Window Title:", self.title_entry)

        # Default Mic
        input_devices, output_devices = parent.audio_manager.get_audio_devices()
        self.mic_menu = QtWidgets.QComboBox()
        self.mic_menu.addItems(input_devices if input_devices else ["None"])
        saved_mic_device = self.config.get("default_mic_name")
        if saved_mic_device in input_devices:
            self.mic_menu.setCurrentText(saved_mic_device)
        layout.addRow("Default Mic:", self.mic_menu)

        # Default Output
        self.cable_menu = QtWidgets.QComboBox()
        self.cable_menu.addItems(output_devices if output_devices else ["None"])
        saved_output_device = self.config.get("virtual_cable_name")
        if saved_output_device in output_devices:
            self.cable_menu.setCurrentText(saved_output_device)
        layout.addRow("Default Cable INPUT:", self.cable_menu)

        # Speakers device combo box
        self.speakers_menu = QtWidgets.QComboBox()
        self.speakers_menu.addItems(output_devices if output_devices else ["None"])
        saved_speakers = self.config.get("speakers_name")
        if saved_speakers in output_devices:
            self.speakers_menu.setCurrentText(saved_speakers)
        layout.addRow("Default Speakers:", self.speakers_menu)

        # Effects Folder
        self.effects_path_entry = QtWidgets.QLineEdit(self.config.get("sound_effects_path"))
        layout.addRow("Effects Folder:", self.effects_path_entry)

        # TTS Pause
        self.tts_pause_entry = QtWidgets.QLineEdit(str(self.config.get("tts_pause_ms")))
        layout.addRow("TTS Pause (ms):", self.tts_pause_entry)

        tones_path = self.config.get("sound_effects_path", "tones")
        tone_files = []
        if os.path.exists(tones_path):
            for f in os.listdir(tones_path):
                if f.endswith((".ogg", ".wav", ".mp3")) and ("-SpeakTone" in f or "-VSpeakTone" in f):
                    tone_files.append(f)

        import re
        normal_tones = {}
        variated_groups = {}
        vspeak_pattern = re.compile(r"^(.*)--VSpeakTone(\d+)\.(ogg|wav|mp3)$", re.IGNORECASE)
        speak_pattern = re.compile(r"^(.*)-SpeakTone\.(ogg|wav|mp3)$", re.IGNORECASE)
        for f in tone_files:
            m = vspeak_pattern.match(f)
            if m:
                base = m.group(1)
                variated_groups.setdefault(base, []).append(f)
            else:
                m2 = speak_pattern.match(f)
                if m2:
                    base = m2.group(1)
                    normal_tones[base] = f
                else:
                    pass  # Ignore files that don't match either pattern

        self.speaktone_menu = QtWidgets.QComboBox()
        self.speaktone_map = {}

        # Add normal SpeakTones
        for base, fname in normal_tones.items():
            display = os.path.splitext(base)[0]
            self.speaktone_menu.addItem(display)
            self.speaktone_map[display] = fname

        # Add variated SpeakTones (grouped, with indicator)
        for base, files in variated_groups.items():
            display = f"{os.path.splitext(base)[0]} [variated]"
            self.speaktone_menu.addItem(display)
            self.speaktone_map[display] = files[0]


        # Set current selection if present in config
        current_speaktone = self.config.get("speaktone_file", "")
        if current_speaktone:
            for display, fname in self.speaktone_map.items():
                if fname == current_speaktone:
                    self.speaktone_menu.setCurrentText(display)
                    break
        layout.addRow("SpeakTone:", self.speaktone_menu)

        # Buttons
        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Save | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.save_and_close)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)

    def save_and_close(self):
        try:
            tts_pause = int(self.tts_pause_entry.text())
        except ValueError:
            QtWidgets.QMessageBox.critical(self, "Invalid Input", "TTS Pause must be a number (in milliseconds).")
            return

        new_config = self.config.copy()
        new_config["app_name"] = self.title_entry.text()
        new_config["default_mic_name"] = self.mic_menu.currentText()
        new_config["virtual_cable_name"] = self.cable_menu.currentText()
        new_config["sound_effects_path"] = self.effects_path_entry.text()
        new_config["tts_pause_ms"] = tts_pause
        new_config["speakers_name"] = self.speakers_menu.currentText()
        # Save SpeakTone selection
        if self.speaktone_menu.count() > 0:
            selected_display = self.speaktone_menu.currentText()
            new_config["speaktone_file"] = self.speaktone_map[selected_display]
        else:
            new_config["speaktone_file"] = ""

        self.settings_manager.save_config(new_config)
        self.accept()