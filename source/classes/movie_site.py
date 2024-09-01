from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Dict
from difflib import SequenceMatcher
from Levenshtein import distance
import locale

from source.classes.movie import Movie

if TYPE_CHECKING:
    from source.classes.types_base import Movie as MoviePayload


def replace_none(value, default=0):
    return default if value is None else value


def longest_common_substring_percentage(s1: str, s2: str) -> float:
    """Computes the longest common substring percentage of s1 and s2."""
    if not s1 or not s2:
        return 0.0

    seq_matcher = SequenceMatcher(None, s1, s2)
    match = seq_matcher.find_longest_match(0, len(s1), 0, len(s2))

    if match.size:
        lcs_length = match.size
        return lcs_length / min(len(s1), len(s2))
    else:
        return 0.0


def levenshtein_distance_percentage(s1: str, s2: str) -> float:
    """Computes the Levenshtein distance. Measures how closely the s1 matches the s2. Used mainly for typos."""
    if not s1 or not s2:
        return 0.0
    return 1.0 - distance(s1, s2) / max(len(s1), len(s2))


def simple_match_percentage(s1: str, s2: str) -> float:
    """Computes the simple comparison checking for exact word matches between the s1 and the s2."""
    if not s1 or not s2:
        return 0.0
    s1_split = s1.split(" ")
    match_count = sum(1 for x in s1_split if x in s2)
    return match_count / len(s1_split)


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

    def get_movies_sorted_by_title(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        """Return a list of movies sorted alphabetically by title."""
        locale.setlocale(locale.LC_COLLATE, 'pl_PL.UTF-8')
        sorted_movies = sorted(self.movies, key=lambda m: locale.strxfrm(m.title), reverse=reverse)
        return sorted_movies[:max_items] if max_items is not None else sorted_movies

    def get_movies_sorted_by_rating(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        """Return a list of movies sorted by rating."""
        locale.setlocale(locale.LC_COLLATE, 'pl_PL.UTF-8')
        sorted_movies = sorted(
            self.movies,
            key=lambda m: (replace_none(m.rating), locale.strxfrm(m.title))
            if not reverse
            else (-replace_none(m.rating), locale.strxfrm(m.title)),
            reverse=False  # Sort by the primary key as adjusted
        )
        return sorted_movies[:max_items] if max_items is not None else sorted_movies

    def get_movies_sorted_by_year(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        """Return a list of movies sorted by year."""
        locale.setlocale(locale.LC_COLLATE, 'pl_PL.UTF-8')
        sorted_movies = sorted(
            self.movies,
            key=lambda m: (replace_none(m.year, 1900), locale.strxfrm(m.title))
            if not reverse
            else (-replace_none(m.year, 1900), locale.strxfrm(m.title)),
            reverse=False  # Sort by the primary key as adjusted
        )
        return sorted_movies[:max_items] if max_items is not None else sorted_movies

    def get_movies_sorted_by_date_added(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        """Retrieves and returns a list of movies sorted by their date of addition."""
        sorted_movies = self.movies[::-1] if reverse else self.movies[:]
        return sorted_movies[:max_items] if max_items is not None else sorted_movies

    def filter_movies_by_tags(self, movies: List[Movie], selected_tags: List[str]) -> List[Movie]:
        """Filter movies by tags."""
        return [movie for movie in movies if all(tag in movie.tags for tag in selected_tags)]

    def filter_movies_by_years(self, movies: List[Movie], selected_years: List[int]) -> List[Movie]:
        """Filter movies by years."""
        return [movie for movie in movies if movie.year in selected_years]

    def search_movies(
            self,
            phrase: str,
            max_items: Optional[int] = None,
            min_match_score: float = 0.0,
            sort_key: str = 'match_score',
            reverse: bool = False,
            limit_before_sort: bool = False,
            filter_tags: Optional[List[str]] = None,
            filter_years: Optional[List[int]] = None
    ) -> List[Movie]:
        """
        Search for movies that match a given phrase and return a sorted list of results based on the match score.

        This method compares the provided phrase against each movie's title in the collection using three algorithms:
        - Simple match percentage: Checks for exact word matches between the phrase and the title.
        - Levenshtein distance percentage: Measures how closely the phrase matches the title even with minor differences
          (e.g., typos).
        - Longest common substring percentage: Identifies the longest continuous sequence of characters shared by the
          phrase and the title.

        Parameters:
        - phrase (str): The search phrase to compare against movie titles.
        - max_items (Optional[int]): The maximum number of movies to return. If None, returns all matching movies.
        - min_match_score (float): The minimum score required for a movie to be included in the results. (0.0-100.0)
        - sort_key (str): The key to sort the movies by. Can be 'match_score', 'date_added', 'year', 'title', 'rating'.
        - reverse (bool): If True, sorts the list in descending order based on the sort key.
        - limit_before_sort (bool): If True, limits the number of items before sorting. If False, limits after sorting.
        - selected_tags (Optional[List[str]]): Filter movies based on these selected tags.
        - selected_years (Optional[List[int]]): Filter movies based on these selected years.

        Returns:
        - List[Movie]: A list of movies sorted by match score in descending order.
        """
        phrase_lower = phrase.lower()
        movie_matches: Dict[Movie, float] = {}

        for movie in self.movies:
            title_lower = movie.title.lower()
            smp = simple_match_percentage(phrase_lower, title_lower)
            ldp = levenshtein_distance_percentage(phrase_lower, title_lower)
            lcsp = longest_common_substring_percentage(phrase_lower, title_lower)
            match_score = 25 * smp + 5 * ldp + 70 * lcsp
            if match_score >= min_match_score:
                movie_matches[movie] = match_score

        # Sort by match score
        sorted_movies_with_scores = sorted(movie_matches.items(), key=lambda x: x[1], reverse=True)

        # Extract movies only
        movies_sorted_by_score = [movie for movie, score in sorted_movies_with_scores]

        # Apply filtering based on tags and years
        if filter_tags:
            movies_sorted_by_score = self.filter_movies_by_tags(movies_sorted_by_score, filter_tags)
        if filter_years:
            movies_sorted_by_score = self.filter_movies_by_years(movies_sorted_by_score, filter_years)

        # Limit the number of items before sorting if limit_before_sort is True
        if limit_before_sort and max_items is not None:
            movies_sorted_by_score = movies_sorted_by_score[:max_items]

        # Sort based on the specified sort key
        if sort_key == 'match_score':
            result_movies = movies_sorted_by_score
        elif sort_key == 'title':
            result_movies = self.get_movies_sorted_by_title(max_items=None, reverse=reverse)
        elif sort_key == 'rating':
            result_movies = self.get_movies_sorted_by_rating(max_items=None, reverse=reverse)
        elif sort_key == 'year':
            result_movies = self.get_movies_sorted_by_year(max_items=None, reverse=reverse)
        elif sort_key == 'date_added':
            result_movies = self.get_movies_sorted_by_date_added(max_items=None, reverse=reverse)
        else:
            raise ValueError(f"Unknown sort_key: {sort_key}")

        # Filter out movies that were not in the original sorted by score list
        if sort_key != 'match_score':
            result_movies = [m for m in result_movies if m in movies_sorted_by_score]

        # Limit the number of items after sorting if limit_before_sort is False
        if not limit_before_sort and max_items is not None:
            result_movies = result_movies[:max_items]

        return result_movies
