import argparse
import logging
import time

from sentence_stream import SentenceBoundaryDetector
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped,
)

from .pocket_engine import PocketEngine

_LOGGER = logging.getLogger(__name__)

class PocketTTSEventHandler(AsyncEventHandler):
    def __init__(
        self,
        wyoming_info: Info,
        cli_args: argparse.Namespace,
        engine: PocketEngine,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.wyoming_info_event = wyoming_info.event()
        self.cli_args = cli_args
        self.engine = engine

        self.sbd = SentenceBoundaryDetector()
        self._current_voice = cli_args.voice
        self._is_streaming = False
        self._audio_started = False

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            return True

        if Synthesize.is_type(event.type):
            if self._is_streaming:
                return True
            synthesize = Synthesize.from_event(event)
            voice = synthesize.voice.name if (synthesize.voice and synthesize.voice.name) else self.cli_args.voice
            
            self.sbd = SentenceBoundaryDetector()
            await self._send_audio_start()

            for sentence in self.sbd.add_chunk(synthesize.text):
                await self._synthesize_segment(sentence, voice)

            rem = self.sbd.finish()
            if rem:
                await self._synthesize_segment(rem, voice)

            await self._send_audio_stop()
            return True

        if SynthesizeStart.is_type(event.type):
            start = SynthesizeStart.from_event(event)
            self._is_streaming = True
            self._current_voice = start.voice.name if (start.voice and start.voice.name) else self.cli_args.voice
            self._audio_started = False
            self.sbd = SentenceBoundaryDetector()
            return True

        if SynthesizeChunk.is_type(event.type):
            if not self._is_streaming:
                return True
            chunk = SynthesizeChunk.from_event(event)
            for sentence in self.sbd.add_chunk(chunk.text):
                await self._synthesize_segment(sentence, self._current_voice)
            return True

        if SynthesizeStop.is_type(event.type):
            if not self._is_streaming:
                return True
            rem = self.sbd.finish()
            if rem:
                await self._synthesize_segment(rem, self._current_voice)
            await self._send_audio_stop()
            await self.write_event(SynthesizeStopped().event())
            self._is_streaming = False
            return True

        return True

    async def _send_audio_start(self):
        if not self._audio_started:
            await self.write_event(
                AudioStart(rate=self.engine.sample_rate, width=2, channels=1).event()
            )
            self._audio_started = True

    async def _send_audio_stop(self):
        if self._audio_started:
            await self.write_event(AudioStop().event())
            self._audio_started = False

    async def _synthesize_segment(self, text: str, voice_name: str):
        clean_text = text.strip()
        if not clean_text:
            return

        if not self._audio_started:
            await self._send_audio_start()

        try:
            async for pcm_bytes in self.engine.synthesize_stream(clean_text, voice_name):
                await self.write_event(
                    AudioChunk(
                        audio=pcm_bytes,
                        rate=self.engine.sample_rate,
                        width=2,
                        channels=1,
                    ).event()
                )
        except Exception as e:
            _LOGGER.error(f"Error in synthesis: {e}")