# FluidWhisper

FluidWhisper is a lightweight, cross-platform audio recording and transcription tool that runs as a standalone executable. It allows you to capture audio with customizable hotkeys, view a real-time waveform during recording, and transcribe speech using an optimized Whisper model. The transcription is automatically copied to your clipboard for immediate use.

## Features

- **Hotkey-Controlled Recording:**  
  Start and stop recording with customizable shortcuts (default: `Alt+Shift+R` to start/stop, `Esc` to cancel).

- **Real-Time Waveform Visualization:**  
  Monitor audio levels with a live waveform display during recording.

- **Fast & Accurate Transcription:**  
  Powered by an optimized Whisper model for efficient speech-to-text conversion.

- **Clipboard Integration:**  
  Transcribed text is copied to your clipboard and auto-pasted for seamless workflows.

- **Customizable Settings:**  
  Adjust hotkeys, language, and model preferences via an intuitive settings dialog.

## Download & Installation

FluidWhisper is distributed as a standalone `.exe` file for Windows. No Python installation or dependencies are required!

1. **Download the Executable:**  
   - Grab the latest release from the [Releases page](#) (replace with actual URL once available).  
   - File: `FluidWhisper-vX.X.X.exe` (version number may vary).

2. **Run the Application:**  
   - Double-click `FluidWhisper-vX.X.X.exe` to launch it.  
   - The app will minimize to your system tray upon startup.

3. **First-Time Setup (Automatic):**  
   - On first run, FluidWhisper will download its transcription model and supporting binaries (internet connection required).  
   - Downloads are stored in `~/.fluidwhisper/` (e.g., `C:\Users\<YourName>\.fluidwhisper\`).

## Usage

1. **Launch FluidWhisper:**  
   Double-click the `.exe` file. It will appear in your system tray (look for the FluidWhisper icon).

2. **Record Audio:**  
   - Press `Alt+Shift+R` (default) to start recording.  
   - A window with a live waveform will appear.  
   - Press `Alt+Shift+R` again to stop, or `Esc` to cancel.

3. **Transcription:**  
   - After stopping, FluidWhisper processes the audio and copies the transcription to your clipboard.  
   - It also auto-pastes the text (simulating `Ctrl+V`) wherever your cursor is active.

4. **Settings:**  
   - Right-click the system tray icon and select **Settings** to customize:  
     - Recording shortcut (e.g., `Alt+Shift+R`)  
     - Cancel shortcut (e.g., `Esc`)  
     - Language (e.g., "auto", "English", "Spanish")  
     - Model (e.g., "Normal", "Pro", "Ultra" - varies by size and accuracy).

5. **Exit:**  
   - Right-click the tray icon and choose **Exit** to close the app.

## Configuration

Settings are saved automatically via the in-app dialog and stored persistently using `QSettings`. On first run, defaults include:

- **Recording Shortcut:** `Alt+Shift+R`  
- **Cancel Shortcut:** `Esc`  
- **Language:** Auto-detect  
- **Model:** Ultra (most accurate, 1.62 GB)  

Files are stored in `~/.fluidwhisper/`:
- **Models:** Pre-trained Whisper models (e.g., `ggml-large-v3-turbo.bin`).  
- **Binaries:** Whisper server executable (e.g., `whisper-server.exe`).

## System Requirements

- **OS:** Windows (64-bit)  
- **RAM:** 4 GB minimum (8 GB+ recommended for "Ultra" model)  
- **Storage:** ~2 GB for models and binaries  
- **Internet:** Required on first run for downloads  
- **GPU (Optional):** NVIDIA GPU with CUDA support for faster transcription (falls back to CPU if unavailable)

## Troubleshooting

- **App Doesn’t Start:**  
  Ensure you have write permissions in your home directory (`C:\Users\<YourName>\`). Check logs in `~/.fluidwhisper/` if available.

- **Hotkeys Not Working:**  
  Adjust them in the Settings dialog; avoid conflicts with other apps.

- **Transcription Slow:**  
  Switch to a lighter model (e.g., "Normal") in Settings if using a CPU or low-memory system.

## For Developers

FluidWhisper is built with Python and PySide6, packaged into an `.exe` using tools like PyInstaller. Source code includes:

- `main.py`: Entry point, system tray, and app setup.  
- `recorder.py`: Audio capture, waveform, and transcription logic.  
- `transcriber.py`: Interfaces with the Whisper server.  
- `visualizer.py`: Real-time waveform rendering.  
- `config_manager.py`: Persistent settings management.

To use from source:
1. Clone the repo: `git clone <repository-url>`  
2. Install dependencies: `pip install -r requirements.txt`  
3. Run: `python main.py`  


## Acknowledgements

- **Whisper.cpp:** For the efficient transcription backend.  
- **PySide6:** For the GUI framework.  
- Thanks to the open-source community for tools and inspiration!