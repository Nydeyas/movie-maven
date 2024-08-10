from typing import TypedDict, List


class Movie(TypedDict):
    title: str
    description: str
    show_type: str
    tags: str
    year: int
    length: int
    rating: float
    votes: int
    countries: str
    link: str
    image_link: str
