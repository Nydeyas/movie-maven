from __future__ import annotations

import csv
import io
from datetime import date
from typing import List, TYPE_CHECKING, Optional
import logging
import locale

from classes.movie import Movie

if TYPE_CHECKING:
    from classes.user import User


def replace_none(value, default=0):
    return default if value is None else value


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
        locale.setlocale(locale.LC_COLLATE, 'pl_PL.UTF-8')
        sorted_entries = sorted(self.entries, key=lambda e: locale.strxfrm(e.movie.title), reverse=reverse)
        return sorted_entries[:max_items] if max_items is not None else sorted_entries

    def get_entries_sorted_by_date(self, max_items: Optional[int] = None, reverse: bool = False) -> List[MovieEntry]:
        locale.setlocale(locale.LC_COLLATE, 'pl_PL.UTF-8')
        sorted_entries = sorted(
            self.entries,
            key=lambda e: (
                (e.date_added, locale.strxfrm(e.movie.title))
                if not reverse
                else (-e.date_added.toordinal(), locale.strxfrm(e.movie.title))
            ),
            reverse=False  # Sort by the primary key as adjusted
        )
        return sorted_entries[:max_items] if max_items is not None else sorted_entries

    def get_entries_sorted_by_rating(self, max_items: Optional[int] = None, reverse: bool = False) -> List[MovieEntry]:
        locale.setlocale(locale.LC_COLLATE, 'pl_PL.UTF-8')
        sorted_entries = sorted(
            self.entries,
            key=(
                lambda e: (replace_none(e.rating), locale.strxfrm(e.movie.title))
                if not reverse
                else (-replace_none(e.rating), locale.strxfrm(e.movie.title))
            ),
            reverse=False  # Always sort by the primary key as adjusted
        )

        return sorted_entries[:max_items] if max_items is not None else sorted_entries

    def get_entries(self, sort_key: str = 'title', reverse: bool = False):
        if sort_key == 'title':
            entries = self.get_entries_sorted_by_title(reverse=reverse)
        elif sort_key == 'date_added':
            entries = self.get_entries_sorted_by_date(reverse=reverse)
        elif sort_key == 'rating':
            entries = self.get_entries_sorted_by_rating(reverse=reverse)
        else:
            raise ValueError(f"Unknown sort_key: {sort_key}")
        return entries

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

    def get_csv(self, sort_key: str = 'title', reverse: bool = False) -> io.BytesIO:
        # Sort the entries based on the provided key and order
        if sort_key == 'title':
            sorted_entries = self.get_entries_sorted_by_title(reverse=reverse)
        elif sort_key == 'date_added':
            sorted_entries = self.get_entries_sorted_by_date(reverse=reverse)
        elif sort_key == 'rating':
            sorted_entries = self.get_entries_sorted_by_rating(reverse=reverse)
        else:
            sorted_entries = self.entries
            logging.warning(f"Unknown sort_key '{sort_key}' provided. Using unsorted entries.")

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')

        # Write CSV header
        writer.writerow(['Tytuł', 'Data dodania', 'Ocena'])

        # Write data rows
        for entry in sorted_entries:
            title = entry.movie.title
            date_added = entry.date_added
            rating = entry.rating if entry.rating is not None else 'Brak'
            writer.writerow([title, date_added, rating])

        # Convert the StringIO to BytesIO
        output.seek(0)
        byte_io = io.BytesIO(output.getvalue().encode('utf-8'))
        byte_io.seek(0)
        return byte_io


class MovieEntry:
    def __init__(self, movie: Movie, rating: Optional[float] = None, date_added: Optional[date] = None):
        self.movie: Movie = movie
        self.rating: Optional[float] = rating
        self.date_added: date = date_added or date.today()

    def __repr__(self):
        cls_name = type(self).__name__
        return f"{cls_name}(movie={self.movie.title}, rating={self.rating}, date_added={self.date_added})"
