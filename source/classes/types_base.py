from typing import TypedDict, List
from typing_extensions import NotRequired


class Movie(TypedDict):
    title: str
    description: str
    show_type: str
    tags: NotRequired[List[str]]
    year: int
    length: int
    rating: float
    votes: int
    countries: str
    link: str
    image_link: str
