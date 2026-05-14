
from __future__ import annotations
from abc import ABC, abstractmethod

class BaseLLMAdapter(ABC):
    name = "base"

    @abstractmethod
    def health(self) -> tuple[bool, str]:
        raise NotImplementedError

    @abstractmethod
    def chat(self, text: str) -> str:
        raise NotImplementedError
