from __future__ import annotations
from typing import TYPE_CHECKING, List

from source.classes.movie import Movie

if TYPE_CHECKING:
    from source.classes.types_base import Movie as MoviePayload


class Website:
    def __init__(self, name: str, data: List[MoviePayload]) -> None:
        self.name: str = name
        self.movies: List[Movie] = [Movie(website=self, data=d) for d in data]

    def __str__(self) -> str:
        return self.name

    def add_movies(self, new_movies: List[MoviePayload], duplicates: bool = True):
        """Add new movies to the website.

        Args:
            new_movies (List[MoviePayload]): List of movies to be added.
            duplicates (bool): Whether to allow duplicates. Defaults to True.
        """
        for data in new_movies:
            new_movie = Movie(website=self, data=data)
            if duplicates or new_movie not in self.movies:
                self.movies.append(new_movie)
