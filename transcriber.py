import requests
import logging
import io

logger = logging.getLogger(__name__)

class Transcriber:
    def __init__(self, server_url, language="auto"):
        self.server_url = server_url
        self.language = language

    def transcribe(self, audio_data):
        """Transcribe audio using the /inference endpoint with language handling."""
        try:
            # Prepare multipart form data
            files = {
                "file": ("audio.wav", audio_data.getvalue(), "audio/wav"),
                "task": (None, "transcribe"),
            }

            # Handle language parameter
            if self.language == "auto":
                # Explicitly pass "auto" to trigger server-side language detection
                files["language"] = (None, "auto")
                logger.info("Transcribing with auto language detection")
            else:
                # Use the specified language (e.g., "es" for Spanish)
                files["language"] = (None, self.language)
                logger.info(f"Transcribing with specified language: {self.language}")

            # Send transcription request to /inference
            response = requests.post(self.server_url, files=files)
            response.raise_for_status()

            # Process the response
            result = response.json()
            transcription = result.get("text", "").strip()
            detected_language = result.get("language", "unknown")
            logger.info(f"Transcription completed. Detected language: {detected_language}")
            return {"text": transcription, "language": detected_language}
        except requests.RequestException as e:
            logger.error(f"Transcription request failed: {e}")
            if e.response is not None:
                logger.error(f"Server response: {e.response.text}")
            raise