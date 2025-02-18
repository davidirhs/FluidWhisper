import tkinter as tk
import threading, queue, time, os, platform, logging, io
import numpy as np
import pyperclip
import sounddevice as sd
import keyboard  # global hotkeys
from pystray import Icon, MenuItem, Menu
from PIL import Image
from transcriber import Transcriber
from concurrent.futures import ThreadPoolExecutor
import soundfile as sf
from visualizer import WaveformFrame  # Use the embedded waveform frame

class RecordingWindow(tk.Toplevel):
    def __init__(self, master, config, toggle_recording_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.title("FluidWhisper Recording")
        self.geometry("350x250")
        self.config_obj = config

        # Compute absolute paths for the icon files
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_png_path = os.path.join(script_dir, "assets", "FluidWhisper.png")
        icon_ico_path = os.path.join(script_dir, "assets", "FluidWhisper.ico")
        
        # Set the icon for the Toplevel window
        try:
            icon_png = tk.PhotoImage(file=icon_png_path)
            self.iconphoto(False, icon_png)
            self._icon = icon_png
            self.iconbitmap(icon_ico_path)
        except Exception as e:
            print("Error setting Toplevel icon:", e)

        # Create an embedded waveform display
        self.waveform = WaveformFrame(self, width=300, height=60, wave_color="white", config=config)
        self.waveform.pack(pady=10)

        # Controls frame for the recording button and shortcut display
        controls_frame = tk.Frame(self)
        controls_frame.pack(pady=10)

        # Button to toggle recording (initially set to "Stop Recording")
        self.record_button = tk.Button(controls_frame, text="Stop Recording", command=toggle_recording_callback, font=("Arial", 14))
        self.record_button.pack(side="left", padx=5)

        # Label showing the global shortcut for starting recording
        shortcut = config.get("shortcut", "alt+shift+r")
        self.shortcut_label = tk.Label(controls_frame, text=f"Shortcut: {shortcut}", font=("Arial", 12))
        self.shortcut_label.pack(side="left", padx=5)

class AudioRecorder:
    def __init__(self, master, config):
        self.master = master
        self.config = config
        self.system_platform = platform.system()
        self.output_folder = "output"
        self.recording_event = threading.Event()
        self.recordings = []  # Buffer for audio data chunks
        self.transcription_queue = queue.Queue()
        self.visualizer = None  # Reference to the embedded waveform frame
        self.recording_window = None

        # Initialize transcriber
        self.transcriber = Transcriber(
            model_name=config.get('model_name'),
            device=config.get('device', 'cuda'),
            log_level=config.get('log_level', 'WARNING'),
            language=config.get('language', 'en')
        )

        self.shortcut = config.get('shortcut', 'alt+shift+r')
        self.cancel_shortcut = config.get('cancel_shortcut', 'esc')
        self.notify_clipboard_saving = config.get('notify_clipboard_saving', True)
        self.logger = logging.getLogger("AudioRecorder")
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Set up global hotkeys and system tray; no main UI is created since the recording window is used
        self.setup_global_shortcut()
        self.setup_cancel_shortcut()
        self.master.after_idle(self.setup_system_tray)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.keep_transcribing = True
        self.executor.submit(self.process_transcriptions)

    def setup_global_shortcut(self):
        """Bind the global hotkey for starting/stopping recording."""
        keyboard.add_hotkey(self.shortcut, self.toggle_recording)
        self.logger.info("Global shortcut set to: %s", self.shortcut)

    def setup_cancel_shortcut(self):
        """Bind the global hotkey for canceling/stopping recording."""
        keyboard.add_hotkey(self.cancel_shortcut, self.stop_recording)
        self.logger.info("Cancel shortcut set to: %s", self.cancel_shortcut)

    def setup_system_tray(self):
        """Create the system tray icon and menu."""
        # Compute the absolute path for the icon image
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, "assets", "FluidWhisper.png")
        try:
            icon_image = Image.open(icon_path)
        except Exception as e:
            self.logger.error("Error loading tray icon: %s", e)
            icon_image = None

        tray_menu = Menu(
            MenuItem(f"Toggle Recording ({self.shortcut})", self.toggle_recording),
            MenuItem("Show Window", self.show_window, default=True),
            MenuItem("Minimize to Tray", self.minimize_to_tray),
            MenuItem("Settings", self.open_options_window),
            MenuItem("Exit", self.exit_application)
        )

        self.tray_icon = Icon(
            name='FluidWhisper',
            icon=icon_image,
            title='FluidWhisper',
            menu=tray_menu
        )
        # Run the tray icon loop detached from the main thread
        threading.Thread(target=self.tray_icon.run_detached, daemon=True).start()

    def minimize_to_tray(self):
        """Hide the main window."""
        self.master.withdraw()
        self.logger.info("Minimized to tray")

    def show_window(self):
        """Restore the main window."""
        self.master.deiconify()

    def open_options_window(self):
        """Open a settings window to update shortcuts and language."""
        options_win = tk.Toplevel(self.master)
        options_win.title("Settings")
        options_win.geometry("350x250")

        tk.Label(options_win, text="Global Shortcut:").pack(pady=5)
        shortcut_entry = tk.Entry(options_win)
        shortcut_entry.insert(0, self.shortcut)
        shortcut_entry.pack()

        tk.Label(options_win, text="Cancel Shortcut:").pack(pady=5)
        cancel_entry = tk.Entry(options_win)
        cancel_entry.insert(0, self.cancel_shortcut)
        cancel_entry.pack()

        tk.Label(options_win, text="Language:").pack(pady=5)
        language_options = {"English": "en", "Spanish": "es"}
        current_language_display = next(
            (name for name, code in language_options.items() if code == self.config.get("language", "en")),
            "English"
        )
        language_var = tk.StringVar(value=current_language_display)
        language_menu = tk.OptionMenu(options_win, language_var, *language_options.keys())
        language_menu.pack()

        def save_options():
            new_shortcut = shortcut_entry.get().strip()
            if new_shortcut and new_shortcut != self.shortcut:
                keyboard.remove_hotkey(self.shortcut)
                self.shortcut = new_shortcut
                self.config["shortcut"] = new_shortcut
                self.setup_global_shortcut()

            new_cancel = cancel_entry.get().strip()
            if new_cancel and new_cancel != self.cancel_shortcut:
                keyboard.remove_hotkey(self.cancel_shortcut)
                self.cancel_shortcut = new_cancel
                self.config["cancel_shortcut"] = new_cancel
                self.setup_cancel_shortcut()

            selected_language_code = language_options.get(language_var.get(), "en")
            if selected_language_code != self.config.get("language", "en"):
                self.config["language"] = selected_language_code
                self.transcriber.language = selected_language_code

            try:
                from config_manager import save_config
                save_config(self.config)
            except Exception as e:
                self.logger.error("Error saving config: %s", e)

            options_win.destroy()

        tk.Button(options_win, text="Save", command=save_options).pack(pady=10)

    def toggle_recording(self):
        """Toggle between start and stop recording."""
        if self.recording_event.is_set():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.recording_event.is_set():
            self.logger.info("Already recording.")
            return

        self.recording_event.set()
        self.logger.info("Recording started.")

        # Create the dedicated recording window with embedded waveform and controls
        self.recording_window = RecordingWindow(self.master, self.config, self.toggle_recording)
        self.visualizer = self.recording_window.waveform

        # Start recording in a background thread
        threading.Thread(target=self.record_audio, daemon=True).start()

    def stop_recording(self):
        if not self.recording_event.is_set():
            return

        self.recording_event.clear()
        sd.stop()
        self.logger.info("Recording stopped.")

        if self.recording_window:
            self.recording_window.destroy()
            self.recording_window = None

        if self.visualizer:
            self.visualizer.stop()
            self.visualizer = None

        # Combine recorded audio and queue it for transcription
        if self.recordings:
            audio_data = np.concatenate(self.recordings)
            audio_data = (audio_data * 32767).astype(np.int16)
            mem_file = io.BytesIO()
            try:
                sf.write(mem_file, audio_data, 44100, format='WAV')
                mem_file.seek(0)
            except Exception as e:
                self.logger.error("Error writing audio file: %s", e)
                return
            self.logger.info("Audio recorded in-memory.")
            self.transcription_queue.put(mem_file)
            self.recordings = []
        else:
            self.logger.warning("No audio data recorded.")

    def record_audio(self):
        """Background thread for continuous audio recording."""
        try:
            with sd.InputStream(callback=self.audio_callback, channels=1, samplerate=44100):
                while self.recording_event.is_set():
                    sd.sleep(100)
        except Exception as e:
            self.logger.error("Recording error: %s", e)

    def audio_callback(self, indata, frames, time_info, status):
        self.recordings.append(indata.copy())
        amplitude = float(np.sqrt(np.mean(indata**2)))
        viz = self.visualizer  # capture the reference
        if viz is not None:
            self.master.after(0, lambda: viz.push_amplitude(amplitude))

    def process_transcriptions(self):
        """Worker thread that transcribes queued audio."""
        while self.keep_transcribing:
            try:
                mem_file = self.transcription_queue.get(timeout=1)
                transcription = self.transcriber.transcribe(mem_file)
                self.logger.info("Transcription: %s", transcription)

                if self.notify_clipboard_saving:
                    pyperclip.copy(transcription)
                    self.master.after(500, self._simulate_paste)

                self.transcription_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error("Transcription error: %s", e)

    def _simulate_paste(self):
        """Simulate a paste action."""
        if self.system_platform == "Windows":
            keyboard.send("ctrl+v")
        elif self.system_platform == "Darwin":
            keyboard.send("command+v")
        else:
            keyboard.send("ctrl+v")

    def exit_application(self):
        """Cleanly shut down the application."""
        self.keep_transcribing = False
        self.executor.shutdown(wait=True)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.transcriber.stop_idle_monitor()
        try:
            from config_manager import save_config
            save_config(self.config)
        except Exception as e:
            self.logger.error("Error saving config: %s", e)
        self.master.quit()

    def on_close(self):
        """Hide the main window on close."""
        self.master.withdraw()
