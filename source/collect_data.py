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
    await scrape_new_data(SCRAPE_URLS, max_pages=1, data=existing_data)

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
    try:
        with open(filename, 'wb') as out:  # Overwrites any existing file.
            pickle.dump(obj, out, pickle.HIGHEST_PROTOCOL)
        print(f"Object successfully saved to {filename}")
    except (OSError, pickle.PicklingError) as e:
        print(f"Failed to save object to {filename}: {e}")


def load_pkl(filename: str, value: Any = None) -> Any:
    """Loads saved Python object from local data."""
    try:
        with open(filename, 'rb') as inp:
            return pickle.load(inp)
    except (OSError, pickle.UnpicklingError) as e:
        print(f"Failed to load object from {filename}: {e}")
        return value


def save_csv(data: Website, filename: str) -> None:
    """Saves Website type class object as a csv type file."""
    columns = ['title', 'description', 'show_type', 'tags', 'year', 'length',
               'rating', 'votes', 'countries', 'link', 'image_link']

    movies = data.movies

    try:
        if movies:
            obj_df = pd.DataFrame(
                [
                    [
                        m.title,
                        m.description,
                        m.show_type,
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

            # Converting columns
            obj_df['title'] = obj_df['title'].astype('string')
            obj_df['description'] = obj_df['description'].astype('string')
            obj_df['show_type'] = obj_df['show_type'].astype('string')
            obj_df['tags'] = obj_df['tags'].astype('object')
            obj_df['year'] = obj_df['year'].astype('Int64')
            obj_df['length'] = obj_df['length'].astype('Int64')
            # obj_df['rating']
            obj_df['votes'] = obj_df['votes'].astype('Int64')
            obj_df['countries'] = obj_df['countries'].astype('string')
            obj_df['link'] = obj_df['link'].astype('string')
            obj_df['image_link'] = obj_df['image_link'].astype('string')
        else:
            obj_df = pd.DataFrame(columns=columns)

        obj_df.to_csv(filename, index=False)
        print(f"Data successfully saved to {filename}")

    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        print(f"Failed to save data to {filename}: {e}")
