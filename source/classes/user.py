from __future__ import annotations
from typing import List

import discord

from source.classes.enums import UserState
from source.classes.movie import Movie
from source.classes.watchlist import Watchlist


class User:
    def __init__(self, member: discord.Member) -> None:
        self.id: int = member.id
        self.name: str = member.name
        self.display_name: str = member.display_name
        self.state: UserState = UserState.idle
        self.movie_selection_list: List[Movie] = []
        self.message_id: int = 0
        self.watchlist: Watchlist = Watchlist(self)

    def __repr__(self) -> str:
        cls_name = type(self).__name__
        return f"{cls_name}(name={self.name!r}, state={self.state!r})"

    def __str__(self) -> str:
        return self.name
