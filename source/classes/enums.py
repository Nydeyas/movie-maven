from __future__ import annotations
from enum import Enum


class UserState(Enum):
    idle = 1
    search_movie = 2
    input_search_filter = 3
    movie_details_search = 4
    movie_details_watchlist = 5
    watchlist_panel = 6
    rate_movie_search = 7
    rate_movie_watchlist = 8

    def __str__(self) -> str:
        return self.name


class MovieTag(Enum):
    ACTION = "Akcja"
    ANIMATION = "Animacja"
    BIOGRAPHY = "Biograficzny"
    DOCUMENTARY = "Dokumentalny"
    DRAMA = "Dramat"
    FAMILY = "Familijny"
    FANTASY = "Fantasy"
    HISTORY = "Historyczny"
    HORROR = "Horror"
    COMEDY = "Komedia"
    CRIME = "Kryminał"
    MUSICAL = "Muzyczny"
    ADVENTURE = "Przygodowy"
    ROMANCE = "Romans"
    SCI_FI = "Sci-Fi"
    SPORT = "Sportowy"
    MYSTERY = "Tajemnica"
    THRILLER = "Thriller"
    WESTERN = "Western"
    WAR = "Wojenny"

    def __str__(self):
        return self.value

