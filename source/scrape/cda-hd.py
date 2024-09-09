import logging
import re
from datetime import datetime
from typing import List, Any

from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

from classes.types_base import Movie as MoviePayload
from to_thread import to_thread


def find_first_number(text: str, find_decimal: bool = False, remove_separator: bool = True) -> str:
    """Finds the first number in the text."""
    if remove_separator:
        text = text.replace(',', '')
    pattern = r'\d+(\.\d+)?' if find_decimal else r'\d+'
    match = re.search(pattern, text)
    return match.group() if match else ""


def find_last_number(text: str, find_decimal: bool = False, remove_separator: bool = True) -> str:
    """Finds the last number in the text."""
    if remove_separator:
        text = text.replace(',', '')
    pattern = r'\d+(\.\d+)?' if find_decimal else r'\d+'
    matches = list(re.finditer(pattern, text))
    return matches[-1].group() if matches else ""


def extract_minutes(text: str, default: Any = None) -> int | None:
    """Extracts total minutes from a time string which could contain hours (h) and minutes (min)."""
    text = text.lower()
    total_minutes = 0

    # Extract hours if present
    hours_match = re.search(r'(\d+)\s*h', text)
    if hours_match:
        hours = hours_match.group(1)
        total_minutes += int(hours) * 60

    # Extract minutes if present
    minutes_match = re.search(r'(\d+)\s*min', text)
    if minutes_match:
        minutes = minutes_match.group(1)
        total_minutes += int(minutes)

    return total_minutes if total_minutes else default


@to_thread
def scrape_movies(site_name: str, site_link: str, max_pages: int | None) -> List[MoviePayload]:
    browser = Driver(uc=True, headless=True)
    a = datetime.now()
    movies = []

    # Get number of pages with movies
    try:
        browser.get(f'{site_link}/page/1/')
        element_last_page = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Ostatnia"))
        )
        href_last_page = element_last_page.get_attribute("href")
    except Exception as e:
        browser.close()
        logging.warning(f"Error 1 in cda-hd.get_movies(): {e}")
        return []

    scheme_list = re.findall(r'\d+', href_last_page)
    if not scheme_list:
        browser.close()
        logging.warning(f"Cannot process element: 'page_count', site_name = {site_name}")
        return []

    try:
        pages_count = min(max_pages, int(scheme_list[0])) if max_pages else int(scheme_list[0])

        for page_number in range(1, pages_count + 1):
            # Get page with movies
            logging.info(f"Page: {page_number}/{pages_count}...")

            browser.default_get(f'{site_link}/page/{page_number}/')

            sector = browser.find_element(By.CLASS_NAME, "item_1")
            elements = sector.find_elements(By.CLASS_NAME, "item")
            hrefs = [e.find_element(By.TAG_NAME, "a").get_attribute('href') for e in elements]

            for h in hrefs:
                # Single Movie url
                browser.default_get(h)
                try:
                    # XPATH - faster than CSS Selector
                    title: str = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/h1").text

                    try:
                        description = browser.find_element(By.XPATH, "//*[@id='cap1']/p").text
                    except NoSuchElementException:
                        description_elements = browser.find_elements(By.XPATH, "//*[@id='cap1']/div/p")
                        description: str = description_elements[0].text if description_elements else ""

                    show_type: str = "Film"

                    tags_elements = browser.find_elements(By.XPATH, "//*[@id='uwee']//a[@rel='category tag']")
                    tags: str = ', '.join(t.text for t in tags_elements)

                    year_text = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/span").text
                    year_str = find_last_number(year_text)
                    year = int(year_str) if year_str.isdigit() and 1900 < int(year_str) < 2100 else None
                    if not year:
                        year_str = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/p[1]/span[1]/a").text
                        year = int(year_str) if year_str.isdigit() and 1900 < int(year_str) < 2100 else None

                    length_text = browser.find_element(By.XPATH, "//*[contains(@class, 'icon-time')]/..").text
                    length = extract_minutes(length_text)

                    rating_str = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/div[2]/a/div/span").text
                    rating = float(rating_str.replace(',', '.')) if rating_str.replace(',', '.').replace('.', '', 1).isdigit() else None

                    votes_text = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/div[2]/div/span/b[2]").text
                    votes_str = find_first_number(votes_text)
                    votes = int(votes_str) if votes_str.isdigit() else None

                    countries = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/p[4]").text
                    countries = '' if countries.isdigit() else countries

                    image_link = browser.find_element(By.XPATH, "//*[@id='uwee']/div[1]/div/img").get_attribute("src")
                    link: str = h

                    movies.append(
                        MoviePayload(
                            title=title,
                            description=description,
                            show_type=show_type,
                            tags=tags,
                            year=year,
                            length=length,
                            rating=rating,
                            votes=votes,
                            countries=countries,
                            link=link,
                            image_link=image_link
                        )
                    )
                except Exception:
                    logging.warning(f"Error extracting movie details for URL {h}")
                    continue

        logging.info(f"Found {len(movies)} movies.")

    except Exception as e:
        logging.warning(f"Error scraping movies: {e}")

    finally:
        browser.quit()

    b = datetime.now()
    logging.info(f"cda-hd.get_movies() completed: {b - a}")
    return movies
