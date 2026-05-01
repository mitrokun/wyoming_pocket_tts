import argparse
import asyncio
import logging
from functools import partial

from wyoming.info import Attribution, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncServer

from .pocket_engine import PocketEngine
from .handler import PocketTTSEventHandler

_LOGGER = logging.getLogger(__name__)
__version__ = "2.0.0"

# Map short codes to internal model names
LANGUAGE_MAP = {
    "en": "english",
    "fr": "french_24l",
    "de": "german_24l",
    "es": "spanish_24l",
    "it": "italian",
    "pt": "portuguese"
}

async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="tcp://0.0.0.0:10202", help="Server URI")
    parser.add_argument("--voice", default="alba", help="Default voice for synthesis")
    parser.add_argument(
        "--language", 
        default="en", 
        choices=list(LANGUAGE_MAP.keys()),
        help="Language code (en, fr, de, es, it, pt)"
    )
    parser.add_argument(
        "--quantize", 
        action="store_true", 
        help="Enable int8 quantization (faster on CPU, requires torchao)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO, 
        format="%(asctime)s %(levelname)s:%(name)s:%(message)s"
    )

    # Initialize the engine with the mapped model name
    model_name = LANGUAGE_MAP[args.language]
    engine = PocketEngine(language=model_name, quantize=args.quantize) 
    await asyncio.to_thread(engine.load)

    # Prepare Wyoming Info for Home Assistant
    kyutai_attr = Attribution(name="Kyutai", url="https://kyutai.org/")
    wyoming_voices = []

    for voice_id in engine.available_voices:
        wyoming_voices.append(
            TtsVoice(
                name=voice_id,
                description=f"{voice_id.replace('_', ' ').title()}",
                attribution=kyutai_attr,
                installed=True,
                version=__version__,
                languages=[args.language],
            )
        )

    wyoming_info = Info(
        tts=[
            TtsProgram(
                name="pocket-tts",
                description=f"Pocket TTS 2.0 ({args.language.upper()})",
                attribution=kyutai_attr,
                installed=True,
                version=__version__,
                supports_synthesize_streaming=True,
                voices=wyoming_voices,
            )
        ],
    )

    server = AsyncServer.from_uri(args.uri)
    _LOGGER.info(f"Pocket TTS server ready at {args.uri} (Language: {args.language})")

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