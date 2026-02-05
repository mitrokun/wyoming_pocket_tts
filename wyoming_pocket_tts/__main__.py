import argparse
import asyncio
import logging
import os
from functools import partial

from wyoming.info import Attribution, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncServer

from .pocket_engine import PocketEngine
from .handler import PocketTTSEventHandler

_LOGGER = logging.getLogger(__name__)
__version__ = "1.0.0"

async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="tcp://0.0.0.0:10202", help="Server URI")
    parser.add_argument("--voice", default="alba", help="Default preset voice")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, 
                        format="%(asctime)s %(levelname)s:%(name)s:%(message)s")


    engine = PocketEngine() 
    await asyncio.to_thread(engine.load)

    wyoming_voices = []
    kyutai_attr = Attribution(name="Kyutai", url="https://kyutai.org/")

    for voice_id in engine.available_voices:
        wyoming_voices.append(
            TtsVoice(
                name=voice_id,
                description=f"Pocket TTS preset voice: {voice_id}",
                attribution=kyutai_attr,
                installed=True,
                version=__version__,
                languages=["en"],
            )
        )

    wyoming_info = Info(
        tts=[
            TtsProgram(
                name="pocket-tts",
                description="Pocket TTS - Fast CPU TTS Server",
                attribution=kyutai_attr,
                installed=True,
                version=__version__,
                supports_synthesize_streaming=True,
                voices=wyoming_voices,
            )
        ],
    )

    server = AsyncServer.from_uri(args.uri)
    _LOGGER.info(f"Pocket TTS server ready at {args.uri}")

    await server.run(
        partial(
            PocketTTSEventHandler,
            wyoming_info,
            args,
            engine,
        )
    )

def run():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run()