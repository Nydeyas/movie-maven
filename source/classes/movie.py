from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from source.classes.movie_site import MovieSite
    from source.classes.types_base import Movie as MoviePayload


class Movie:
    def __init__(self, site: MovieSite, data: MoviePayload) -> None:
        self.site: MovieSite = site
        self.title: str = data.get('title', '')
        self.description: str = data.get('description', '')
        self.show_type: str = data.get('show_type', '')
        self.tags: str = data.get('tags', '')
        self.year: Optional[int] = data.get('year')
        self.length: Optional[int] = data.get('length')
        self.rating: Optional[float] = data.get('rating')
        self.votes: Optional[int] = data.get('votes')
        self.countries: str = data.get('countries', '')
        self.link: str = data.get('link', '')
        self.image_link: str = data.get('image_link', '')

    def __str__(self) -> str:
        return self.title

    def __repr__(self) -> str:
        cls_name = type(self).__name__
        return f"{cls_name}(title={self.title!r})"

    def __eq__(self, other: object) -> bool:
        return (
                isinstance(other, Movie)
                and self.title == other.title
                and self.year == other.year
        )

    def __hash__(self):
        return hash((self.title, self.year, self.length))

    def is_valid(self) -> bool:
        """Check if the movie is valid by ensuring that all required fields are filled properly."""
        return all(
            value not in (None, '')
            for value in (
                self.title, self.description, self.show_type, self.tags, self.countries, self.link, self.image_link
            )
        ) and all(
            value is not None
            for value in (self.year, self.length, self.rating, self.votes)
        )

    def to_payload(self) -> MoviePayload:
        return {
            'title': self.title,
            'description': self.description,
            'show_type': self.show_type,
            'tags': self.tags,
            'year': self.year,
            'length': self.length,
            'rating': self.rating,
            'votes': self.votes,
            'countries': self.countries,
            'link': self.link,
            'image_link': self.image_link,
        }
