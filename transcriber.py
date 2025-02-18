import torch
from faster_whisper import WhisperModel
import logging, time, gc, threading

class Transcriber:
    def __init__(self, model_name, device="cuda", language="en", beam_size=7,
                 auto_unload_timeout=300, log_level="WARNING"):
        self.model_name = model_name
        self.device = device
        self.language = language
        self.beam_size = beam_size
        self.auto_unload_timeout = auto_unload_timeout
        self.model = None
        self.last_used = None

        self.logger = logging.getLogger("Transcriber")
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.WARNING))
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(getattr(logging, log_level.upper(), logging.WARNING))
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

        self.logger.info("Initializing Transcriber with device: %s", self.device)
        self.idle_event = threading.Event()
        self.idle_event.clear()
        self.idle_monitor_running = True
        self.idle_monitor_thread = threading.Thread(target=self._idle_monitor_event, daemon=True)
        self.idle_monitor_thread.start()

    def _idle_monitor_event(self):
        while self.idle_monitor_running:
            triggered = self.idle_event.wait(timeout=self.auto_unload_timeout)
            if (not triggered) and self.model is not None and (time.time() - self.last_used) > self.auto_unload_timeout:
                self.logger.info("Model idle for more than %s seconds. Unloading model.", self.auto_unload_timeout)
                self.unload_model()
            self.idle_event.clear()

    def stop_idle_monitor(self):
        self.idle_monitor_running = False
        self.idle_event.set()
        self.idle_monitor_thread.join()

    def load_model(self):
        if self.model is None:
            if self.device == "cuda" and not torch.cuda.is_available():
                self.logger.warning("CUDA not available. Falling back to CPU.")
                self.device = "cpu"
            try:
                self.logger.info("Loading model from: %s on device: %s", self.model_name, self.device)
                self.model = WhisperModel(self.model_name, device=self.device,
                                           compute_type="float16" if self.device == "cuda" else "int8")
                self.last_used = time.time()
                self.idle_event.set()
            except Exception as e:
                self.logger.error("Error loading model: %s", e)
                raise e

    def unload_model(self):
        if self.model is not None:
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                del self.model
                self.model = None
                self.logger.info("Model unloaded from memory.")
            except Exception as e:
                self.logger.error("Error unloading model: %s", e)
            gc.collect()

    def transcribe(self, audio_input):
        try:
            if self.model is None:
                self.load_model()
            self.last_used = time.time()
            segments, info = self.model.transcribe(audio_input, beam_size=self.beam_size, language=self.language)
            transcription = " ".join(segment.text for segment in segments)
            return transcription
        except Exception as e:
            self.logger.error("Error during transcription: %s", e)
            self.unload_model()
            self.load_model()
            segments, info = self.model.transcribe(audio_input, beam_size=self.beam_size, language=self.language)
            transcription = " ".join(segment.text for segment in segments)
            return transcription
