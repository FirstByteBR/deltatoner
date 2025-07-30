# default_config.py
def get_default_config():
    return {
        "app_name": "DeltaToner",
        "default_mic_name": "",      # NEW: To store the user's preferred microphone
        "virtual_cable_name": "",    # This is the default output device
        "theme": "dark",
        "accent_color": "blue",
        "sound_effects_path": "tones",
        "temp_tts_filename": "temp_tts_audio.wav",
        "tts_pause_ms": 100,
        "effects_volume_db": -12.0,
        "sample_rate": 48000
    }