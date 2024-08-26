from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Dict
from difflib import SequenceMatcher
from Levenshtein import distance

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

    def get_movies_sorted_by_title(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        """Return a list of movies sorted alphabetically by title."""
        sorted_movies = sorted(self.movies, key=lambda movie: movie.title, reverse=reverse)
        return sorted_movies[:max_items] if max_items is not None else sorted_movies

    def get_movies_sorted_by_rating(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        """Return a list of movies sorted by rating."""
        sorted_movies = sorted(self.movies, key=lambda movie: movie.rating, reverse=reverse)
        return sorted_movies[:max_items] if max_items is not None else sorted_movies

    def get_movies_sorted_by_year(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        """Return a list of movies sorted by year."""
        sorted_movies = sorted(self.movies, key=lambda movie: movie.year, reverse=reverse)
        return sorted_movies[:max_items] if max_items is not None else sorted_movies

    def get_movies_sorted_by_date_added(self, max_items: Optional[int] = None, reverse: bool = False) -> List[Movie]:
        """Retrieves and returns a list of movies sorted by their date of addition."""
        sorted_movies = self.movies[::-1] if reverse else self.movies[:]
        return sorted_movies[:max_items] if max_items is not None else sorted_movies

    def search_movies(
            self,
            phrase: str,
            max_items: Optional[int] = None,
            min_match_score: float = 0.0,
            sort_key: str = 'match_score',
            reverse: bool = False
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

        Returns:
        - List[Movie]: A list of movies sorted by match score in descending order.
        """
        phrase_lower = phrase.lower()
        movie_matches: Dict[Movie, float] = {}

        for movie in self.movies:
            title_lower = movie.title.lower()
            smp = self.simple_match_percentage(phrase_lower, title_lower)
            ldp = self.levenshtein_distance_percentage(phrase_lower, title_lower)
            lcsp = self.longest_common_substring_percentage(phrase_lower, title_lower)
            match_score = 25 * smp + 5 * ldp + 70 * lcsp
            if match_score >= min_match_score:
                movie_matches[movie] = match_score

        # Extract sorted movies
        movies_sorted_by_score: List[Movie] = sorted(movie_matches.items(), key=lambda x: x[1], reverse=True)

        # Sort based on the specified sort key if it's not 'match_score'
        if sort_key == 'match_score':
            # Already sorted by match_score, no further sorting needed
            final_sorted_movies = movies_sorted_by_score
        elif sort_key == 'title':
            final_sorted_movies = self.get_movies_sorted_by_title(max_items=None, reverse=reverse)
        elif sort_key == 'rating':
            final_sorted_movies = self.get_movies_sorted_by_rating(max_items=None, reverse=reverse)
        elif sort_key == 'year':
            final_sorted_movies = self.get_movies_sorted_by_year(max_items=None, reverse=reverse)
        elif sort_key == 'date_added':
            final_sorted_movies = self.get_movies_sorted_by_date_added(max_items=None, reverse=reverse)
        else:
            raise ValueError(f"Unknown sort_key: {sort_key}")

        # Filter out movies that were not in the original sorted by score list (only if sort_key is not 'match_score')
        if sort_key != 'match_score':
            final_sorted_movies = [movie for movie in final_sorted_movies if movie in movies_sorted_by_score]

        # Limit the number of items if max_items is specified
        if max_items is not None:
            final_sorted_movies = final_sorted_movies[:max_items]

        return [movie for movie, score in final_sorted_movies]

    def simple_match_percentage(self, s1: str, s2: str) -> float:
        """Computes the simple comparison checking for exact word matches between the s1 and the s2."""
        if not s1 or not s2:
            return 0.0
        s1_split = s1.split(" ")
        match_count = sum(1 for x in s1_split if x in s2)
        return match_count / len(s1_split)

    def levenshtein_distance_percentage(self, s1: str, s2: str) -> float:
        """Computes the Levenshtein distance. Measures how closely the s1 matches the s2. Used mainly for typos."""
        if not s1 or not s2:
            return 0.0
        return 1.0 - distance(s1, s2) / max(len(s1), len(s2))

    def longest_common_substring_percentage(self, s1: str, s2: str) -> float:
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
