import sounddevice as sd
import numpy as np
from pydub import AudioSegment
import os
import threading
import random
from logger_config import logger

class AudioManager:
    def __init__(self, settings_manager):
        self.settings = settings_manager
        self.stream = None
        self.active_effects = []
        self.is_running = False
        self.lock = threading.Lock()
        self.reload_config()
        self.mute_effects = False
        self.preview_stream = None
        self.preview_enabled = False
        self.preview_device_id = None

    def reload_config(self):
        with self.lock:
            self.effects_volume_db = self.settings.get("effects_volume_db")
            if self.effects_volume_db is None:
                self.effects_volume_db = -18
            self.sample_rate = self.settings.get("sample_rate") or 44100
            self.sound_effects_path = self.settings.get("sound_effects_path") or "sounds/"
            self.temp_tts_filename = self.settings.get("temp_tts_filename") or "temp_tts.wav"
            self.tts_pause_ms = self.settings.get("tts_pause_ms") or 100
            self.speak_tone, self.variated_speak_tones = self._load_speak_tone()
            self.mode = "merged"
            logger.info(f"Config loaded: sample_rate={self.sample_rate}, effects_volume_db={self.effects_volume_db}")

    def get_audio_devices(self):
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        input_devices, output_devices = [], []
        for device in devices:
            try:
                hostapi_name = hostapis[device['hostapi']]['name']
                device_name = f"{device['name']}, {hostapi_name}"
                if device['max_input_channels'] > 0:
                    input_devices.append(device_name)
                if device['max_output_channels'] > 0:
                    output_devices.append(device_name)
            except Exception as e:
                logger.error(f"Could not query device '{device.get('name', 'Unknown')}': {e}")
        return input_devices, output_devices

    def start_audio_processing(self, mic_device_id, output_device_id, preview_output_device_id=None, preview_enabled=False):
        if self.is_running:
            return
        self.is_running = True
        self.preview_enabled = preview_enabled
        self.preview_device_id = preview_output_device_id

        try:
            # Main stream to virtual cable output
            self.stream = sd.Stream(
                samplerate=self.sample_rate,
                blocksize=0,
                device=(mic_device_id, output_device_id),
                channels=(1, 2),
                dtype='float32',
                latency='low',
                callback=self._processing_callback
            )
            self.stream.start()
            logger.info("Audio stream (main output) started successfully.")

            # If preview is enabled, open a second output stream to speakers
            if self.preview_enabled and self.preview_device_id is not None:
                self.preview_stream = sd.OutputStream(
                    samplerate=self.sample_rate,
                    device=self.preview_device_id,
                    channels=2,
                    dtype='float32',
                    latency='low',
                    callback=self._preview_callback
                )
                self.preview_stream.start()
                logger.info("Preview audio stream to speakers started successfully.")
            else:
                self.preview_stream = None

        except Exception as e:
            logger.error(f"CRITICAL ERROR starting audio streams: {e}", exc_info=True)
            self.is_running = False
            return False
        return True

    def stop_audio_processing(self):
        if not self.is_running:
            return

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if hasattr(self, 'preview_stream') and self.preview_stream:
            self.preview_stream.stop()
            self.preview_stream.close()
            self.preview_stream = None
        self.is_running = False
        self.stop_all_sounds()
        logger.info("All audio streams stopped.")


    def _db_to_gain(self, db):
        return 10 ** (db / 20.0)

    def _processing_callback(self, indata, outdata, frames, time, status):
        if status:
            logger.warning(status)

        with self.lock:
            if self.mode in "merged":
                mic_data = np.tile(indata, (1, 2))
                mic_gain = 0.7
                mic_data *= mic_gain
                self.mute_effects = False
            elif self.mode == "pass-through":
                mic_data = np.tile(indata, (1, 2))
                mic_gain = 0.7
                mic_data *= mic_gain
                self.mute_effects = True
            else:
                mic_data = np.zeros((frames, 2), dtype='float32')
                self.mute_effects = False

            effects_data = np.zeros((frames, 2), dtype='float32')
            remaining_effects = []
            effects_gain = self._db_to_gain(self.effects_volume_db)

            for effect in self.active_effects:
                effect_data = effect['data']
                pos = effect['pos']
                chunk = effect_data[pos:pos + frames]
                chunk_len = len(chunk)
                if chunk_len < frames:
                    pad = np.zeros((frames - chunk_len, 2), dtype='float32')
                    chunk = np.vstack([chunk, pad])
                effects_data[:frames] += chunk * effects_gain
                effect['pos'] += chunk_len
                if effect['pos'] < len(effect_data):
                    remaining_effects.append(effect)

            self.active_effects = remaining_effects

            mixed_data = mic_data + effects_data
            max_amp = np.max(np.abs(mixed_data))
            if max_amp > 1.0:
                mixed_data = mixed_data / max_amp
            np.clip(mixed_data, -1.0, 1.0, out=outdata)
        if self.preview_enabled and hasattr(self, 'preview_stream') and self.preview_stream:
            with self.lock:
                # Save the outdata frame for preview
                self._last_output_block = outdata.copy()
    
    def _preview_callback(self, outdata, frames, time, status):
    # Playback last output block to preview device
        if status:
            logger.warning(f"Preview stream status: {status}")
        with self.lock:
            if hasattr(self, '_last_output_block'):
                data = self._last_output_block
                # Make sure data shape matches expected frames/channels
                if data.shape[0] == frames and data.shape[1] == 2:
                    outdata[:] = data
                else:
                    outdata.fill(0)
            else:
                outdata.fill(0)

    def update_preview_enabled(self, enabled):
        # To handle enabling/disabling preview after start
        self.preview_enabled = enabled
        if not enabled and self.preview_stream:
            self.preview_stream.stop()
            self.preview_stream.close()
            self.preview_stream = None
        elif enabled and not self.preview_stream and self.is_running:
            try:
                # reopen preview stream with stored preview_device_id
                self.preview_stream = sd.OutputStream(
                    samplerate=self.sample_rate,
                    device=self.preview_device_id,
                    channels=2,
                    dtype='float32',
                    latency='low',
                    callback=self._preview_callback
                )
                self.preview_stream.start()
                logger.info("Preview audio stream enabled.")
            except Exception as e:
                logger.error(f"Failed to enable preview audio stream: {e}")

    def set_preview_device_id(self, device_id):
        self.preview_device_id = device_id
        if self.preview_enabled:
            self.update_preview_enabled(False)  # disable first if running
            self.update_preview_enabled(True)   # re-enable with new device

    def set_effects_volume(self, db_level):
        with self.lock:
            self.effects_volume_db = float(db_level)
            logger.info(f"Effects volume set to {self.effects_volume_db} dB")
            self.speak_tone, self.variated_speak_tones = self._load_speak_tone()

    def stop_all_sounds(self):
        with self.lock:
            self.active_effects.clear()
        logger.info("All sound effects stopped.")

    def play_sound_effect(self, sound_file):
        if not self.mute_effects:
            try:
                path_to_sound = sound_file if os.path.exists(sound_file) else os.path.join(self.sound_effects_path, sound_file)
                sound = AudioSegment.from_file(path_to_sound)
                target_volume_db = self.effects_volume_db
                gain_change = target_volume_db - sound.dBFS
                sound = sound.apply_gain(gain_change)
                if sound.channels == 1:
                    sound = sound.set_channels(2)
                sound = sound.set_frame_rate(self.sample_rate)
                sample_width = sound.sample_width
                max_val = float(2 ** (8 * sample_width - 1))
                samples = np.array(sound.get_array_of_samples()).astype(np.float32) / max_val
                samples = samples.reshape((-1, 2))
                with self.lock:
                    self.active_effects.append({'data': samples, 'pos': 0})
            except Exception as e:
                logger.error(f"Error playing sound effect {sound_file}: {e}")

    def _load_speak_tone(self):
        """
        Loads the selected SpeakTone or VSpeakTone set from config.
        Returns:
            - speak_tone: dict for normal SpeakTone or None if using variated
            - variated_speak_tones: list of dicts if using VSpeakTone, else []
        """
        try:
            if not os.path.exists(self.sound_effects_path):
                os.makedirs(self.sound_effects_path)
            selected_speaktone = self.settings.get("speaktone_file")
            speak_tone_path = None
            variated_tones = []

            import re
            # Check for VSpeakTone selection (e.g. tenna--VSpeakTone1.ogg)
            vspeak_match = re.match(r"^(.*)--VSpeakTone\d+\.(ogg|wav|mp3)$", selected_speaktone or "", re.IGNORECASE)
            if vspeak_match:
                base = vspeak_match.group(1)
                # Load all matching VSpeakTone files for this base
                vtones = []
                for f in os.listdir(self.sound_effects_path):
                    if re.match(rf"^{re.escape(base)}--VSpeakTone\d+\.(ogg|wav|mp3)$", f, re.IGNORECASE):
                        vtones.append(os.path.join(self.sound_effects_path, f))
                vtones.sort()
                for vtone_path in vtones:
                    ext = os.path.splitext(vtone_path)[1].lower()
                    if ext == ".ogg":
                        sound = AudioSegment.from_ogg(vtone_path)
                    elif ext == ".wav":
                        sound = AudioSegment.from_wav(vtone_path)
                    elif ext == ".mp3":
                        sound = AudioSegment.from_mp3(vtone_path)
                    else:
                        sound = AudioSegment.from_file(vtone_path)
                    gain_change = self.effects_volume_db - sound.dBFS
                    sound = sound.apply_gain(gain_change)
                    if sound.channels == 1:
                        sound = sound.set_channels(2)
                    sound = sound.set_frame_rate(self.sample_rate)
                    sample_width = sound.sample_width
                    max_val = float(2 ** (8 * sample_width - 1))
                    samples = np.array(sound.get_array_of_samples()).astype(np.float32) / max_val
                    samples = samples.reshape((-1, 2))
                    variated_tones.append({
                        'audio_segment': sound,
                        'data': samples,
                        'pos': 0
                    })
                if not variated_tones:
                    logger.warning("No VSpeakTone files found. Using silence.")
                    silent_seg = AudioSegment.silent(duration=1000, frame_rate=self.sample_rate).set_channels(2)
                    return None, [{
                        'audio_segment': silent_seg,
                        'data': np.zeros((self.sample_rate, 2), dtype=np.float32),
                        'pos': 0
                    }]
                return None, variated_tones

            # Otherwise, use normal SpeakTone
            if selected_speaktone:
                candidate = os.path.join(self.sound_effects_path, selected_speaktone)
                if os.path.exists(candidate):
                    speak_tone_path = candidate
            if not speak_tone_path:
                # Fallback: first available -SpeakTone file (any extension, not variated)
                speak_pattern = re.compile(r"^(.*)-SpeakTone\.(ogg|wav|mp3)$", re.IGNORECASE)
                speak_tone_path = next(
                    (os.path.join(self.sound_effects_path, f)
                     for f in os.listdir(self.sound_effects_path)
                     if speak_pattern.match(f)),
                    None)
            if not speak_tone_path:
                logger.warning("No speak tone file found. Using silence.")
                silent_seg = AudioSegment.silent(duration=1000, frame_rate=self.sample_rate).set_channels(2)
                return {
                    'audio_segment': silent_seg,
                    'data': np.zeros((self.sample_rate, 2), dtype=np.float32),
                    'pos': 0
                }, []
            ext = os.path.splitext(speak_tone_path)[1].lower()
            if ext == ".ogg":
                sound = AudioSegment.from_ogg(speak_tone_path)
            elif ext == ".wav":
                sound = AudioSegment.from_wav(speak_tone_path)
            elif ext == ".mp3":
                sound = AudioSegment.from_mp3(speak_tone_path)
            else:
                sound = AudioSegment.from_file(speak_tone_path)
            gain_change = self.effects_volume_db - sound.dBFS
            sound = sound.apply_gain(gain_change)
            if sound.channels == 1:
                sound = sound.set_channels(2)
            sound = sound.set_frame_rate(self.sample_rate)
            sample_width = sound.sample_width
            max_val = float(2 ** (8 * sample_width - 1))
            samples = np.array(sound.get_array_of_samples()).astype(np.float32) / max_val
            samples = samples.reshape((-1, 2))
            return {
                'audio_segment': sound,
                'data': samples,
                'pos': 0
            }, []

        except Exception as e:
            logger.error(f"Error loading speak tone: {e}")
            silent_seg = AudioSegment.silent(duration=1000, frame_rate=self.sample_rate).set_channels(2)
            return {
                'audio_segment': silent_seg,
                'data': np.zeros((self.sample_rate, 2), dtype=np.float32),
                'pos': 0
            }, []

        except Exception as e:
            logger.error(f"Error loading speak tone: {e}")
            silent_seg = AudioSegment.silent(duration=1000, frame_rate=self.sample_rate).set_channels(2)
            return {
                'audio_segment': silent_seg,
                'data': np.zeros((self.sample_rate, 2), dtype=np.float32),
                'pos': 0
            }, []

    def generate_tts_audio(self, text):
        # If using variated speak tones, randomly select for each character, avoiding repeats
        if (self.variated_speak_tones is not None) and len(self.variated_speak_tones) > 0:
            try:
                with self.lock:
                    pause_duration = self.tts_pause_ms
                    vtones = self.variated_speak_tones
                combined = AudioSegment.empty()
                silent_pause = AudioSegment.silent(duration=pause_duration, frame_rate=self.sample_rate)
                last_idx = None
                for char in text:
                    if char == ' ':
                        combined += silent_pause
                    else:
                        # Pick a random index, reroll if same as last
                        if len(vtones) == 1:
                            idx = 0
                        else:
                            idx = random.randint(0, len(vtones) - 1)
                            while idx == last_idx and len(vtones) > 1:
                                idx = random.randint(0, len(vtones) - 1)
                        combined += vtones[idx]['audio_segment']
                        last_idx = idx
                combined = combined.set_channels(2).set_frame_rate(self.sample_rate)
                combined.export(self.temp_tts_filename, format="ogg")
                logger.info(f"TTS audio (variated) generated and saved to {self.temp_tts_filename}")
                return True
            except Exception as e:
                logger.error(f"Error generating TTS audio (variated): {e}")
                return False

        # Otherwise, use normal speak tone
        if not self.speak_tone or 'audio_segment' not in self.speak_tone:
            logger.warning("No speak tone audio segment loaded for TTS.")
            return False
        try:
            with self.lock:
                pause_duration = self.tts_pause_ms
                speak_tone_seg = self.speak_tone['audio_segment']
            combined = AudioSegment.empty()
            silent_pause = AudioSegment.silent(duration=pause_duration, frame_rate=self.sample_rate)
            for char in text:
                if char == ' ':
                    combined += silent_pause
                else:
                    combined += speak_tone_seg
            combined = combined.set_channels(2).set_frame_rate(self.sample_rate)
            combined.export(self.temp_tts_filename, format="ogg")
            logger.info(f"TTS audio generated and saved to {self.temp_tts_filename}")
            return True
        except Exception as e:
            logger.error(f"Error generating TTS audio: {e}")
            return False

    def play_generated_tts(self):
        if (not self.mute_effects) and (os.path.exists(self.temp_tts_filename)):
            self.play_sound_effect(self.temp_tts_filename)
            logger.info(f"TTS audio played from {self.temp_tts_filename}")