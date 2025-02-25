import sys
import os
import logging
import io
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
import requests
import platform
import stat
import subprocess
import tempfile
import zipfile
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QLabel, QSystemTrayIcon, QMenu,
                               QLineEdit, QComboBox, QApplication, QHBoxLayout, QProgressDialog)
from PySide6.QtCore import (QTimer, Qt, Signal, Slot, QObject, QRunnable, QThreadPool, QMetaObject, Q_ARG, QDateTime)
from PySide6.QtGui import QIcon, QAction
import soundfile as sf
from transcriber import Transcriber
from visualizer import WaveformWidget

logger = logging.getLogger(__name__)

class DownloadTask(QRunnable, QObject):
    progress_updated = Signal(int)  # Emits progress percentage (0-100)
    download_complete = Signal()   # Emits when download finishes

    def __init__(self, url, file_path):
        QRunnable.__init__(self)
        QObject.__init__(self)
        self.url = url
        self.file_path = file_path
        self.canceled = False

    def run(self):
        try:
            response = requests.get(self.url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(self.file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.canceled:
                        break
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded / total_size) * 100)
                            self.progress_updated.emit(progress)
            if not self.canceled:
                self.download_complete.emit()
        except Exception as e:
            logger.error(f"Download failed: {e}")

class RecordingWindow(QDialog):
    def __init__(self, recorder, shortcut, cancel_shortcut):
        super().__init__()
        self.recorder = recorder
        self.state = 'recording'
        self.setWindowTitle("Recording")
        self.setMinimumSize(400, 150)
        self.setStyleSheet("background-color: #333333;")
        layout = QVBoxLayout(self)
        self.visualizer = WaveformWidget(width=400, height=100)
        layout.addWidget(self.visualizer)
        status_timer_layout = QHBoxLayout()
        self.status_label = QLabel("Recording...")
        self.status_label.setStyleSheet("font-size: 18px; color: white;")
        status_timer_layout.addWidget(self.status_label)
        status_timer_layout.addStretch()
        self.timer_label = QLabel("00:00")
        self.timer_label.setStyleSheet("font-size: 16px; color: white;")
        status_timer_layout.addWidget(self.timer_label)
        layout.addLayout(status_timer_layout)
        self.shortcut_label = QLabel(f"Start/Stop: {shortcut} | Cancel: {cancel_shortcut}")
        self.shortcut_label.setStyleSheet("font-size: 12px; color: lightgray;")
        layout.addWidget(self.shortcut_label)
        self.recorder.amplitude_ready.connect(self.push_amplitude)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.start_time = QDateTime.currentDateTime()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)

    def switch_to_processing(self):
        self.state = 'processing'
        self.status_label.setText("Processing...")
        self.timer_label.hide()
        self.visualizer.set_mode('processing')

    @Slot(float)
    def push_amplitude(self, amplitude):
        if self.state == 'recording':
            self.visualizer.push_amplitude(amplitude)

    def update_timer(self):
        if self.state == 'recording':
            now = QDateTime.currentDateTime()
            elapsed = self.start_time.secsTo(now)
            minutes = elapsed // 60
            seconds = elapsed % 60
            self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")

    def closeEvent(self, event):
        self.timer.stop()
        self.visualizer.stop()
        event.accept()

class RecorderWorker(QRunnable):
    def __init__(self, recorder):
        super().__init__()
        self.recorder = recorder

    def run(self):
        stream = sd.InputStream(callback=self.recorder.audio_callback, channels=1, dtype='float32', samplerate=16000)
        with stream:
            while self.recorder.is_recording:
                sd.sleep(100)
        QMetaObject.invokeMethod(self.recorder, "emit_worker_stopped", Qt.QueuedConnection)

