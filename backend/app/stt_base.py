
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(slots=True)
class STTResult:
    text: str
    language: str = "unknown"
    duration_ms: int = 0
    contains_speech: bool = False

class BaseSTTAdapter(ABC):
    name = "base"

    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def listen_once(self) -> STTResult:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError
