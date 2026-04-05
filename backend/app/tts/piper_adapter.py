
from __future__ import annotations
import shutil
from app.tts.base import BaseTTSAdapter

class PiperAdapter(BaseTTSAdapter):
    name = "piper"

    def __init__(self, executable: str = "piper", model_path: str = ""):
        self.executable = executable
        self.model_path = model_path

    def available(self) -> bool:
        return bool(shutil.which(self.executable)) and bool(self.model_path)

    def speak(self, text: str) -> bool:
        return False
