from datetime import datetime
from math import ceil
import pandas as pd
import importlib
import pickle

from typing import Dict, Tuple, List

from classes.website import Website


async def collect_data() -> Tuple[List[str], List[Website]]:
    SCRAPE_URLS = {
        "cda-hd": "https://cda-hd.cc/filmy-online"
    }

    websites = [w for w in SCRAPE_URLS.keys()]

    # Run scripts that collects new data
    await scrape_new_data(SCRAPE_URLS, limit_pages=2)

    # Load new data
    print("Loading new data...")
    data = load_scraped_data(websites)

    return websites, data


async def scrape_new_data(data: Dict[str, str], limit_pages: int | None) -> None:
    counter = 0
    tasks_count = len(data)
    print("Collecting data...")
    st = datetime.now()
    for i, (w_name, link) in enumerate(data.items()):
        module = importlib.import_module(fr"scrape.{w_name}")

        # Run web scraping
        result: Website = await module.scrape_website(w_name, fr'{link}', limit_pages)

        save_csv(result, fr'data/csv/{w_name}.csv')
        save_pkl(result, fr'data/pkl/{w_name}.pkl')

        counter += 1
        et = datetime.now()
        time_remain = (et - st) * ((tasks_count - counter) / counter)
        print(f"Done {counter}/{tasks_count} operations.")
        print(f"Remaining time approx: {ceil(time_remain.total_seconds() / 60)} min.")
    print("Data collected and saved successfully.")


def load_scraped_data(websites: List[str]) -> List[Website]:
    """Loads data to bot"""
    data = []
    for w_name in websites:
        try:
            w = load_pkl(fr'data/pkl/{w_name}.pkl')
        except FileNotFoundError as e:
            print(e)
            w = Website(name=w_name, data=[])

        data.append(w)
    return data


def save_pkl(obj: Website, filename: str) -> None:
    """Saves Python object as a pickle file."""
    with open(filename, 'wb') as out:  # Overwrites any existing file.
        pickle.dump(obj, out, pickle.HIGHEST_PROTOCOL)


def load_pkl(filename: str) -> Website:
    """Loads saved Python object from local data."""
    with open(filename, 'rb') as inp:
        return pickle.load(inp)


def save_csv(data: Website, filename: str) -> None:
    """Saves Website type class object as a csv type file."""
    columns = ['title', 'description', 'tags', 'year', 'length',
               'rating', 'votes', 'countries', 'link', 'image_link']

    movies = data.movies

    if movies:
        obj_df = pd.DataFrame(
            [
                [
                    m.title,
                    m.description,
                    m.tags,
                    m.year,
                    m.length,
                    m.rating,
                    m.votes,
                    m.countries,
                    m.link,
                    m.image_link,
                ]
                for m in movies
            ],
            columns=columns,
        )
    else:
        obj_df = pd.DataFrame(columns=columns)

    obj_df.to_csv(filename, index=False)
