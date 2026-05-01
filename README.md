# Wyoming Pocket TTS

Streaming server for Home Assistant using [Kyutai Pocket TTS](https://github.com/kyutai-labs/pocket-tts).

## Installation

```bash
# Clone the repository
git clone https://github.com/mitrokun/wyoming_pocket_tts
cd wyoming_pocket_tts

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (CPU version of Torch)
pip install --upgrade pip
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install wyoming pocket-tts numpy soundfile sentence_stream
```

## Usage

**Run the server**:
   ```bash
   python3 -m wyoming_pocket_tts --uri tcp://0.0.0.0:10202
   ```
The English model is downloaded by default. You can select a different (fr, de, it, es, pt) language using the `--language` option.
   ```bash
   python3 -m wyoming_pocket_tts --uri tcp://0.0.0.0:10202 --language it
   ```
   
