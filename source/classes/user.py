from __future__ import annotations

import asyncio
from typing import List, Union, Optional

import discord

from source.classes.enums import UserState
from source.classes.movie import Movie
from source.classes.watchlist import Watchlist


class User:
    def __init__(self, member_id: int, name: str, display_name: str) -> None:
        self.id: int = member_id
        self.name: str = name
        self.display_name: str = display_name
        self.state: UserState = UserState.idle
        self.movie_selection_list: List[Movie] = []
        self.message_id: int = 0
        self.interaction_task: Optional[Union[
            asyncio.Task[discord.RawReactionActionEvent],
            asyncio.Task[discord.Message],
        ]] = None
        self.watchlist: Watchlist = Watchlist(self)

    def __repr__(self) -> str:
        cls_name = type(self).__name__
        return f"{cls_name}(name={self.name!r}, state={self.state!r})"

    def __str__(self) -> str:
        return self.name

    def copy_without_task(self) -> User:
        """Create a copy of the User object with interaction_task set to None."""
        new_user = User(self.id, self.name, self.display_name)
        new_user.state = self.state
        new_user.movie_selection_list = self.movie_selection_list.copy()
        new_user.message_id = self.message_id
        new_user.watchlist = self.watchlist
        new_user.interaction_task = None
        return new_user
