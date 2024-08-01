from __future__ import annotations
from enum import Enum


class UserState(Enum):
    idle = 1

    def __str__(self) -> str:
        return self.name