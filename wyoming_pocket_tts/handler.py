import argparse
import logging

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

# Minimum characters required to start synthesis for a segment
MIN_SENTENCE_CHARS = 22

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
        
        # Buffer for merging short sentences
        self._text_buffer = ""

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
            self._text_buffer = ""
            await self._send_audio_start()

            # Process text through SBD and merge logic
            for sentence in self.sbd.add_chunk(synthesize.text):
                await self._process_sentence(sentence, voice)

            # Flush remaining SBD text
            rem = self.sbd.finish()
            if rem:
                await self._process_sentence(rem, voice)
            
            # Final flush of the buffer
            await self._flush_buffer(voice)

            await self._send_audio_stop()
            return True

        if SynthesizeStart.is_type(event.type):
            start = SynthesizeStart.from_event(event)
            self._is_streaming = True
            self._current_voice = start.voice.name if (start.voice and start.voice.name) else self.cli_args.voice
            self._audio_started = False
            self.sbd = SentenceBoundaryDetector()
            self._text_buffer = ""
            return True

        if SynthesizeChunk.is_type(event.type):
            if not self._is_streaming:
                return True
            chunk = SynthesizeChunk.from_event(event)
            for sentence in self.sbd.add_chunk(chunk.text):
                await self._process_sentence(sentence, self._current_voice)
            return True

        if SynthesizeStop.is_type(event.type):
            if not self._is_streaming:
                return True
            
            # Finish SBD
            rem = self.sbd.finish()
            if rem:
                await self._process_sentence(rem, self._current_voice)
            
            # Force send whatever is left in the buffer
            await self._flush_buffer(self._current_voice)
            
            await self._send_audio_stop()
            await self.write_event(SynthesizeStopped().event())
            self._is_streaming = False
            return True

        return True

    async def _process_sentence(self, sentence: str, voice: str):
        """Adds a sentence to buffer and checks if it's long enough to synthesize."""
        clean_sentence = sentence.strip()
        if not clean_sentence:
            return

        if self._text_buffer:
            self._text_buffer += " " + clean_sentence
        else:
            self._text_buffer = clean_sentence

        # If buffer is long enough, synthesize it
        if len(self._text_buffer) >= MIN_SENTENCE_CHARS:
            await self._flush_buffer(voice)

    async def _flush_buffer(self, voice: str):
        """Synthesizes current buffer regardless of its length."""
        text_to_send = self._text_buffer.strip()
        if not text_to_send:
            return

        self._text_buffer = ""
        await self._synthesize_segment(text_to_send, voice)

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
        if not self._audio_started:
            await self._send_audio_start()

        try:
            async for pcm_bytes in self.engine.synthesize_stream(text, voice_name):
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