"""Explicit, one-time ONLINE download. Never invoked during normal app startup."""

import argparse
from pathlib import Path

parser = argparse.ArgumentParser(
    description="Download a local faster-whisper model while online."
)
parser.add_argument("--size", choices=["tiny", "base", "small"], default="base")
args = parser.parse_args()
from huggingface_hub import snapshot_download

folder = Path(__file__).resolve().parents[1] / "data/models" / ("whisper-" + args.size)
snapshot_download("Systran/faster-whisper-" + args.size, local_dir=folder)
print(
    "Download complete. Paste this path into Settings > Local faster-whisper model folder:"
)
print(folder)