import tkinter as tk
import threading, queue, time, os, platform, logging, io
import numpy as np
import pyperclip
import sounddevice as sd
import keyboard  # global hotkeys
from pystray import Icon, MenuItem, Menu
from PIL import Image
from transcriber import Transcriber
from concurrent.futures import ThreadPoolExecutor
import soundfile as sf
from visualizer import WaveformFrame  # Use the embedded waveform frame

class RecordingWindow(tk.Toplevel):
    def __init__(self, master, config, toggle_recording_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.title("FluidWhisper Recording")
        self.geometry("350x250")
        self.config_obj = config

        # Create an embedded waveform display
        self.waveform = WaveformFrame(self, width=300, height=60, wave_color="white", config=config)
        self.waveform.pack(pady=10)

        # Controls frame for the recording button and shortcut display
        controls_frame = tk.Frame(self)
        controls_frame.pack(pady=10)

        # Button to toggle recording (initially set to "Stop Recording")
        self.record_button = tk.Button(controls_frame, text="Stop Recording", command=toggle_recording_callback, font=("Arial", 14))
        self.record_button.pack(side="left", padx=5)

        # Label showing the global shortcut for starting recording
        shortcut = config.get("shortcut", "alt+shift+r")
        self.shortcut_label = tk.Label(controls_frame, text=f"Shortcut: {shortcut}", font=("Arial", 12))
        self.shortcut_label.pack(side="left", padx=5)

class AudioRecorder:
    def __init__(self, master, config):
        self.master = master
        self.config = config
        self.system_platform = platform.system()
        self.output_folder = "output"
        self.recording_event = threading.Event()
        self.recordings = []  # Buffer for audio data chunks
        self.transcription_queue = queue.Queue()
        self.visualizer = None  # Reference to the embedded waveform frame
        self.recording_window = None

        # Initialize transcriber
        self.transcriber = Transcriber(
            model_name=config.get('model_name'),
            device=config.get('device', 'cuda'),
            log_level=config.get('log_level', 'WARNING'),
            language=config.get('language', 'en')
        )

        self.shortcut = config.get('shortcut', 'alt+shift+r')
        self.cancel_shortcut = config.get('cancel_shortcut', 'esc')
        self.notify_clipboard_saving = config.get('notify_clipboard_saving', True)
        self.logger = logging.getLogger("AudioRecorder")
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Set up global hotkeys and system tray; no main UI is created since the recording window is used
        self.setup_global_shortcut()
        self.setup_cancel_shortcut()
        self.master.after_idle(self.setup_system_tray)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.keep_transcribing = True
        self.executor.submit(self.process_transcriptions)

    def setup_global_shortcut(self):
        """Bind the global hotkey for starting/stopping recording."""
        keyboard.add_hotkey(self.shortcut, self.toggle_recording)
        self.logger.info("Global shortcut set to: %s", self.shortcut)

    def setup_cancel_shortcut(self):
        """Bind the global hotkey for canceling/stopping recording."""
        keyboard.add_hotkey(self.cancel_shortcut, self.stop_recording)
        self.logger.info("Cancel shortcut set to: %s", self.cancel_shortcut)

    def setup_system_tray(self):
        """Create the system tray icon and menu."""
        try:
            icon_image = Image.open('./assets/FluidWhisper.png')
        except Exception as e:
            self.logger.error("Error loading tray icon: %s", e)
            icon_image = None

        tray_menu = Menu(
            MenuItem(f"Toggle Recording ({self.shortcut})", self.toggle_recording),
            MenuItem("Show Window", self.show_window, default=True),
            MenuItem("Minimize to Tray", self.minimize_to_tray),
            MenuItem("Settings", self.open_options_window),
            MenuItem("Exit", self.exit_application)
        )

        self.tray_icon = Icon(
            name='FluidWhisper',
            icon=icon_image,
            title='FluidWhisper',
            menu=tray_menu
        )
        threading.Thread(target=self.tray_icon.run_detached, daemon=True).start()

    def minimize_to_tray(self):
        """Hide the main window."""
        self.master.withdraw()
        self.logger.info("Minimized to tray")

    def show_window(self):
        """Restore the main window."""
        self.master.deiconify()

    def open_options_window(self):
        """Open a settings window to update shortcuts and language."""
        options_win = tk.Toplevel(self.master)
        options_win.title("Settings")
        options_win.geometry("350x250")

        tk.Label(options_win, text="Global Shortcut:").pack(pady=5)
        shortcut_entry = tk.Entry(options_win)
        shortcut_entry.insert(0, self.shortcut)
        shortcut_entry.pack()

        tk.Label(options_win, text="Cancel Shortcut:").pack(pady=5)
        cancel_entry = tk.Entry(options_win)
        cancel_entry.insert(0, self.cancel_shortcut)
        cancel_entry.pack()

        tk.Label(options_win, text="Language:").pack(pady=5)
        language_options = {"English": "en", "Spanish": "es"}
        current_language_display = next(
            (name for name, code in language_options.items() if code == self.config.get("language", "en")),
            "English"
        )
        language_var = tk.StringVar(value=current_language_display)
        language_menu = tk.OptionMenu(options_win, language_var, *language_options.keys())
        language_menu.pack()

        def save_options():
            new_shortcut = shortcut_entry.get().strip()
            if new_shortcut and new_shortcut != self.shortcut:
                keyboard.remove_hotkey(self.shortcut)
                self.shortcut = new_shortcut
                self.config["shortcut"] = new_shortcut
                self.setup_global_shortcut()

            new_cancel = cancel_entry.get().strip()
            if new_cancel and new_cancel != self.cancel_shortcut:
                keyboard.remove_hotkey(self.cancel_shortcut)
                self.cancel_shortcut = new_cancel
                self.config["cancel_shortcut"] = new_cancel
                self.setup_cancel_shortcut()

            selected_language_code = language_options.get(language_var.get(), "en")
            if selected_language_code != self.config.get("language", "en"):
                self.config["language"] = selected_language_code
                self.transcriber.language = selected_language_code

            try:
                from config_manager import save_config
                save_config(self.config)
            except Exception as e:
                self.logger.error("Error saving config: %s", e)

            options_win.destroy()

        tk.Button(options_win, text="Save", command=save_options).pack(pady=10)

    def toggle_recording(self):
        """Toggle between start and stop recording."""
        if self.recording_event.is_set():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.recording_event.is_set():
            self.logger.info("Already recording.")
            return

        self.recording_event.set()
        self.logger.info("Recording started.")

        # Create the dedicated recording window with embedded waveform and controls
        self.recording_window = RecordingWindow(self.master, self.config, self.toggle_recording)
        self.visualizer = self.recording_window.waveform

        # Start recording in a background thread
        threading.Thread(target=self.record_audio, daemon=True).start()

    def stop_recording(self):
        if not self.recording_event.is_set():
            return

        self.recording_event.clear()
        sd.stop()
        self.logger.info("Recording stopped.")

        if self.recording_window:
            self.recording_window.destroy()
            self.recording_window = None

        if self.visualizer:
            self.visualizer.stop()
            self.visualizer = None

        # Combine recorded audio and queue it for transcription
        if self.recordings:
            audio_data = np.concatenate(self.recordings)
            audio_data = (audio_data * 32767).astype(np.int16)
            mem_file = io.BytesIO()
            try:
                sf.write(mem_file, audio_data, 44100, format='WAV')
                mem_file.seek(0)
            except Exception as e:
                self.logger.error("Error writing audio file: %s", e)
                return
            self.logger.info("Audio recorded in-memory.")
            self.transcription_queue.put(mem_file)
            self.recordings = []
        else:
            self.logger.warning("No audio data recorded.")

    def record_audio(self):
        """Background thread for continuous audio recording."""
        try:
            with sd.InputStream(callback=self.audio_callback, channels=1, samplerate=44100):
                while self.recording_event.is_set():
                    sd.sleep(100)
        except Exception as e:
            self.logger.error("Recording error: %s", e)

    def audio_callback(self, indata, frames, time_info, status):
        self.recordings.append(indata.copy())
        amplitude = float(np.sqrt(np.mean(indata**2)))
        # Only push amplitude if the visualizer is still available.
        if self.visualizer is not None:
            self.master.after(0, lambda: self.visualizer and self.visualizer.push_amplitude(amplitude))


    def process_transcriptions(self):
        """Worker thread that transcribes queued audio."""
        while self.keep_transcribing:
            try:
                mem_file = self.transcription_queue.get(timeout=1)
                transcription = self.transcriber.transcribe(mem_file)
                self.logger.info("Transcription: %s", transcription)

                if self.notify_clipboard_saving:
                    pyperclip.copy(transcription)
                    self.master.after(500, self._simulate_paste)

                self.transcription_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error("Transcription error: %s", e)

    def _simulate_paste(self):
        """Simulate a paste action."""
        if self.system_platform == "Windows":
            keyboard.send("ctrl+v")
        elif self.system_platform == "Darwin":
            keyboard.send("command+v")
        else:
            keyboard.send("ctrl+v")

    def exit_application(self):
        """Cleanly shut down the application."""
        self.keep_transcribing = False
        self.executor.shutdown(wait=True)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.transcriber.stop_idle_monitor()
        try:
            from config_manager import save_config
            save_config(self.config)
        except Exception as e:
            self.logger.error("Error saving config: %s", e)
        self.master.quit()

    def on_close(self):
        """Hide the main window on close."""
        self.master.withdraw()
import tkinter as tk
import threading, queue, time, os, platform, logging, io
import numpy as np
import pyperclip
import sounddevice as sd
import keyboard  # global hotkeys
from pystray import Icon, MenuItem, Menu
from PIL import Image
from transcriber import Transcriber
from concurrent.futures import ThreadPoolExecutor
import soundfile as sf
from visualizer import WaveformFrame  # Use the embedded waveform frame

class RecordingWindow(tk.Toplevel):
    def __init__(self, master, config, toggle_recording_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.title("FluidWhisper Recording")
        self.geometry("350x250")
        self.config_obj = config

        # Create an embedded waveform display
        self.waveform = WaveformFrame(self, width=300, height=60, wave_color="white", config=config)
        self.waveform.pack(pady=10)

        # Controls frame for the recording button and shortcut display
        controls_frame = tk.Frame(self)
        controls_frame.pack(pady=10)

        # Button to toggle recording (initially set to "Stop Recording")
        self.record_button = tk.Button(controls_frame, text="Stop Recording", command=toggle_recording_callback, font=("Arial", 14))
        self.record_button.pack(side="left", padx=5)

        # Label showing the global shortcut for starting recording
        shortcut = config.get("shortcut", "alt+shift+r")
        self.shortcut_label = tk.Label(controls_frame, text=f"Shortcut: {shortcut}", font=("Arial", 12))
        self.shortcut_label.pack(side="left", padx=5)

class AudioRecorder:
    def __init__(self, master, config):
        self.master = master
        self.config = config
        self.system_platform = platform.system()
        self.output_folder = "output"
        self.recording_event = threading.Event()
        self.recordings = []  # Buffer for audio data chunks
        self.transcription_queue = queue.Queue()
        self.visualizer = None  # Reference to the embedded waveform frame
        self.recording_window = None

        # Initialize transcriber
        self.transcriber = Transcriber(
            model_name=config.get('model_name'),
            device=config.get('device', 'cuda'),
            log_level=config.get('log_level', 'WARNING'),
            language=config.get('language', 'en')
        )

        self.shortcut = config.get('shortcut', 'alt+shift+r')
        self.cancel_shortcut = config.get('cancel_shortcut', 'esc')
        self.notify_clipboard_saving = config.get('notify_clipboard_saving', True)
        self.logger = logging.getLogger("AudioRecorder")
        self.executor = ThreadPoolExecutor(max_workers=2)

        # Set up global hotkeys and system tray; no main UI is created since the recording window is used
        self.setup_global_shortcut()
        self.setup_cancel_shortcut()
        self.master.after_idle(self.setup_system_tray)
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        self.keep_transcribing = True
        self.executor.submit(self.process_transcriptions)

    def setup_global_shortcut(self):
        """Bind the global hotkey for starting/stopping recording."""
        keyboard.add_hotkey(self.shortcut, self.toggle_recording)
        self.logger.info("Global shortcut set to: %s", self.shortcut)

    def setup_cancel_shortcut(self):
        """Bind the global hotkey for canceling/stopping recording."""
        keyboard.add_hotkey(self.cancel_shortcut, self.stop_recording)
        self.logger.info("Cancel shortcut set to: %s", self.cancel_shortcut)

    def setup_system_tray(self):
        """Create the system tray icon and menu."""
        try:
            icon_image = Image.open('./assets/FluidWhisper.png')
        except Exception as e:
            self.logger.error("Error loading tray icon: %s", e)
            icon_image = None

        tray_menu = Menu(
            MenuItem(f"Toggle Recording ({self.shortcut})", self.toggle_recording),
            MenuItem("Show Window", self.show_window, default=True),
            MenuItem("Minimize to Tray", self.minimize_to_tray),
            MenuItem("Settings", self.open_options_window),
            MenuItem("Exit", self.exit_application)
        )

        self.tray_icon = Icon(
            name='FluidWhisper',
            icon=icon_image,
            title='FluidWhisper',
            menu=tray_menu
        )
        threading.Thread(target=self.tray_icon.run_detached, daemon=True).start()

    def minimize_to_tray(self):
        """Hide the main window."""
        self.master.withdraw()
        self.logger.info("Minimized to tray")

    def show_window(self):
        """Restore the main window."""
        self.master.deiconify()

    def open_options_window(self):
        """Open a settings window to update shortcuts and language."""
        options_win = tk.Toplevel(self.master)
        options_win.title("Settings")
        options_win.geometry("350x250")

        tk.Label(options_win, text="Global Shortcut:").pack(pady=5)
        shortcut_entry = tk.Entry(options_win)
        shortcut_entry.insert(0, self.shortcut)
        shortcut_entry.pack()

        tk.Label(options_win, text="Cancel Shortcut:").pack(pady=5)
        cancel_entry = tk.Entry(options_win)
        cancel_entry.insert(0, self.cancel_shortcut)
        cancel_entry.pack()

        tk.Label(options_win, text="Language:").pack(pady=5)
        language_options = {"English": "en", "Spanish": "es"}
        current_language_display = next(
            (name for name, code in language_options.items() if code == self.config.get("language", "en")),
            "English"
        )
        language_var = tk.StringVar(value=current_language_display)
        language_menu = tk.OptionMenu(options_win, language_var, *language_options.keys())
        language_menu.pack()

        def save_options():
            new_shortcut = shortcut_entry.get().strip()
            if new_shortcut and new_shortcut != self.shortcut:
                keyboard.remove_hotkey(self.shortcut)
                self.shortcut = new_shortcut
                self.config["shortcut"] = new_shortcut
                self.setup_global_shortcut()

            new_cancel = cancel_entry.get().strip()
            if new_cancel and new_cancel != self.cancel_shortcut:
                keyboard.remove_hotkey(self.cancel_shortcut)
                self.cancel_shortcut = new_cancel
                self.config["cancel_shortcut"] = new_cancel
                self.setup_cancel_shortcut()

            selected_language_code = language_options.get(language_var.get(), "en")
            if selected_language_code != self.config.get("language", "en"):
                self.config["language"] = selected_language_code
                self.transcriber.language = selected_language_code

            try:
                from config_manager import save_config
                save_config(self.config)
            except Exception as e:
                self.logger.error("Error saving config: %s", e)

            options_win.destroy()

        tk.Button(options_win, text="Save", command=save_options).pack(pady=10)

    def toggle_recording(self):
        """Toggle between start and stop recording."""
        if self.recording_event.is_set():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.recording_event.is_set():
            self.logger.info("Already recording.")
            return

        self.recording_event.set()
        self.logger.info("Recording started.")

        # Create the dedicated recording window with embedded waveform and controls
        self.recording_window = RecordingWindow(self.master, self.config, self.toggle_recording)
        self.visualizer = self.recording_window.waveform

        # Start recording in a background thread
        threading.Thread(target=self.record_audio, daemon=True).start()

    def stop_recording(self):
        if not self.recording_event.is_set():
            return

        self.recording_event.clear()
        sd.stop()
        self.logger.info("Recording stopped.")

        if self.recording_window:
            self.recording_window.destroy()
            self.recording_window = None

        if self.visualizer:
            self.visualizer.stop()
            self.visualizer = None

        # Combine recorded audio and queue it for transcription
        if self.recordings:
            audio_data = np.concatenate(self.recordings)
            audio_data = (audio_data * 32767).astype(np.int16)
            mem_file = io.BytesIO()
            try:
                sf.write(mem_file, audio_data, 44100, format='WAV')
                mem_file.seek(0)
            except Exception as e:
                self.logger.error("Error writing audio file: %s", e)
                return
            self.logger.info("Audio recorded in-memory.")
            self.transcription_queue.put(mem_file)
            self.recordings = []
        else:
            self.logger.warning("No audio data recorded.")

    def record_audio(self):
        """Background thread for continuous audio recording."""
        try:
            with sd.InputStream(callback=self.audio_callback, channels=1, samplerate=44100):
                while self.recording_event.is_set():
                    sd.sleep(100)
        except Exception as e:
            self.logger.error("Recording error: %s", e)

    def audio_callback(self, indata, frames, time_info, status):
        self.recordings.append(indata.copy())
        amplitude = float(np.sqrt(np.mean(indata**2)))
        # Only push amplitude if the visualizer is still available.
        if self.visualizer is not None:
            self.master.after(0, lambda: self.visualizer.push_amplitude(amplitude))

    def process_transcriptions(self):
        """Worker thread that transcribes queued audio."""
        while self.keep_transcribing:
            try:
                mem_file = self.transcription_queue.get(timeout=1)
                transcription = self.transcriber.transcribe(mem_file)
                self.logger.info("Transcription: %s", transcription)

                if self.notify_clipboard_saving:
                    pyperclip.copy(transcription)
                    self.master.after(500, self._simulate_paste)

                self.transcription_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error("Transcription error: %s", e)

    def _simulate_paste(self):
        """Simulate a paste action."""
        if self.system_platform == "Windows":
            keyboard.send("ctrl+v")
        elif self.system_platform == "Darwin":
            keyboard.send("command+v")
        else:
            keyboard.send("ctrl+v")

    def exit_application(self):
        """Cleanly shut down the application."""
        self.keep_transcribing = False
        self.executor.shutdown(wait=True)
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.transcriber.stop_idle_monitor()
        try:
            from config_manager import save_config
            save_config(self.config)
        except Exception as e:
            self.logger.error("Error saving config: %s", e)
        self.master.quit()

    def on_close(self):
        """Hide the main window on close."""
        self.master.withdraw()
