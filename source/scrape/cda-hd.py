from source.to_thread import to_thread
from selenium.webdriver.common.by import By
from datetime import datetime
from typing import List
import re
from source.classes.types_base import Movie as MoviePayload
import logging
from seleniumbase import Driver


def find_first_number(text: str) -> str:
    """Finds the first number in the text."""
    return next((match.group() for match in re.finditer(r'\d+', text)), "")


def find_last_number(text: str) -> str:
    """Finds the last number in the text."""
    return next((match.group() for match in reversed(list(re.finditer(r'\d+', text)))), "")


@to_thread
def scrape_movies(site_name: str, site_link: str, max_pages: int | None) -> List[MoviePayload]:
    browser = Driver(uc=True, headless=True)
    a = datetime.now()
    movies = []

    # Get number of pages with movies
    try:
        browser.get(f'{site_link}/page/1/')
        browser.sleep(2)
        element_last_page = browser.find_element(By.LINK_TEXT, value="Ostatnia")
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

                    description_elements = browser.find_elements(By.XPATH, "//*[@id='cap1']/p")
                    description: str = description_elements[0].text if description_elements else ""

                    show_type: str = "Film"

                    tags_elements = browser.find_elements(By.XPATH, "//*[@id='uwee']//a[@rel='category tag']")
                    tags: str = ', '.join(t.text for t in tags_elements)

                    year_text = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/span").text
                    year_str = find_last_number(year_text)
                    year = int(year_str) if year_str.isdigit() else None

                    length_text = browser.find_element(By.XPATH, "//*[contains(@class, 'icon-time')]/..").text
                    length_str = find_first_number(length_text)
                    length = int(length_str) if length_str.isdigit() else None

                    rating_str = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/div[2]/a/div/span").text
                    rating = float(rating_str) if rating_str.replace('.', '', 1).isdigit() else "N/A"

                    votes_text = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/div[2]/div/span/b[2]").text
                    votes_str = find_first_number(votes_text)
                    votes = int(votes_str) if votes_str.isdigit() else None

                    countries = browser.find_element(By.XPATH, "//*[@id='uwee']/div[2]/p[4]").text
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
        browser.close()

    b = datetime.now()
    logging.info(f"cda-hd.get_movies() completed: {b - a}")
    return movies
