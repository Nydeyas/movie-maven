import importlib
import logging
import os
import pickle
from datetime import datetime
from math import ceil
from typing import Dict, List, Any

import pandas as pd

from classes.movie_site import MovieSite

SITES_DATA_PATH = "source/data/sites"
SCRAPE_URLS = {
    "cda-hd": "https://cda-hd.cc/filmy-online"
}


async def collect_data() -> List[MovieSite]:
    sites = [w for w in SCRAPE_URLS.keys()]

    # Load existing data
    existing_data = load_scraped_data(sites)

    # Run scripts that collects new data
    await scrape_new_data(SCRAPE_URLS, max_pages=1, data=existing_data)

    # Reload data
    data = load_scraped_data(sites)

    return data


async def scrape_new_data(urls: Dict[str, str], max_pages: int | None, data: List[MovieSite]) -> None:
    counter = 0
    tasks_count = len(urls)
    st = datetime.now()
    for i, (w_name, link) in enumerate(urls.items()):
        module = importlib.import_module(fr"scrape.{w_name}")

        logging.info(f"Scraping data from {w_name}...")
        # Run web scraping
        result = await module.scrape_movies(w_name, fr'{link}', max_pages)

        # Join old data with new data
        old_size = len(data[i].movies) if data else 0
        data[i].add_movies(result, duplicates=False)
        new_size = len(data[i].movies)
        logging.info(f"{new_size - old_size} new movies added to data.")

        # Find invalid movies
        invalid_data = data[i].filter_invalid_movies()

        save_csv(data[i], fr'{SITES_DATA_PATH}/{w_name}/{w_name}.csv')
        save_pkl(data[i], fr'{SITES_DATA_PATH}/{w_name}/{w_name}.pkl')
        save_csv(invalid_data, fr'{SITES_DATA_PATH}/{w_name}/{w_name}-errors.csv')

        counter += 1
        et = datetime.now()
        time_remain = (et - st) * ((tasks_count - counter) / counter)
        logging.info(f"Done {counter}/{tasks_count} scraping operations.")
        logging.info(f"Remaining time approx: {ceil(time_remain.total_seconds() / 60)} min.")
    logging.info("Data collected and saved successfully.")


def load_scraped_data(sites: List[str]) -> List[MovieSite]:
    """Loads data to bot"""
    data = []
    for w_name in sites:
        w = load_pkl(fr'{SITES_DATA_PATH}/{w_name}/{w_name}.pkl')
        if w is None:
            w = MovieSite(name=w_name, data=[])
            logging.warning(f"Creating new MovieSite object for {w_name}")
        data.append(w)

    return data


def save_pkl(obj: Any, filename: str) -> None:
    """Saves Python object as a pickle file."""
    try:
        # Make a directory if it doesn't exist
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'wb') as out:  # Overwrites any existing file.
            pickle.dump(obj, out, pickle.HIGHEST_PROTOCOL)
        logging.info(f"Object successfully saved to {filename}")
    except (OSError, pickle.PicklingError) as e:
        logging.error(f"Failed to save object to {filename}: {e}")


def load_pkl(filename: str, value: Any = None) -> Any:
    """Loads saved Python object from local data."""
    try:
        with open(filename, 'rb') as inp:
            return pickle.load(inp)
    except FileNotFoundError:
        logging.warning(f"File not found: {filename}")
        return value
    except (OSError, pickle.UnpicklingError) as e:
        logging.error(f"Failed to load object from {filename}: {e}")
        return value
    except Exception as e:
        logging.error(f"Unexpected error while loading object from {filename}: {e}")
        return value


def save_csv(data: MovieSite, filename: str) -> None:
    """Saves site type class object as a csv type file."""
    columns = ['title', 'description', 'show_type', 'tags', 'year', 'length',
               'rating', 'votes', 'countries', 'link', 'image_link']

    movies = data.movies

    try:
        # Make a directory if it doesn't exist
        os.makedirs(os.path.dirname(filename), exist_ok=True)
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
        logging.info(f"Data successfully saved to {filename}")

    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError) as e:
        logging.error(f"Failed to save data to {filename}: {e}")
