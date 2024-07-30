from datetime import datetime
from math import ceil
import pandas as pd
import importlib
import pickle

from typing import Dict, Tuple, List

from classes.website import Website
from classes.types_base import Website as WebsitePayload


async def collect_data() -> Tuple[List[str], List[Website]]:
    SCRAPE_URLS = {
        "cda-hd": "https://cda-hd.cc/filmy-online"
    }

    websites = [w for w in SCRAPE_URLS.keys()]

    # Run scripts that collects new data
    await scrape_new_data(SCRAPE_URLS, limit_pages=3)

    # Load existing data
    data = load_scraped_data(websites)

    return websites, data


async def scrape_new_data(data: Dict[str, str], limit_pages: int|None) -> None:
    counter = 0
    tasks_count = len(data)
    print("Collecting data...")
    st = datetime.now()
    for website, link in data.items():
        module = importlib.import_module(fr"scrape.{website}")

        result = await module.get_movies(website, fr'{link}', limit_pages)

        save_csv(result, fr'data/csv/{website}.csv')
        save_pkl(result, fr'data/pkl/{website}.pkl')

        counter += 1
        et = datetime.now()
        time_remain = (et - st) * ((tasks_count - counter) / counter)
        print(f"Done {counter}/{tasks_count} operations.")
        print(f"Remaining time approx: {ceil(time_remain.total_seconds() / 60)} min.")
    print("Data collected and saved successfully.")


def load_scraped_data(websites: List[str]) -> List[Website]:
    """Loads data to bot"""
    data = []
    for w in websites:
        payload: WebsitePayload = load_pkl(fr'data/pkl/{w}.pkl')
        website = Website(w, payload.get('movies', []))
        data.append(website)
    return data


def save_pkl(obj: WebsitePayload, filename: str) -> None:
    """Saves Python object as a pickle file."""
    with open(filename, 'wb') as out:  # Overwrites any existing file.
        pickle.dump(obj, out, pickle.HIGHEST_PROTOCOL)


def load_pkl(filename: str) -> WebsitePayload:
    """Loads saved Python object from local data."""
    with open(filename, 'rb') as inp:
        return pickle.load(inp)


def save_csv(data: WebsitePayload, filename: str) -> None:
    """Saves Website type class object as a csv type file."""
    columns = ['title', 'description', 'genres', 'year', 'length',
               'rating', 'votes', 'countries', 'link', 'image_link']

    movies = data.get('movies', [])

    if movies:
        obj_df = pd.DataFrame(
            [
                [
                    m.get("title"),
                    m.get("description"),
                    m.get("tags"),
                    m.get("year"),
                    m.get("length"),
                    m.get("rating"),
                    m.get("votes"),
                    m.get("countries"),
                    m.get("link"),
                    m.get("image_link"),
                ]
                for m in movies
            ],
            columns=columns,
        )
    else:
        obj_df = pd.DataFrame(columns=columns)

    obj_df.to_csv(filename, index=False)