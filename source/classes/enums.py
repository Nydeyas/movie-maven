from __future__ import annotations
from enum import Enum


class UserState(Enum):
    idle = 1
    search_panel = 2
    search_result = 3
    movie_details = 4
    watchlist_panel = 5
    rate_movie = 6

    def __str__(self) -> str:
        return self.name