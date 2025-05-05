# voice_assistant.py

# --- Standard Library Imports ---
import os
import logging
from tempfile import NamedTemporaryFile

# --- Third-Party Library Imports ---
import numpy as np
import pyttsx3
import scipy.io.wavfile as wav
import sounddevice as sd
try:
    import whisper # Use openai-whisper if you installed that package specifically
except ImportError:
    print("ERROR: Whisper library not found. Please install it (e.g., 'pip install -U openai-whisper')")
    whisper = None # Set to None so checks later will fail gracefully
except Exception as e:
    print(f"ERROR: Unexpected error importing Whisper: {e}")
    whisper = None

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- VoiceAssistant Class Definition ---
class VoiceAssistant:
    """Handles STT and TTS functionalities."""

    def __init__(self, model_size="base"):
        """Initializes STT and TTS engines."""
        self.model = None
        self.engine = None
        self.stt_ready = False
        self.tts_ready = False
        logger.info(f"Initializing VoiceAssistant (Whisper model: {model_size})")

        # Init Whisper (STT)
        if whisper:
            try:
                logger.info(f"Loading Whisper model: '{model_size}'...")
                self.model = whisper.load_model(model_size)
                self.stt_ready = True
                logger.info(f"Whisper STT model '{model_size}' loaded.")
            except FileNotFoundError: logger.error(f"Whisper model file '{model_size}' not found."); logger.warning("STT disabled.")
            except Exception as e: logger.error(f"Error loading Whisper model '{model_size}': {e}", exc_info=True); logger.warning("STT disabled.")
        else: logger.error("Whisper library unavailable. STT disabled.")

        # Init pyttsx3 (TTS)
        try:
            logger.info("Initializing TTS engine...")
            self.engine = pyttsx3.init()
            if not self.engine: raise RuntimeError("pyttsx3.init() failed.")
            # Optional Config
            # self.engine.setProperty('rate', 180)
            driver = getattr(self.engine, 'driverName', 'Unknown')
            self.tts_ready = True
            logger.info(f"TTS engine initialized (driver: {driver}).")
        except Exception as e:
            logger.error(f"Error initializing TTS engine: {e}", exc_info=True); logger.warning("TTS disabled.")

    def speak(self, text):
        """Speaks text using TTS or prints."""
        if not text: logger.warning("speak() called with empty text."); return
        if self.engine and self.tts_ready:
            logger.info(f"TTS Speaking: '{text[:80]}...'")
            print(f"🤖 Assistant: {text}") # Always print
            try:
                self.engine.stop(); self.engine.say(text); self.engine.runAndWait()
            except Exception as e: logger.error(f"TTS runtime error: {e}", exc_info=True); print(f"🤖 Assistant (TTS runtime error): {text}")
        else: logger.info(f"TTS Unavailable, Printing: {text}"); print(f"🤖 Assistant (TTS unavailable): {text}")

    def listen(self, duration=7, fs=16000, prompt="Listening..."):
        """Records audio, transcribes, returns text or None."""
        logger.debug(f"Listen called (duration={duration}s, prompt='{prompt}')")
        if not self.model or not self.stt_ready:
            logger.error("Listen called but STT not ready."); self.speak("Speech recognition unavailable."); return None
        try: sd.check_input_settings(); logger.debug("Sounddevice check OK.")
        except Exception as e:
            logger.error(f"Sounddevice check failed: {e}", exc_info=True)
            if 'PortAudioError' in str(e) or 'No Default Input' in str(e): self.speak("Microphone access error.")
            else: self.speak("Audio system error.")
            return None

        self.speak(prompt) # Announce listening
        recording_data = None
        try:
            logger.info(f"Recording audio ({duration}s)...")
            recording_data = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait(); logger.info("Recording finished.")
            if recording_data is None or recording_data.size == 0: raise ValueError("Empty audio data.")
        except Exception as e: logger.error(f"Audio recording failed: {e}", exc_info=True); self.speak("Error during recording."); return None

        temp_file_path = None
        try: # Process via temp file
            with NamedTemporaryFile(suffix=".wav", delete=False) as temp_f:
                temp_file_path = temp_f.name
                logger.debug(f"Writing to temp file: {temp_file_path}")
                wav.write(temp_file_path, fs, recording_data)
            logger.info(f"Transcribing {temp_file_path}...")
            result = self.model.transcribe(temp_file_path, fp16=False) # fp16=False for CPU
            transcribed_text = result["text"].strip()
            logger.info(f"Transcription result: '{transcribed_text}'")
            if not transcribed_text: logger.warning("Empty transcription."); self.speak("Didn't catch that. Please repeat."); return None
            return transcribed_text
        except Exception as e: logger.error(f"Processing/Transcription error: {e}", exc_info=True); self.speak("Error processing speech."); return None
        finally: # Cleanup temp file
            if temp_file_path and os.path.exists(temp_file_path):
                try: os.remove(temp_file_path); logger.debug(f"Deleted temp file: {temp_file_path}")
                except Exception as e: logger.error(f"Error deleting temp file '{temp_file_path}': {e}")

if __name__ == '__main__':
    print("--- Running Voice Assistant Direct Test ---")
    va_test = VoiceAssistant(model_size='tiny')
    print(f"STT Ready: {va_test.stt_ready}"); print(f"TTS Ready: {va_test.tts_ready}")
    if va_test.stt_ready and va_test.tts_ready:
        print("\nTesting Speak -> Listen -> Speak Cycle:")
        va_test.speak("Test: Say something after the prompt.")
        command = va_test.listen(duration=5, prompt="TEST: Say something:")
        if command: va_test.speak(f"Test result: Heard '{command}'")
        else: va_test.speak("Test result: Didn't capture command.")
    elif va_test.tts_ready: print("\nTesting Speak Only:"); va_test.speak("TTS test successful.")
    else: print("\nCannot perform live voice tests.")
    print("\n--- Voice Assistant Direct Test Finished ---")