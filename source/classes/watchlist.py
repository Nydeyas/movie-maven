from __future__ import annotations

from datetime import date
from typing import List, TYPE_CHECKING, Optional
import logging

from source.classes.movie import Movie

if TYPE_CHECKING:
    from source.classes.user import User


class Watchlist:
    def __init__(self, user: User) -> None:
        self.user: User = user
        self.entries: List[MovieEntry] = []

    def __repr__(self) -> str:
        cls_name = type(self).__name__
        return f"{cls_name}(entries={len(self.entries)} movies)"

    def add_movie(self, movie: Movie, rating: Optional[float] = None):
        if self.has_movie(movie):
            logging.warning(f"Movie '{movie.title}' already exists in the watchlist entries. {repr(self.user)}.")
            return

        entry = MovieEntry(movie, rating)
        self.entries.append(entry)

    def remove_movie(self, movie: Movie):
        self.entries = [entry for entry in self.entries if entry.movie != movie]

    def has_movie(self, movie: Movie) -> bool:
        """Check if the movie is in the watchlist."""
        return any(entry.movie == movie for entry in self.entries)

    def update_rating(self, movie: Movie, new_rating: float):
        for entry in self.entries:
            if entry.movie == movie:
                entry.rating = new_rating
                break

    def get_entries_sorted_by_title(self, max_items: Optional[int] = None, reverse: bool = False) -> List[MovieEntry]:
        sorted_entries = sorted(self.entries, key=lambda e: e.movie.title, reverse=reverse)
        return sorted_entries[:max_items] if max_items is not None else sorted_entries

    def get_entries_sorted_by_date(self, max_items: Optional[int] = None, reverse: bool = False) -> List[MovieEntry]:
        sorted_entries = sorted(self.entries, key=lambda e: e.date_added, reverse=reverse)
        return sorted_entries[:max_items] if max_items is not None else sorted_entries

    def get_entries_sorted_by_rating(self, max_items: Optional[int] = None, reverse: bool = False) -> List[MovieEntry]:
        sorted_entries = sorted(self.entries, key=lambda e: e.rating or 0, reverse=reverse)
        return sorted_entries[:max_items] if max_items is not None else sorted_entries

    def get_movies(self, max_items: Optional[int] = None) -> List[Movie]:
        movies = [entry.movie for entry in self.entries]
        return movies[:max_items] if max_items is not None else movies

    def get_movies_sorted_by_title(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        sorted_entries = self.get_entries_sorted_by_title(max_items, reverse)
        return [entry.movie for entry in sorted_entries]

    def get_movies_sorted_by_date(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        sorted_entries = self.get_entries_sorted_by_date(max_items, reverse)
        return [entry.movie for entry in sorted_entries]

    def get_movies_sorted_by_rating(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        sorted_entries = self.get_entries_sorted_by_rating(max_items, reverse)
        return [entry.movie for entry in sorted_entries]


class MovieEntry:
    def __init__(self, movie: Movie, rating: Optional[float] = None, date_added: Optional[date] = None):
        self.movie: Movie = movie
        self.rating: Optional[float] = rating
        self.date_added: date = date_added or date.today()

    def __repr__(self):
        cls_name = type(self).__name__
        return f"{cls_name}(movie={self.movie.title}, rating={self.rating}, date_added={self.date_added})"
