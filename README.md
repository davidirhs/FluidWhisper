# FluidWhisper

FluidWhisper is a lightweight desktop application designed for recording audio, visualizing waveforms in real time, and transcribing speech using the `faster-whisper` model. Built with Python and Tkinter, it features configurable global hotkeys, an integrated settings window, and system tray integration for seamless operation.

## Features

- **Audio Recording**: Start and stop recording using global hotkeys.
- **Real-time Waveform Visualization**: Monitor audio levels live with an embedded waveform display.
- **Speech Transcription**: Convert recorded audio to text using the `faster-whisper` model.
- **Clipboard Integration**: Automatically copies transcriptions to the clipboard.
- **Customizable Shortcuts & Settings**: Adjust global hotkeys, language settings, and more via an in-app settings window.
- **System Tray Integration**: Access core functions directly from the system tray.

## Prerequisites

- **Python 3.7+**: Ensure you have Python installed.
- **CUDA (Optional)**: For GPU acceleration, ensure CUDA is available. (The default device is set to `cuda` in the configuration.)

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/FluidWhisper.git
cd FluidWhisper
```

### 2. Create and Activate a Virtual Environment
#### Create Virtual Environment:
```bash
python -m venv .venv
```

#### Activate Virtual Environment:
- On macOS/Linux:
  ```bash
  source .venv/bin/activate
  ```
- On Windows:
  ```bash
  .venv\Scripts\activate
  ```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

The application settings are stored in `config.json`. The default configuration includes:

```json
{
  "model_name": "deepdml/faster-whisper-large-v3-turbo-ct2",
  "shortcut": "alt+shift+r",
  "cancel_shortcut": "esc",
  "notify_clipboard_saving": true,
  "log_level": "WARNING",
  "language": "en",
  "device": "cuda"
}
```

You can modify these settings directly in the `config.json` file or through the in-app settings window.


## Running the Application

To launch FluidWhisper, run the following command from the project root:
```bash
python main.py
```
The application will launch in the background with a system tray icon. Use the configured global hotkeys to start and stop recording.

## Project Structure
```
FluidWhisper/
├── .gitignore
├── config.json
├── config_manager.py
├── main.py
├── recorder.py
├── requirements.txt
├── transcriber.py
└── visualizer.py
```
- **`.gitignore`**: Specifies files and directories to be ignored by Git.
- **`config.json`**: Contains the application's configuration settings.
- **`config_manager.py`**: Manages loading and saving configuration settings.
- **`main.py`**: Entry point of the application.
- **`recorder.py`**: Contains the logic for audio recording, system tray integration, and transcription processing.
- **`transcriber.py`**: Implements speech transcription using the `faster-whisper` model.
- **`visualizer.py`**: Provides real-time waveform visualization.

## GitHub Repository Description

FluidWhisper is a Python-based desktop application for audio recording, real-time waveform visualization, and speech transcription using the `faster-whisper` model. With global hotkeys, clipboard integration, and customizable settings, FluidWhisper is ideal for professionals and enthusiasts alike seeking a robust transcription tool.

## Contributing

Contributions are welcome! Please fork the repository, make your changes, and open a pull request with your improvements or bug fixes.

