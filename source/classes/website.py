from __future__ import annotations
from typing import TYPE_CHECKING, List

from classes.movie import Movie

if TYPE_CHECKING:
    from classes.types_base import Movie as MoviePayload


class Website:
    def __init__(self, name: str, data: List[MoviePayload]) -> None:
        self.name: str = name
        self.movies: List[Movie] = [Movie(website=self, data=d) for d in data]

    def __str__(self) -> str:
        return self.name
