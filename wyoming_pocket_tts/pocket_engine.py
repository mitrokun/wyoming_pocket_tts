import logging
import asyncio
import threading
import numpy as np
from pocket_tts import TTSModel

_LOGGER = logging.getLogger(__name__)

# Full catalog of voices available in Pocket TTS 2.0
PRESET_VOICES = [
    "alba", "anna", "azelma", "bill_boerst", "caro_davy", "charles", 
    "cosette", "eponine", "eve", "fantine", "george", "jane", 
    "jean", "javert", "marius", "mary", "michael", "paul", 
    "peter_yearsley", "stuart_bell", "vera"
]

class PocketEngine:
    def __init__(self, language: str = "english", quantize: bool = False):
        self.model = None
        self.sample_rate = 24000
        self.voice_states = {}
        self.available_voices = PRESET_VOICES
        self.language = language
        self.quantize = quantize

    def load(self):
        _LOGGER.info(f"Loading Pocket TTS 2.0 (lang={self.language}, quantize={self.quantize})...")
        self.model = TTSModel.load_model(
            language=self.language,
            quantize=self.quantize
        )
        self.sample_rate = self.model.sample_rate
        _LOGGER.info("Model loaded successfully.")

    def _get_voice_state(self, voice_name: str):
        """Retrieves voice state from cache or loads a preset by name."""
        if voice_name in self.voice_states:
            return self.voice_states[voice_name]

        _LOGGER.debug(f"Extracting state for voice: {voice_name}")
        try:
            state = self.model.get_state_for_audio_prompt(voice_name)
            self.voice_states[voice_name] = state
            return state
        except Exception as e:
            _LOGGER.error(f"Failed to load voice '{voice_name}': {e}")
            return None

    async def synthesize_stream(self, text: str, voice_name: str):
        if self.model is None:
            raise RuntimeError("Engine not loaded!")

        voice_state = self._get_voice_state(voice_name)
        if voice_state is None:
            _LOGGER.warning(f"Voice '{voice_name}' not found, falling back to 'alba'")
            voice_state = self._get_voice_state("alba")
            if voice_state is None:
                raise RuntimeError("Default voice 'alba' could not be loaded.")

        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()

        def _generate_thread():
            """Runs the synchronous generator in a background thread."""
            try:
                # generate_audio_stream provides chunks as soon as they are decoded
                for chunk in self.model.generate_audio_stream(voice_state, text):
                    # Convert float32 tensor to int16 PCM bytes
                    audio_bytes = (chunk.numpy() * 32767).astype(np.int16).tobytes()
                    loop.call_soon_threadsafe(queue.put_nowait, audio_bytes)
            except Exception as e:
                _LOGGER.error(f"Stream generation error: {e}")
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        threading.Thread(target=_generate_thread, daemon=True).start()

        # Yield chunks to Wyoming as they arrive in the queue
        while True:
            audio_chunk = await queue.get()
            if audio_chunk is None:
                break
            yield audio_chunk