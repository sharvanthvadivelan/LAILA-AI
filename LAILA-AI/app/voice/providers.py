import asyncio, json, os, subprocess, tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from app.core.config import DATA, ROOT


class WakeWordProvider(ABC):
    @abstractmethod
    def listen(self): ...
class LocalSTT:
    def __init__(self):
        self.path = None
        self.model = None
        self.lock = asyncio.Lock()

    async def transcribe(self, path, model_path):
        if not model_path or not Path(model_path).is_dir():
            raise ValueError(
                "Download a faster-whisper model first and set its local folder in Settings."
            )
        async with self.lock:

            def work():
                try:
                    from faster_whisper import WhisperModel
                except ImportError as e:
                    raise ValueError(
                        "Install requirements-voice.txt to enable local transcription."
                    ) from e
                if self.path != model_path:
                    self.model = WhisperModel(
                        model_path,
                        device="cpu",
                        compute_type="int8",
                        local_files_only=True,
                    )
                    self.path = model_path
                segments, info = self.model.transcribe(
                    str(path), beam_size=1, vad_filter=True
                )
                return {
                    "text": " ".join(s.text.strip() for s in segments),
                    "language": info.language,
                }

            return await asyncio.to_thread(work)


class WindowsSpeech:
    """Offline Windows System.Speech. Fixed script + JSON stdin; no generated shell code."""

    def run(self, payload):
        if os.name != "nt":
            raise ValueError(
                "Offline speech output in v0.1 requires Windows System.Speech."
            )
        ps = (
            Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        result = subprocess.run(
            [
                str(ps),
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(ROOT / "scripts/speech.ps1"),
            ],
            input=json.dumps(payload),
            encoding="utf-8",
            capture_output=True,
            timeout=90,
        )
        if result.returncode:
            raise ValueError(
                "Windows speech failed. Check the installed voices in Windows speech settings."
            )
        return result.stdout.strip().lstrip("\ufeff")

    async def voices(self):
        if os.name != "nt":
            return []
        value = await asyncio.to_thread(self.run, {"action": "voices"})
        data = json.loads(value)
        return data if isinstance(data, list) else [data] if data else []

    async def synthesize(self, text, settings):
        folder = DATA / "audio"
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".wav", dir=folder, delete=False) as f:
            path = Path(f.name)
        try:
            await asyncio.to_thread(
                self.run,
                {
                    "action": "speak",
                    "text": text[:6000],
                    "voice": settings.voice,
                    "rate": settings.speech_rate,
                    "volume": settings.speech_volume,
                    "path": str(path),
                },
            )
            return path.read_bytes()
        finally:
            path.unlink(missing_ok=True)
