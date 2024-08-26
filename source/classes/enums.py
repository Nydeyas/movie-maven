from __future__ import annotations
from enum import Enum


class UserState(Enum):
    idle = 1
    search_movie = 2
    movie_details_search = 3
    movie_details_watchlist = 4
    watchlist_panel = 5
    rate_movie_search = 6
    rate_movie_watchlist = 7

    def __str__(self) -> str:
        return self.name