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


class MovieTagColor(Enum):
    ACTION = 0xFF0000         # Red
    ANIMATION = 0xFFD700      # Bright Yellow
    BIOGRAPHY = 0xD1D1D1      # Light Gray
    DOCUMENTARY = 0x808080    # Neutral Gray
    DRAMA = 0x800080          # Deep Purple
    FAMILY = 0x43C4E9         # Sky Blue
    FANTASY = 0x9E38B8        # Vivid Orchid
    HISTORY = 0x704214        # Sepia (Deep Brown)
    HORROR = 0x000000         # Black
    COMEDY = 0xF7DC6F         # Light Goldenrod Yellow
    CRIME = 0x2F4F4F          # Dark Slate Gray
    MUSICAL = 0xFF69B4        # Vibrant Pink
    ADVENTURE = 0x1F811F      # Forest Green
    ROMANCE = 0xFF007F        # Rose Pink
    SCI_FI = 0x1ABC9C         # Strong Cyan
    SPORT = 0x32CD32          # Lime Green
    MYSTERY = 0x191970        # Midnight Blue
    THRILLER = 0x8B0000       # Dark Red
    WESTERN = 0xD35400        # Burnt Orange
    WAR = 0x556B2F            # Olive Green

    def __str__(self):
        return f"#{self.value:06X}"
