from source.to_thread import to_thread
from selenium import webdriver
from selenium.webdriver.common.by import By
from datetime import datetime
from typing import List
import re
from source.classes.types_base import Movie as MoviePayload


def find_first_number(text: str) -> str:
    """Finds the first number in the text."""
    return next((match.group() for match in re.finditer(r'\d+', text)), "")


def find_last_number(text: str) -> str:
    """Finds the last number in the text."""
    return next((match.group() for match in reversed(list(re.finditer(r'\d+', text)))), "")


@to_thread
def scrape_movies(website_name: str, website_link: str, max_pages: int | None) -> List[MoviePayload]:
    options = webdriver.FirefoxOptions()
    options.add_argument('-headless')
    browser = webdriver.Firefox(options=options)
    a = datetime.now()

    try:
        browser.get(f'{website_link}/page/1/')
        element_last_page = browser.find_element(By.LINK_TEXT, value="Ostatnia")
        href_last_page = element_last_page.get_attribute("href")
    except Exception as e:
        browser.close()
        print(f"Error 1 in cda-hd.get_movies(): {e}")
        return []

    scheme_list = re.findall(r'\d+', href_last_page)

    if scheme_list:
        try:
            movies = []

            # Check if maximum page limit is set
            if max_pages:
                pages_count = min(max_pages, int(scheme_list[0]))
            else:
                pages_count = int(scheme_list[0])

            for page_number in range(220, pages_count + 1):
                # Page with movies
                print(f"Page: {page_number}/{pages_count}")

                browser.get(f'{website_link}/page/{page_number}/')

                sector = browser.find_element(By.CLASS_NAME, "item_1")
                elements = sector.find_elements(By.CLASS_NAME, "item")
                hrefs = [e.find_element(By.TAG_NAME, "a").get_attribute('href') for e in elements]

                for h in hrefs:
                    # Movie url
                    browser.get(h)

                    # XPATH - faster than CSS Selector
                    obj = browser.find_element(By.XPATH, value="//*[@id='uwee']")
                    title: str = obj.find_element(By.XPATH, value="./div[2]/h1").text

                    d_elements = browser.find_elements(By.XPATH, value="//*[@id='cap1']/p")
                    description: str = d_elements[0].text if d_elements else ""

                    show_type: str = "Film"

                    tags_elements = obj.find_elements(By.XPATH, value=".//a[@rel='category tag']")
                    tags: List[str] = [t.text for t in tags_elements]

                    year_text = obj.find_element(By.XPATH, value="./div[2]/span").text
                    year_str = find_last_number(year_text)
                    year = int(year_str) if year_str.isdigit() else None

                    length_text = obj.find_element(By.XPATH, "//*[contains(@class, 'icon-time')]/..").text
                    length_str = find_first_number(length_text)
                    length = int(length_str) if length_str.isdigit() else None

                    rating_str = obj.find_element(By.XPATH, value="./div[2]/div[2]/a/div/span").text
                    rating = float(rating_str) if rating_str.replace('.', '', 1).isdigit() else "N/A"

                    votes_text = obj.find_element(By.XPATH, value="./div[2]/div[2]/div/span/b[2]").text
                    votes_str = find_first_number(votes_text)
                    votes = int(votes_str) if votes_str.isdigit() else None

                    countries: str = obj.find_element(By.XPATH, value="./div[2]/p[4]").text
                    image_link: str = obj.find_element(By.XPATH, value="./div[1]/div/img").get_attribute("src")
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
            print(f"Found {len(movies)} movies.")

        except Exception as e:
            print(f"Error 3 in cda-hd.get_movies(): {e}")
            return []

    else:
        browser.close()
        print(
            f"Error 2: Cannot process element: 'page_count' in cda-hd.get_movies(), website_name = {website_name}")
        return []

    b = datetime.now()
    print(f"cda-hd.get_movies() completed: {b - a}")
    browser.close()
    return movies