class TranscriptionTask(QRunnable):
    def __init__(self, recorder, audio_data):
        super().__init__()
        self.recorder = recorder
        self.audio_bytes = audio_data.getvalue()

    def run(self):
        try:
            with io.BytesIO(self.audio_bytes) as audio_data:
                result = self.recorder.transcriber.transcribe(audio_data)
            transcription = result["text"]
            detected_language = result["language"]
            if transcription and transcription.strip():
                QMetaObject.invokeMethod(
                    self.recorder,
                    "handle_transcription",
                    Qt.QueuedConnection,
                    Q_ARG(str, transcription),
                    Q_ARG(str, detected_language)
                )
            else:
                logger.warning("Transcription was empty")
        except Exception as e:
            logger.error("Transcription error: %s", e)

class AudioRecorder(QObject):
    transcription_complete = Signal()
    amplitude_ready = Signal(float)
    worker_stopped = Signal()

    def __init__(self, config, app):
        super().__init__()
        self.app = app
        self.config = config
        self.recording_window = None
        self.is_recording = False
        self.canceled = False
        self.hotkey_id = None
        self.cancel_hotkey_id = None
        self.audio_data = io.BytesIO()
        self.pending_settings = False
        self.models_dir = os.path.join(os.path.expanduser("~"), ".fluidwhisper", "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        self.model_options = {
            "normal": {
                "name": "ggml-large-v3-turbo-q5_0.bin",
                "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin?download=true"
            },
            "pro": {
                "name": "ggml-large-v3-turbo-q8_0.bin",
                "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q8_0.bin?download=true"
            },
            "ultra": {
                "name": "ggml-large-v3-turbo.bin",
                "url": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin?download=true"
            }
        }
        
        self.download_model(self.config.get('model', 'ultra'))
        self.executable_path = self.setup_executable()
        model_key = self.config.get('model', 'ultra')
        self.model_path = os.path.join(self.models_dir, self.model_options[model_key]["name"])
        
        self.server_process = None
        self.transcriber = None
        self.threadpool = QThreadPool()
        self.setup_hotkeys()
        self.setup_system_tray()
        self.worker_stopped.connect(self.process_audio_data)
        self.inactivity_timer = QTimer(self)
        self.inactivity_timer.setInterval(300000)
        self.inactivity_timer.timeout.connect(self.stop_server)
        self.app.aboutToQuit.connect(self.cleanup)

    def setup_executable(self):
        bin_dir = os.path.join(os.path.expanduser("~"), ".fluidwhisper", "bin")
        os.makedirs(bin_dir, exist_ok=True)
        system, arch = platform.system(), platform.machine().lower()
        if system == "Windows" and arch in ("x86_64", "amd64"):
            try:
                subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                binary_info = {
                    "zip_filename": "whisper-server-cublas-12.2.0-bin-x64.zip",
                    "exe_name": "whisper-server.exe",
                    "url": "https://github.com/davidirhs/FluidWhisper/releases/download/utilities/whisper-cublas-12.2.0-bin-x64.zip"
                }
            except Exception:
                binary_info = {
                    "zip_filename": "whisper-server-bin-x64.zip",
                    "exe_name": "whisper-server.exe",
                    "url": "https://github.com/davidirhs/FluidWhisper/releases/download/utilities/whisper-bin-x64.zip"
                }
        else:
            raise RuntimeError(f"Unsupported platform: {system} {arch}")
        
        exe_path = os.path.join(bin_dir, binary_info["exe_name"])
        if os.path.exists(exe_path):
            logger.info(f"Executable found at {exe_path}")
            return exe_path
        
        zip_path = os.path.join(bin_dir, binary_info["zip_filename"])
        success = self.download_with_progress("Whisper CPP executable", binary_info["url"], zip_path)
        if not success:
            raise RuntimeError("Executable download canceled or failed")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(bin_dir)
        os.remove(zip_path)
        if not os.path.exists(exe_path):
            raise FileNotFoundError(f"Executable {binary_info['exe_name']} not found in {bin_dir}")
        os.chmod(exe_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        logger.info(f"Extracted to {exe_path}")
        return exe_path

    def download_model(self, key):
        model_info = self.model_options.get(key)
        if not model_info:
            logger.error(f"Invalid model key: {key}. Using 'ultra'.")
            model_info = self.model_options["ultra"]
            self.config['model'] = "ultra"
        file_path = os.path.join(self.models_dir, model_info["name"])
        if os.path.exists(file_path):
            return
        success = self.download_with_progress(f"{key} model", model_info["url"], file_path)
        if not success:
            raise RuntimeError(f"Model '{key}' download canceled or failed")

    @Slot()
    def toggle_recording(self):
        if self.pending_settings:
            return
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    @Slot()
    def cancel_recording(self):
        if not self.is_recording:
            return
        self.canceled = True
        self.is_recording = False
        if self.recording_window:
            self.recording_window.close()
            self.recording_window = None
        self.audio_data = io.BytesIO()

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        self.canceled = False
        self.audio_data = io.BytesIO()
        shortcut = self.config.get('shortcut', 'alt+shift+r')
        cancel_shortcut = self.config.get('cancel_shortcut', 'esc')
        self.recording_window = RecordingWindow(self, shortcut, cancel_shortcut)
        self.recording_window.show()
        self.recorder_worker = RecorderWorker(self)
        self.threadpool.start(self.recorder_worker)
        self.ensure_server_running()

    def stop_recording(self):
        self.is_recording = False

    def audio_callback(self, indata, frames, time, status):
        if status:
            logger.warning(status)
        self.audio_data.write(indata.tobytes())
        amplitude = float(np.sqrt(np.mean(indata**2)))
        self.amplitude_ready.emit(amplitude)

    @Slot()
    def emit_worker_stopped(self):
        self.worker_stopped.emit()

    @Slot()
    def process_audio_data(self):
        if not self.canceled:
            self.audio_data.seek(0)
            wav_buffer = io.BytesIO()
            audio_array = np.frombuffer(self.audio_data.getvalue(), dtype=np.float32)
            sf.write(wav_buffer, audio_array, 16000, format='WAV', subtype='PCM_16')
            wav_buffer.seek(0)
            task = TranscriptionTask(self, wav_buffer)
            self.threadpool.start(task)
            self.inactivity_timer.start()
            if self.recording_window:
                self.recording_window.switch_to_processing()
        else:
            if self.recording_window:
                self.recording_window.close()
                self.recording_window = None

    def setup_hotkeys(self):
        try:
            if self.hotkey_id:
                keyboard.remove_hotkey(self.hotkey_id)
            if self.cancel_hotkey_id:
                keyboard.remove_hotkey(self.cancel_hotkey_id)
            shortcut = self.config.get('shortcut', 'alt+shift+r')
            cancel_shortcut = self.config.get('cancel_shortcut', 'esc')
            self.hotkey_id = keyboard.add_hotkey(
                shortcut,
                lambda: QMetaObject.invokeMethod(self, "toggle_recording", Qt.QueuedConnection)
            )
            self.cancel_hotkey_id = keyboard.add_hotkey(
                cancel_shortcut,
                lambda: QMetaObject.invokeMethod(self, "cancel_recording", Qt.QueuedConnection)
            )
        except Exception as e:
            logger.error(f"Failed to set up hotkeys: {e}")

    def setup_system_tray(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "assets", "FluidWhisper.ico")
        self.tray_icon = QSystemTrayIcon(QIcon(icon_path) if os.path.exists(icon_path) else QIcon(),
                                        QApplication.instance())
        self.tray_icon.setToolTip("FluidWhisper")
        menu = QMenu()
        settings_action = QAction("Settings", self.tray_icon)
        settings_action.triggered.connect(self._open_settings_dialog)
        menu.addAction(settings_action)
        exit_action = QAction("Exit", self.tray_icon)
        exit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(exit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    @Slot(str, str)
    def handle_transcription(self, transcription, detected_language):
        if self.recording_window:
            self.recording_window.close()
            self.recording_window = None
        pyperclip.copy(transcription)
        keyboard.press_and_release('ctrl+v')

    def stop_server(self):
        if self.server_process and self.server_process.poll() is None:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            logger.info("Server stopped")
            self.server_process = None
            self.transcriber = None

    def ensure_server_running(self):
        if not self.server_process or self.server_process.poll() is not None:
            language = self.config.get('language', 'auto')
            logger.info(f"Starting server with language set in config: {language}")
            # Use os.devnull to suppress server output
            with open(os.devnull, 'w') as devnull:
                self.server_process = subprocess.Popen(
                    [self.executable_path, "-m", self.model_path, "--host", "127.0.0.1", "--port", "8080", "-t", "8"],
                    stdout=devnull,
                    stderr=devnull,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            import time
            time.sleep(1)  # Give the server time to start
            if self.server_process.poll() is not None:
                raise RuntimeError("Server failed to start (check server configuration or binary)")
            logger.info("Server started successfully")
            self.transcriber = Transcriber(server_url="http://127.0.0.1:8080/inference", language=language)
            logger.info(f"Transcriber initialized with language: {self.transcriber.language}")


    def cleanup(self):
        self.stop_server()
        if self.hotkey_id:
            keyboard.remove_hotkey(self.hotkey_id)
        if self.cancel_hotkey_id:
            keyboard.remove_hotkey(self.cancel_hotkey_id)

    def _open_settings_dialog(self):
        dialog = QDialog()
        dialog.setWindowTitle("Settings")
        dialog.resize(400, 500)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Recording Shortcut:"))
        shortcut_input = QLineEdit(self.config.get('shortcut', 'alt+shift+r'))
        layout.addWidget(shortcut_input)
        layout.addWidget(QLabel("Cancel Shortcut:"))
        cancel_shortcut_input = QLineEdit(self.config.get('cancel_shortcut', 'esc'))
        layout.addWidget(cancel_shortcut_input)
        layout.addWidget(QLabel("Language (leave empty for auto-detection):"))
        language_combo = QComboBox()
        languages = [("", "auto"), ("English", "en"), ("Spanish", "es")]
        for display, code in languages:
            language_combo.addItem(display or "Auto", code)
        current_language = self.config.get('language', "auto")
        index = language_combo.findData(current_language)
        if index != -1:
            language_combo.setCurrentIndex(index)
        layout.addWidget(language_combo)
        layout.addWidget(QLabel("Model:"))
        model_combo = QComboBox()
        model_options = [
            ("Normal - Fastest, less accurate (574 MB)", "normal"),
            ("Pro - Balanced (874 MB)", "pro"),
            ("Ultra - Most accurate (1.62 GB)", "ultra")
        ]
        for display, key in model_options:
            model_combo.addItem(display, key)
        current_model = self.config.get('model', "ultra")
        index = model_combo.findData(current_model)
        if index != -1:
            model_combo.setCurrentIndex(index)
        layout.addWidget(model_combo)
        save_button = QPushButton("Save")
        def save_settings():
            self.pending_settings = True
            self.config['shortcut'] = shortcut_input.text()
            self.config['cancel_shortcut'] = cancel_shortcut_input.text()
            new_language = language_combo.currentData()
            self.config['language'] = new_language
            self.config['model'] = model_combo.currentData()
            logger.info(f"Saving settings with language: {self.config['language']}")
            self.setup_hotkeys()
            from config_manager import save_config
            save_config(self.config)
            self.download_model(self.config['model'])
            self.model_path = os.path.join(self.models_dir, self.model_options[self.config['model']]["name"])
            self.stop_server()
            self.ensure_server_running()
            self.pending_settings = False
            dialog.accept()
        save_button.clicked.connect(save_settings)
        layout.addWidget(save_button)
        dialog.exec()

    def download_with_progress(self, description, url, file_path):
        progress_dialog = QProgressDialog(f"Downloading {description}...", "Cancel", 0, 100)
        progress_dialog.setWindowModality(Qt.ApplicationModal)
        progress_dialog.setMinimumDuration(0)
        
        task = DownloadTask(url, file_path)
        task.progress_updated.connect(progress_dialog.setValue)
        task.download_complete.connect(progress_dialog.accept)
        progress_dialog.canceled.connect(lambda: setattr(task, 'canceled', True))
        
        self.threadpool.start(task)
        result = progress_dialog.exec()
        
        if result != QDialog.Accepted:
            logger.info(f"Download of {description} was canceled")
            if os.path.exists(file_path):
                os.remove(file_path)
            return False
        return True