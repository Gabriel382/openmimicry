
from __future__ import annotations
from abc import ABC, abstractmethod

class BaseTTSAdapter(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def speak(self, text: str) -> bool:
        raise NotImplementedError
