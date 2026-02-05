import logging
import asyncio
import numpy as np
from pocket_tts import TTSModel

_LOGGER = logging.getLogger(__name__)

PRESET_VOICES = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"]

class PocketEngine:
    def __init__(self):
        self.model = None
        self.sample_rate = 24000
        self.voice_states = {}
        self.available_voices = []

    def load(self):
        _LOGGER.info("Loading Pocket TTS model...")
        self.model = TTSModel.load_model()
        self.sample_rate = self.model.sample_rate
        self.available_voices = list(PRESET_VOICES)
        
        _LOGGER.info(f"Engine ready. Available voices: {', '.join(self.available_voices)}")

    def _get_voice_state(self, voice_name: str):
        """Получает состояние голоса из кэша или загружает пресет."""
        # 1. Проверяем кэш
        if voice_name in self.voice_states:
            return self.voice_states[voice_name]

        if voice_name in PRESET_VOICES:
            _LOGGER.debug(f"Loading preset voice: {voice_name}...")
            state = self.model.get_state_for_audio_prompt(voice_name)

            self.voice_states[voice_name] = state
            return state
        
        return None

    async def synthesize_stream(self, text: str, voice_name: str):
        if self.model is None:
            raise RuntimeError("Engine is not loaded!")

        voice_state = self._get_voice_state(voice_name)
        if voice_state is None:
            _LOGGER.warning(f"Voice '{voice_name}' not found, falling back to 'alba'")
            voice_state = self._get_voice_state("alba")
            if voice_state is None:
                raise RuntimeError("Default voice 'alba' could not be loaded.")

        audio_tensor = await asyncio.to_thread(self.model.generate_audio, voice_state, text)
        
        audio_bytes = (audio_tensor.numpy() * 32767).astype(np.int16).tobytes()
        
        chunk_size = 4096
        for i in range(0, len(audio_bytes), chunk_size):
            yield audio_bytes[i : i + chunk_size]