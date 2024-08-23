from __future__ import annotations
from enum import Enum


class UserState(Enum):
    idle = 1
    search_panel = 2
    search_result = 3
    movie_details_search = 4
    movie_details_watchlist = 5
    watchlist_panel = 6
    rate_movie_search = 7
    rate_movie_watchlist = 8

    def __str__(self) -> str:
        return self.name