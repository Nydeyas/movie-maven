from datetime import datetime
from math import ceil
import pandas as pd
import importlib
import pickle

from typing import Dict, List, Any
from source.classes.website import Website

SCRAPE_URLS = {
    "cda-hd": "https://cda-hd.cc/filmy-online"
}


async def collect_data() -> List[Website]:
    websites = [w for w in SCRAPE_URLS.keys()]

    # Load existing data
    existing_data = load_scraped_data(websites)

    # Run scripts that collects new data
    await scrape_new_data(SCRAPE_URLS, limit_pages=2)

    # Reload data
    data = load_scraped_data(websites)

    return data


async def scrape_new_data(urls: Dict[str, str], max_pages: int | None, data: List[Website]) -> None:
    counter = 0
    tasks_count = len(urls)
    st = datetime.now()
    for i, (w_name, link) in enumerate(urls.items()):
        module = importlib.import_module(fr"scrape.{w_name}")

        print(f"Scraping data from {w_name}...")
        # Run web scraping
        result = await module.scrape_movies(w_name, fr'{link}', max_pages)

        # Add new data
        old_size = len(data[i].movies)
        data[i].add_movies(result, duplicates=False)
        new_size = len(data[i].movies)
        print(f"{new_size - old_size} new movies added to data.")

        save_csv(data[i], fr'data/websites/csv/{w_name}.csv')
        save_pkl(data[i], fr'data/websites/pkl/{w_name}.pkl')

        counter += 1
        et = datetime.now()
        time_remain = (et - st) * ((tasks_count - counter) / counter)
        print(f"Done {counter}/{tasks_count} scraping operations.")
        print(f"Remaining time approx: {ceil(time_remain.total_seconds() / 60)} min.")
    print("Data collected and saved successfully.")


def load_scraped_data(websites: List[str]) -> List[Website]:
    """Loads data to bot"""
    data = []
    for w_name in websites:
        try:
            w = load_pkl(fr'data/websites/pkl/{w_name}.pkl')
        except FileNotFoundError as e:
            print(e)
            w = Website(name=w_name, data=[])

        data.append(w)
    return data


def save_pkl(obj: Any, filename: str) -> None:
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
