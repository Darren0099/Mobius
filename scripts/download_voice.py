"""Download the multilingual faster-whisper base model for local Indonesian speech.
Download only on explicit user setup, never automatically on microphone click.
"""
from pathlib import Path
import sys

from huggingface_hub import snapshot_download

root = Path.home() / '.mobius' / 'models'
root.mkdir(parents=True, exist_ok=True)
print('Mengunduh model suara multilingual satu kali ke', root)
snapshot_download(repo_id='Systran/faster-whisper-base', cache_dir=str(root),
                  allow_patterns=['config.json', 'model.bin', 'tokenizer.json', 'vocabulary.*', 'preprocessor_config.json'])
print('Selesai. Download model hanya dibutuhkan sekali.')
