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

# Remove the _24l suffix to switch to the smaller 6-layer model.
# However, quality and stability will be reduced.
LANGUAGE_MAP = {
    "en": "english",
    "fr": "french_24l",
    "de": "german_24l",
    "es": "spanish_24l",
    "it": "italian_24l",
    "pt": "portuguese_24l"
}

def setup_logging(debug: bool):
    """Configures logging to silence noisy third-party libraries."""
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Root logger set to WARNING to silence everything by default
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s:%(name)s:%(message)s"
    )

    # Set our specific module loggers to INFO or DEBUG
    # Note: Replace 'wyoming_pocket_tts' with your actual package folder name if different
    logging.getLogger("wyoming_pocket_tts").setLevel(log_level)
    logging.getLogger("__main__").setLevel(log_level)

    # Silence specific noisy libraries unless in full debug mode
    external_loggers = [
        "httpx", 
        "httpcore", 
        "huggingface_hub", 
        "torch", 
        "urllib3", 
        "pocket_tts"
    ]
    
    for logger_name in external_loggers:
        if debug:
            logging.getLogger(logger_name).setLevel(logging.DEBUG)
        else:
            # In normal mode, we only want to see Errors or Warnings from these
            logging.getLogger(logger_name).setLevel(logging.WARNING)

async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="tcp://0.0.0.0:10202", help="Server URI")
    parser.add_argument("--voice", default="alba", help="Default voice")
    parser.add_argument(
        "--language", 
        default="en", 
        choices=list(LANGUAGE_MAP.keys()),
        help="Language code (en, fr, de, es, it, pt)"
    )
    parser.add_argument(
        "--quantize", 
        action="store_true", 
        help="Enable int8 quantization"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Apply noise-filtering logging setup
    setup_logging(args.debug)

    model_name = LANGUAGE_MAP[args.language]
    engine = PocketEngine(language=model_name, quantize=args.quantize) 
    await asyncio.to_thread(engine.load)

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
