import keyboard
from audio_manager import AudioManager
from settings_manager import SettingsManager
from typing import Literal
from logger_config import logger
import time

class PhraseDetector:
    def __init__(self):
        self.phrase = ""
        self._listening = False
        self._hook = None  # to store the hook for later removal
        self.audio = AudioManager(SettingsManager())

    def _on_key_event(self, event):
        if not self._listening:
            return
            
        if event.event_type == 'down':
            name = event.name

            if name == 'enter':
                # Stop listener on Enter key, breaking the loop in listen_for_phrase
                self._listening = False
            elif name == 'backspace':
                self.phrase = self.phrase[:-1]
            elif len(name) == 1:
                self.phrase += name
            elif name == 'space':
                self.phrase += ' '

    def listen_for_phrase(self):
        """ 
        Returns typed phrase when Enter is pressed.
        This is a polling-based implementation to allow interruption from other threads.
        """
        self.phrase = ""
        self._listening = True
        self._hook = keyboard.hook(self._on_key_event)
        logger.info("[HOTKEYER] Phrase detection started.")

        while self._listening:
            time.sleep(0.05)  # Poll to prevent high CPU, allows thread to be interrupted

        keyboard.unhook(self._hook)
        self._hook = None
        
        # Only log if the phrase was completed by the user, not by an external stop
        if not self._listening and self.phrase:
             logger.info(f"[HOTKEYER] Detected phrase: {self.phrase}")
        else:
             logger.info("[HOTKEYER] Phrase detection stopped.")
        return self.phrase
    
    def stop(self):
        """Forcibly stops the listening loop from another thread."""
        self._listening = False

    def standalone(self,mode:Literal["effects-only","merged"]='effects-only'):
        """ Mode can be 'effects-only' or 'merged'. Defult: 'effects-only'. """
        self.audio.start_audio_processing(mic_device_id="(Logitech G733 Gamin, MME",output_device_id="CABLE Input (VB-Audio Virtual C")
        self.audio.mode = mode
        while True:
            self.audio.generate_tts_audio(text=detector.listen_for_phrase())
            print(f"Generated TTS for: {detector.phrase}")
            self.audio.play_generated_tts()

detector = PhraseDetector()

if __name__ == '__main__':
    detector.standalone()