from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from source.classes.website import Website
    from source.classes.types_base import Movie as MoviePayload


class Movie:
    def __init__(self, website: Website, data: MoviePayload) -> None:
        self.website: Website = website
        self.title: str = data.get('title', '')
        self.description: str = data.get('description', '')
        self.show_type: str = data.get('show_type', '')
        self.tags: str = data.get('tags', '')
        self.year: int = data.get('year', 0)
        self.length: int = data.get('length', 0)
        self.rating: float = data.get('rating', 0.0)
        self.votes: int = data.get('votes', 0)
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
