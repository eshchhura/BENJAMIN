# jarvis/interfaces/voice_interface.py
# -------------------------------------
# Continuously listens on microphone for wake-word or terminal-based fallback.
# Uses Vosk (offline) or Whisper (offline) for STT, and pyttsx3/Coqui for TTS.
# -------------------------------------

import threading
import queue
import logging
import time

import vosk             # For offline STT
import pyttsx3          # For offline TTS
import speech_recognition as sr  # High-level microphone handling
from jarvis.config import Config

logger = logging.getLogger(__name__)

class VoiceInterface:
    """
    - Continuously listens in the background (separate thread).
    - Detects wake-word (configurable) before transcribing full command.
    - On recognized speech, invokes callback(text, source="voice").
    - Exposes speak(text) to emit TTS.
    """

    def __init__(self, callback):
        self.cfg = Config()
        self.callback = callback
        self.running = False

        # Initialize STT engine (e.g., Vosk)
        model_path = self.cfg.get("assistant", "stt_engine")
        # Example: load a pretrained Vosk model
        try:
            self.vosk_model = vosk.Model("models/vosk-model-small-en-us-0.15")
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
        except Exception as e:
            logger.error("Failed to initialize STT engine: %s", e)
            raise

        # Initialize TTS engine (pyttsx3 or Coqui)
        tts_engine_name = self.cfg.get("assistant", "tts_engine")
        self.tts = pyttsx3.init() if tts_engine_name == "pyttsx3" else None
        # If using Coqui: from coqui_tts import TTS, etc.

    def listen_loop(self):
        """
        Main loop that listens for wake-word, then captures command.
        Runs until self.running = False.
        """
        self.running = True
        wake_word = self.cfg.get("assistant", "wake_word", default="hey jarvis")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)  # initial calibration
        logger.info("VoiceInterface listening for wake-word '%s'...", wake_word)

        while self.running:
            with self.microphone as source:
                try:
                    # Non-blocking listen (small timeout), then process audio
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                except sr.WaitTimeoutError:
                    continue

            try:
                text = self.recognizer.recognize_vosk(audio)
                text = text.lower()
                logger.debug("Raw speech recognized: %s", text)
            except Exception:
                continue

            if wake_word in text:
                # Detected wake-word -> record the full command after beep or immediately
                logger.info("Wake-word detected. Listening for command...")
                # Optionally play a beep sound here
                with self.microphone as source:
                    audio_cmd = self.recognizer.listen(source, timeout=5, phrase_time_limit=7)
                try:
                    command = self.recognizer.recognize_vosk(audio_cmd)
                    logger.info("Command recognized: %s", command)
                    self.callback(command, source="voice")
                except Exception as e:
                    logger.warning("Could not transcribe command: %s", e)

            time.sleep(0.1)

    def speak(self, text: str):
        """
        Convert text → speech (and also print to console).
        """
        if not text:
            return
        # Print to console for clarity
        print(f"[Jarvis]: {text}")
        if self.tts:
            self.tts.say(text)
            self.tts.runAndWait()

    def stop(self):
        self.running = False
