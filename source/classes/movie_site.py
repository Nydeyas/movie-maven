from __future__ import annotations
from typing import TYPE_CHECKING, List

from source.classes.movie import Movie

if TYPE_CHECKING:
    from source.classes.types_base import Movie as MoviePayload


class MovieSite:
    def __init__(self, name: str, data: List[MoviePayload]) -> None:
        self.name: str = name
        self.movies: List[Movie] = [Movie(site=self, data=d) for d in data]

    def __str__(self) -> str:
        return self.name

    def add_movies(self, new_movies: List[MoviePayload], duplicates: bool = True):
        """Add new movies to the list."""
        for data in new_movies:
            new_movie = Movie(site=self, data=data)
            if duplicates or new_movie not in self.movies:
                self.movies.append(new_movie)

    def get_sorted_by_title(self, reverse: bool = False) -> List[Movie]:
        """Return a list of movies sorted alphabetically by title."""
        return sorted(self.movies, key=lambda movie: movie.title, reverse=reverse)

    def get_sorted_by_rating(self, reverse: bool = False) -> List[Movie]:
        """Return a list of movies sorted by rating."""
        return sorted(self.movies, key=lambda movie: movie.rating, reverse=reverse)

    def get_sorted_by_year(self, reverse: bool = False) -> List[Movie]:
        """Return a list of movies sorted by year."""
        return sorted(self.movies, key=lambda movie: movie.year, reverse=reverse)
