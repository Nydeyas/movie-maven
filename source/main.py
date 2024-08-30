import asyncio
import time
import re
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Optional, Callable, List, Dict

import discord
from discord import Message, File
from discord.ext import commands, tasks
from discord.ext.commands import Context
import os
import collect_data
from dotenv import load_dotenv
import logging

from source.classes.enums import UserState, MovieTag
from source.classes.movie import Movie
from source.classes.user import User
from source.classes.watchlist import MovieEntry

# Logging
# Set up the log file handler to rotate daily
log_file_handler = TimedRotatingFileHandler(
    filename='logs/logfile.log',  # Active log file
    when='midnight',  # When to rotate
    interval=1,  # Interval for rotation
    backupCount=10000,  # Number of backup files to keep
    encoding='utf-8',  # Encoding of the log file
    utc=False  # UTC or local time
)
# Set up logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        log_file_handler,
        logging.StreamHandler()
    ]
)

# Load environment variables
load_dotenv()

# Discord Bot token
TOKEN = os.getenv('TOKEN')
if not TOKEN:
    raise ValueError(
        f"Environment variable 'TOKEN' is not set. Please set it in the .env file before running the application.")

# Intents
intents = discord.Intents.default()
intents.message_content = True

# Change the no_category default string in help command
help_command = commands.DefaultHelpCommand(
    no_category='Commands',
    show_parameter_descriptions=False
)

# Bot activity status
activity = discord.Activity(type=discord.ActivityType.listening, name="m.help")

# Bot
bot = discord.ext.commands.Bot(command_prefix=["m.", "M."], activity=activity, case_insensitive=True, intents=intents,
                               help_command=help_command)

# Constants
TEXT_CHANNELS = [1267279190206451752, 1267248186410406023]  # Discord channels IDs where the bot will operate
USERS_PATH = "data/users"
MAX_ROWS_SEARCH = 15  # Max number of rows showed in movie search
MAX_ROWS_WATCHLIST = 20  # Max number of rows showed in watchlist
MAX_FIELD_LENGTH = 1024  # Max length of the embed fields (up to 1024 characters limited by Discord)
MIN_MATCH_SCORE = 40  # Minimum score of similarity in the search(0-100)
REACTION_TIMEOUT = 600.0  # Time in seconds for bot to track reactions

# Global Bot values
bot.g_locked = False
bot.g_users = collect_data.load_pkl(f'{USERS_PATH}/users.pkl', [])  # List of Users with Movies lists.
bot.g_sites = []  # List of Sites with Movies data
bot.g_task_lock = asyncio.Lock()


@bot.event
async def on_ready() -> None:
    logging.info(f'Logged as: {bot.user}')

    # Start tasks
    update_site_data.start()
    save_user_data.start()


@tasks.loop(hours=12)
async def update_site_data() -> None:
    logging.info("Collecting data...")
    data = await collect_data.collect_data()

    logging.info("Loading data...")
    bot.g_locked = True  # bot controls blocked
    await asyncio.sleep(3)  # wait in case of handle state running
    bot.g_sites = data
    bot.g_locked = False
    logging.info(f"Using sites: {', '.join(w.name for w in bot.g_sites)}")


@tasks.loop(minutes=5)
async def save_user_data() -> None:
    z1 = datetime.now()

    users_copy = [user.copy_without_task() for user in bot.g_users]
    collect_data.save_pkl(users_copy, f'{USERS_PATH}/users.pkl')

    z2 = datetime.now()
    logging.info("save_user_data(): " + str(z2 - z1))


@bot.command(aliases=['szukaj', 's', 'filmy', 'films', 'movies'], brief='Wyszukiwanie filmów',
             description='Wyszukuje tytuł filmu na podstawie wpisanej frazy')
async def search(ctx: Context, *title: Optional[str]) -> None:
    """
        This command allows users to search for movies with a query. The query can be a single word or multiple words.
        If no query is provided, the function will open a search panel where users can enter their search criteria.

        Parameters:
        - ctx (Context): The context in which the command was invoked.
        - title (Optional[str]): One or more words representing the movie title to search for.
    """
    if ctx.channel.id in TEXT_CHANNELS and not bot.g_locked:
        if not is_user(ctx.author.id):
            # Add new User
            bot.g_users.append(User(ctx.author.id, ctx.author.name, ctx.author.display_name))

        search_query = ' '.join(title) if title else ''
        ctx.message.content = search_query
        await search_movie(ctx.message)


@bot.command(aliases=['list', 'lista', 'w', 'wl', 'l'], brief='Lista filmów użytkownika',
             description='Wyświetla listę filmów użytkownika wraz z ocenami')
async def watchlist(ctx: Context) -> None:
    if ctx.channel.id in TEXT_CHANNELS and not bot.g_locked:
        if not is_user(ctx.author.id):
            # Add new User
            bot.g_users.append(User(ctx.author.id, ctx.author.name, ctx.author.display_name))
        await watchlist_panel(ctx.message)


@bot.event
async def on_message(message: Message) -> None:
    """Main message event handler."""
    if (
            bot.g_locked
            or message.channel.id not in TEXT_CHANNELS
            or not is_user(message.author.id)
            or message.content.startswith(tuple(bot.command_prefix))
    ):
        await bot.process_commands(message)
        return

    # Ignore bot's own messages
    if message.author == bot.user:
        return

    user = get_user(message.author.id)
    await process_state(message, user)

    await bot.process_commands(message)


async def process_state(message: Message, user) -> None:
    """Handles user input and executes the appropriate state handler."""
    old_state = user.state
    blacklist = [UserState.idle]
    state_functions = {
        UserState.search_movie: search_movie,
        UserState.movie_details_search: movie_details,
        UserState.movie_details_watchlist: movie_details,
        UserState.watchlist_panel: watchlist_panel,
    }

    # Determine the new state based on the input
    if message.content.isdecimal():  # Numeric input
        if int(message.content) in range(1, len(user.movie_selection_list) + 1) and old_state in [
            UserState.watchlist_panel,
            UserState.movie_details_watchlist
        ]:
            user.state = UserState.movie_details_watchlist
        elif old_state in [
            UserState.search_movie,
            UserState.movie_details_search,
        ]:
            user.state = UserState.movie_details_search
        else:
            logging.debug(f"Input: '{message.content}', Old State: '{old_state}', (returned)")
            return
    elif message.content.lower() == 'w':  # Go back
        if old_state == UserState.movie_details_search:  # Movie details from search
            user.state = UserState.search_movie
            message.content = user.search_query
        elif old_state == UserState.movie_details_watchlist:  # Movie details from watchlist
            user.state = UserState.watchlist_panel
        else:
            logging.debug(f"Input: '{message.content}', Old State: '{old_state}', (returned)")
            return
    else:  # Non-numeric input
        if old_state in [
            UserState.search_movie,
            UserState.movie_details_search,
            UserState.movie_details_watchlist
        ]:
            user.state = UserState.search_movie
        else:
            logging.debug(f"Input: '{message.content}', Old State: '{old_state}', (returned)")
            return

    new_state = user.state
    logging.debug(f"Input: '{message.content}', Old State: '{old_state}', New state: '{new_state}'")

    if new_state in blacklist:
        logging.debug(f"No handler was executed ('{new_state}' is blacklisted for handler )")
        return

    # Execute the handler for the new state
    handler = state_functions.get(new_state)
    if not handler:
        logging.warning(f"Unknown UserState: {new_state}")
        return

    try:
        fetched_message = await message.channel.fetch_message(user.message_id)
        logging.debug(f"Running handler: {handler.__name__}, Channel: '{str(message.channel)}'")
        await handler(message, fetched_message)
    except discord.HTTPException as err:
        logging.warning(f"Error fetching message ({message.channel}): {err}")
        user.state = UserState.idle
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


async def search_movie(user_message: Message, bot_message: Optional[Message] = None) -> None:
    """Search result panel shown (List of movies)"""
    # Emojis
    emoji_filter_tag = '🎭'
    emoji_filter_year = '🎦'
    emoji_sort = '🔀'
    emoji_sort_reset = '🔄'
    emoji_sort_exit = '🆗'
    emoji_sort_by_title = '🆎'
    emoji_sort_by_year = '📅'
    emoji_sort_by_rating = '🏆'
    emoji_sort_by_date_added = '🔥'
    emoji_sort_descending = '📉'
    emoji_sort_ascending = '📈'

    ctx = await bot.get_context(user_message)
    channel = user_message.channel
    user = get_user(ctx.author.id)
    user.state = UserState.search_movie
    user_input = user_message.content[:100]
    user.search_query = user_input
    msg = bot_message

    # Default sorting parameters
    if user_input:
        sort_ascending = True
        sort_key = 'match_score'
    else:
        sort_ascending = False
        sort_key = 'date_added'

    selected_tags = []
    selected_years = []

    def make_embed(movies: List[Movie]) -> discord.Embed:
        """Create the embed message with the current search results."""
        title = f"Wyszukiwarka filmów ({user.display_name})"
        field_title, field_year_tags, field_rating = '', '', ''
        i = 1

        for s in bot.g_sites:
            site_name = f"**{str(s).upper()}:**\n"
            line_break = "\u200B\n"

            # Check field length limit
            if (len(field_title) + len(site_name) > MAX_FIELD_LENGTH or
                    len(field_year_tags) + len(line_break) > MAX_FIELD_LENGTH or
                    len(field_rating) + len(line_break) > MAX_FIELD_LENGTH):
                break

            # Add site name to field_title and placeholders for alignment
            field_title += site_name
            field_year_tags += line_break
            field_rating += line_break

            for movie in movies:
                if movie.site != s:  # Skip movies not from the current site
                    continue

                watched_mark = '✔' if user.watchlist.has_movie(movie) else ''
                column_title = f"{watched_mark} {i}\. {movie.title.split('/')[0]}"
                column_year_tags = f"{movie.year}\u2003{movie.tags}"
                column_rating = f"{movie.rating}"

                # Limit Row Width
                if len(column_title) >= 37:
                    column_title = column_title[:34] + "..."
                if len(column_year_tags) >= 26:
                    column_year_tags = column_year_tags[:23].rstrip(",") + "..."

                # Check field length limit
                if (len(field_title) + len(column_title) + 1 > MAX_FIELD_LENGTH or
                        len(field_year_tags) + len(column_year_tags) + 1 > MAX_FIELD_LENGTH or
                        len(field_rating) + len(column_rating) + 1 > MAX_FIELD_LENGTH):
                    break

                field_title += column_title + "\n"
                field_year_tags += column_year_tags + "\n"
                field_rating += column_rating + "\n"
                i += 1

        if not movies:
            if not user_input and not selected_tags and not selected_years:
                description = "Brak filmów w bazie."
            else:
                description = f"**Wyniki: {user_input}**\n\nNie znaleziono pasujących wyników.\n"
            e = construct_embedded_message(title=title, description=description)
        else:
            # Filter description
            filtering_info = ''
            if selected_tags:
                tags = ", ".join(selected_tags)
                if len(tags) >= 100:
                    tags = tags[:97] + '...'
                filtering_info += f'• **Gatunek**: {tags}\n'

            if selected_years:
                years = list_to_range_string(selected_years)
                if len(years) >= 100:
                    years = years[:97] + '...'
                filtering_info += f'• **Rok produkcji**: {years}\n'

            if filtering_info:
                filtering_info = '**Filtrowanie:**\n' + filtering_info

            # Sort description
            sort_desc = {
                'title': 'Tytuł',
                'rating': 'Ocena',
                'year': 'Rok'
            }
            if sort_key == 'date_added':
                if sort_ascending:
                    sorting_info = '**Sortowanie:\n• Najdawniej dodane**\n'
                else:
                    if user_input:
                        sorting_info = '**Sortowanie:\n• Ostatnio dodane**\n'
                    else:
                        sorting_info = '**Ostatnio dodane:**\n'  # Default sort text for empty m.search command
            elif sort_key != 'match_score':
                key = sort_key.split('_')[0]  # Extract part before '_'
                sort_label = sort_desc.get(key, '')
                order_label = 'rosnąco' if sort_ascending else 'malejąco'
                sorting_info = f'**Sortowanie:\n• {sort_label}**: {order_label}\n'
            else:
                sorting_info = ''

            # Create description based on user_input
            if user_input:
                description = f"{filtering_info}{sorting_info}\n**Wyniki: {user_input}**\n\n"
            else:
                description = (
                    "**Info:**\nWpisz na czacie tytuł filmu do wyszukania lub numer z poniższej listy.\n"
                    f"Możesz także zastosować odpowiednie filtry za pomocą reakcji.\n\n{filtering_info}{sorting_info}\n\n"
                )

            # Construct the embed message
            e = construct_embedded_message(field_title, field_year_tags, field_rating, title=title,
                                           description=description)
        return e

    def get_tags_from_input(input_str: str) -> List[str]:
        """Convert user input (numbers or tag names) to a list of MovieTag names as strings."""
        tags = []
        input_parts = input_str.split(',')
        tag_map = {str(x): t for x, t in enumerate(MovieTag, start=1)}  # Map numbers to tags

        for p in input_parts:
            p = p.strip().lower()

            if p.isdigit() and p in tag_map:  # If it's a number and in the tag map
                tags.append(tag_map[p].value)
            else:
                for t in MovieTag:
                    if t.value.lower() == p:  # If it's a tag name
                        tags.append(t.value)
                        break
        return tags

    def get_years_from_input(input_str: str) -> List[int]:
        """
        Convert a string containing years and year ranges (e.g., "2000-2002, 2003, 2005-2006")
        into a sorted list of individual years.
        """
        min_year = 1900
        max_year = 2100

        years = []
        input_parts = input_str.split(',')

        for p in input_parts:
            p = p.strip()

            if '-' in p:  # Handle year range (e.g., "2000-2002")
                y_start_str, y_end_str = p.split('-')

                if not y_start_str.isdigit() or not y_end_str.isdigit():
                    continue

                y_start, y_end = int(y_start_str), int(y_end_str)

                if y_start > y_end:  # Swap if the range is given in reverse
                    y_start, y_end = y_end, y_start

                # Limit the range to valid years
                if y_start < min_year:
                    y_start = min_year
                if y_end > max_year:
                    y_end = max_year

                years.extend(range(y_start, y_end + 1))
            else:  # Handle single year (e.g., "2003")
                if not p.isdigit():
                    continue
                year = int(p)
                if min_year <= year <= max_year:
                    years.append(year)

        return sorted(years)

    def list_to_range_string(numbers):
        if not numbers:
            return ""

        numbers = sorted(numbers)
        ranges = []
        start = numbers[0]
        end = numbers[0]

        for n in numbers[1:]:
            if n == end + 1:
                end = n
            else:
                if start == end:
                    ranges.append(f"{start}")
                else:
                    ranges.append(f"{start}-{end}")
                start = end = n

        if start == end:
            ranges.append(f"{start}")
        else:
            ranges.append(f"{start}-{end}")

        return ", ".join(ranges)

    # Delete the user's message if the function wasn't triggered by a command.
    if msg:
        await user_message.delete()

    # Main loop for handling user interactions
    while True:
        # Perform the search with sorting
        result_movies = []
        for site in bot.g_sites:
            # Get specific search result if there is input or search for all movies if there is no input
            site_movies = site.search_movies(
                phrase=user_input,
                max_items=MAX_ROWS_SEARCH,
                min_match_score=MIN_MATCH_SCORE if user_input else 0.0,
                sort_key=sort_key,
                reverse=not sort_ascending,
                limit_before_sort=True if user_input else False,
                filter_tags=selected_tags,
                filter_years=selected_years
            )
            result_movies.extend(site_movies)

        user.movie_selection_list = result_movies

        embed = make_embed(result_movies)
        emoji_to_text = {
            emoji_filter_tag: "Filtruj (Gatunek)",
            emoji_filter_year: "Filtruj (Rok produkcji)",
            emoji_sort: "Sortuj",
        }
        footer = make_footer(emoji_mapping=emoji_to_text)
        embed.set_footer(text=footer)

        if msg is None:
            msg = await channel.send(embed=embed)
            user.message_id = msg.id
        else:
            await msg.edit(embed=embed)

        # Get user reaction for sorting
        payload = await get_user_reaction(msg, list(emoji_to_text.keys()), user, REACTION_TIMEOUT)
        if payload is None:
            return

        selected_emoji = str(payload.emoji)

        if selected_emoji == emoji_sort:  # Sorting menu
            while True:
                # Prepare sorting options based on the current sort key
                sort_options = {
                    'match_score': {emoji_sort_by_title: "Sortuj po Tytule", emoji_sort_by_year: "Sortuj po Roku wydania",
                                    emoji_sort_by_rating: "Sortuj po Ocenie",
                                    emoji_sort_by_date_added: "Sortuj po dacie dodania"},
                    'title': {emoji_sort_by_year: "Sortuj po Roku wydania", emoji_sort_by_rating: "Sortuj po Ocenie",
                              emoji_sort_by_date_added: "Sortuj po dacie dodania"},
                    'year': {emoji_sort_by_title: "Sortuj po Tytule", emoji_sort_by_rating: "Sortuj po Ocenie",
                             emoji_sort_by_date_added: "Sortuj po dacie dodania"},
                    'rating': {emoji_sort_by_title: "Sortuj po Tytule", emoji_sort_by_year: "Sortuj po Roku wydania",
                               emoji_sort_by_date_added: "Sortuj po dacie dodania"},
                    'date_added': {emoji_sort_by_title: "Sortuj po Tytule", emoji_sort_by_year: "Sortuj po Roku wydania",
                                   emoji_sort_by_rating: "Sortuj po Ocenie"}
                }
                emoji_to_text = sort_options.get(sort_key, {})

                # Sorting order options
                if sort_key != 'match_score':
                    if sort_ascending:
                        emoji_to_text[emoji_sort_descending] = "Sortuj malejąco"
                    else:
                        emoji_to_text[emoji_sort_ascending] = "Sortuj rosnąco"
                    emoji_to_text[emoji_sort_reset] = "Resetuj sortowanie"

                emoji_to_text[emoji_sort_exit] = "Akceptuj"

                # Update embed with sorting options
                embed = make_embed(result_movies)
                embed.set_footer(text=make_footer(emoji_mapping=emoji_to_text))
                await msg.edit(embed=embed)

                sort_payload = await get_user_reaction(msg, list(emoji_to_text.keys()), user, REACTION_TIMEOUT)
                if sort_payload is None:
                    return

                sort_selected_emoji = str(sort_payload.emoji)

                if sort_selected_emoji == emoji_sort_reset:
                    sort_key = 'match_score'
                    sort_ascending = True
                elif sort_selected_emoji == emoji_sort_by_title:
                    sort_key = 'title'
                elif sort_selected_emoji == emoji_sort_by_year:
                    sort_key = 'year'
                elif sort_selected_emoji == emoji_sort_by_rating:
                    sort_key = 'rating'
                elif sort_selected_emoji == emoji_sort_by_date_added:
                    sort_key = 'date_added'
                elif sort_selected_emoji == emoji_sort_descending:
                    sort_ascending = False
                elif sort_selected_emoji == emoji_sort_ascending:
                    sort_ascending = True
                elif sort_selected_emoji == emoji_sort_exit:
                    break  # Exit sorting menu

                # Re-fetch and update the movies list based on the new sort settings
                result_movies = []
                for site in bot.g_sites:
                    site_movies = site.search_movies(
                        phrase=user_input,
                        max_items=MAX_ROWS_SEARCH,
                        min_match_score=MIN_MATCH_SCORE if user_input else 0.0,
                        sort_key=sort_key,
                        reverse=not sort_ascending,
                        limit_before_sort=True if user_input else False,
                        filter_tags=selected_tags,
                        filter_years=selected_years
                    )
                    result_movies.extend(site_movies)

                user.movie_selection_list = result_movies

        elif selected_emoji == emoji_filter_tag:  # Filter by tag
            user.state = UserState.input_search_filter

            await msg.clear_reactions()

            # Make list of tags from MovieTag Enum
            lines = []
            for i, tag in enumerate(MovieTag, start=1):
                lines.append(f"{i}. {tag.value}")
            tag_list = "\n".join(lines)

            # Edit message
            filter_prompt = (
                f"Wprowadź gatunki z listy lub ich numery (np. '1,2,8', lub 'horror, dramat'):\n\n{tag_list}"
            )
            footer = make_footer(show_back_text=True)
            filter_embed = construct_embedded_message(title="Filtrowanie (Gatunek)", description=filter_prompt,
                                                      footer=footer)
            await msg.edit(embed=filter_embed)

            # Get User input
            response = await get_user_text(user,REACTION_TIMEOUT)

            if response is None:  # Timeout
                timeout_description = "Czas na wprowadzenie tekstu upłynął."
                filter_embed = construct_embedded_message(title="Filtrowanie (Gatunek)",
                                                          description=timeout_description)
                await msg.edit(embed=filter_embed)
                return

            if response.content == 'w':  # Go back
                await response.delete()
                user.state = UserState.search_movie
                continue

            # Process the filter text
            selected_tags = get_tags_from_input(response.content)

            await response.delete()
            user.state = UserState.search_movie

        elif selected_emoji == emoji_filter_year:  # Filter by year
            user.state = UserState.input_search_filter

            await msg.clear_reactions()

            filter_prompt = 'Wprowadź rok lub zakres lat (np. 2000-2005, 2012, 2024)'
            footer = make_footer(show_back_text=True)
            filter_embed = construct_embedded_message(title="Filtrowanie (Rok wydania)", description=filter_prompt, footer=footer)
            await msg.edit(embed=filter_embed)

            pattern = r'^(\d+(-\d+)?)(,\s*\d+(-\d+)?)*$'

            response = await get_user_text(
                user,
                REACTION_TIMEOUT,
                check=(
                    lambda m: m.author == user_message.author
                    and m.channel.id == msg.channel.id
                    and (bool(re.match(pattern, m.content)) or m.content == 'w')
                )
            )

            if response is None:  # Timeout
                timeout_description = "Czas na wprowadzenie tekstu upłynął."
                filter_embed = construct_embedded_message(title="Filtrowanie (Rok produkcji)", description=timeout_description)
                await msg.edit(embed=filter_embed)
                return

            if response.content == 'w':  # Go back
                await response.delete()
                user.state = UserState.search_movie
                continue

            # Process the filter text
            selected_years = get_years_from_input(response.content)

            await response.delete()
            user.state = UserState.search_movie


async def movie_details(user_message: Message, bot_message: Message) -> None:
    """Individual movie panel"""
    add_to_watchlist_emoji = '📥'
    remove_from_watchlist_emoji = '📤'
    rate_movie_emoji = '📊'

    user = get_user(user_message.author.id)

    if not user:
        title = "Wyszukiwarka filmów (Brak użytkownika)"
        description = "**Użytkownik nie istnieje.**\n\n"
        embed = construct_embedded_message(title=title, description=description)
        await user_message.delete()
        await bot_message.edit(embed=embed)
        return

    title = f"Wyszukiwarka filmów ({user.display_name})"
    input_int = int(user_message.content)

    if input_int not in range(1, len(user.movie_selection_list) + 1):
        description = "**Wprowadzono liczbę poza zakresem.**\n\n"
        embed = construct_embedded_message(title=title, description=description)
        await user_message.delete()
        await bot_message.edit(embed=embed)
        return

    user.selection_input = input_int
    selected_movie = user.movie_selection_list[input_int - 1]

    description = (
        f"**{selected_movie.year}r\u2004|\u2004{selected_movie.length}min\u2004|\u2004{selected_movie.tags}**\n\n"
        f"{selected_movie.description}\n\n"
        f"Ocena: {selected_movie.rating}/10\n"
        f"{selected_movie.votes} głosów\n\n"
        f"Format: {selected_movie.show_type}\n"
        f"Kraje: {selected_movie.countries}\n\n"
        f"Link: {selected_movie.link}\n\n"
    )

    # Make embedded message
    embed = construct_embedded_message(title=selected_movie.title, description=description)
    embed.set_image(url=selected_movie.image_link)

    # Prepare reaction emojis
    if user.watchlist.has_movie(selected_movie):
        emoji_to_text = {remove_from_watchlist_emoji: "Usuń z listy filmów", rate_movie_emoji: "Oceń film"}
    else:
        emoji_to_text = {add_to_watchlist_emoji: "Zapisz na liście filmów"}

    # Set footer, Delete User message, Edit Bot message
    footer_text = make_footer(emoji_mapping=emoji_to_text, show_back_text=True)
    embed.set_footer(text=footer_text)
    await user_message.delete()
    msg = await bot_message.edit(embed=embed)

    # Waiting for user reaction and updating message
    while True:
        payload = await get_user_reaction(msg, list(emoji_to_text.keys()), user, REACTION_TIMEOUT)
        if payload is None:
            return
        selected_emoji = str(payload.emoji)

        # Change the status of the movie on the watchlist and update the footer
        if selected_emoji == add_to_watchlist_emoji:
            user.watchlist.add_movie(selected_movie)
            emoji_to_text = {remove_from_watchlist_emoji: "Usuń z listy filmów", rate_movie_emoji: "Oceń film"}
        elif selected_emoji == remove_from_watchlist_emoji:
            user.watchlist.remove_movie(selected_movie)
            emoji_to_text = {add_to_watchlist_emoji: "Zapisz na liście filmów"}
        elif selected_emoji == rate_movie_emoji:
            state = user.state
            await rate_movie(user_message, bot_message)
            time.sleep(2.5)
            user.state = state
        # Update message
        footer_text = make_footer(emoji_mapping=emoji_to_text, show_back_text=True)
        embed.set_footer(text=footer_text)
        await msg.edit(embed=embed)


async def rate_movie(user_message: Message, bot_message: Message) -> None:
    # Prompt user to enter rating
    user = get_user(user_message.author.id)
    old_state = user.state
    if old_state == UserState.movie_details_watchlist:
        user.state = UserState.rate_movie_watchlist
    else:
        user.state = UserState.rate_movie_search
    input_int = int(user_message.content)
    selected_movie = user.movie_selection_list[input_int - 1]

    await bot_message.clear_reactions()
    rating_prompt = "Wpisz ocenę filmu (1-10):"
    footer = make_footer(show_back_text=True)
    rating_embed = construct_embedded_message(title="Oceń Film", description=rating_prompt, footer=footer)
    await bot_message.edit(embed=rating_embed)

    # Wait for user to enter a rating
    response = await get_user_text(
        user,
        REACTION_TIMEOUT,
        check=(
            lambda m: m.author == user_message.author
            and ((m.content.replace(".", "", 1).isdigit() and 1 <= float(m.content) <= 10) or (m.content == 'w'))
            and m.channel.id == bot_message.channel.id
        )
    )
    if response is None:
        timeout_description = "Czas na ocenę filmu upłynął."
        rating_embed = construct_embedded_message(title="Oceń Film", description=timeout_description)
        await bot_message.edit(embed=rating_embed)
        return

    if response.content == 'w':  # Go back
        await response.delete()
        user.state = old_state
        return

    # Update rating
    new_rating = int(response.content) if response.content.isdigit() else round(float(response.content), 1)
    user.watchlist.update_rating(selected_movie, new_rating)

    # Confirm rating update
    confirm_description = f"Film został oceniony na {new_rating}/10."
    footer = make_footer(text="m.list - otwiera listę filmów")
    rating_embed = construct_embedded_message(title="Oceniono Film", description=confirm_description, footer=footer)
    await response.delete()
    await bot_message.edit(embed=rating_embed)


async def watchlist_panel(user_message: Message, bot_message: Optional[Message] = None) -> None:
    """Main panel of the watchlist with sorting and pagination"""
    # Emojis
    emoji_previous_page = '⬅'
    emoji_next_page = '➡'
    emoji_sort = '🔀'
    emoji_download = '🧾'
    emoji_sort_exit = '🆗'
    emoji_sort_by_title = '🆎'
    emoji_sort_by_date_added = '📅'
    emoji_sort_by_rating = '📊'
    emoji_sort_descending = '📉'
    emoji_sort_ascending = '📈'

    ctx = await bot.get_context(user_message)
    channel = user_message.channel
    user = get_user(ctx.author.id)
    user.state = UserState.watchlist_panel
    title = f"Lista filmów ({user.display_name})"
    msg = bot_message

    entries = user.watchlist.get_entries_sorted_by_title()  # Default sort by title
    entries_count = len(entries)

    # If User message is not initial message - delete it
    if msg is not None:
        await user_message.delete()

    if not entries:
        description = "**Twoja lista jest pusta.**\n" \
                      "Skorzystaj z komendy **m.szukaj**, aby wyszukać i dodać wybrane przez siebie filmy."
        embed = construct_embedded_message(title=title, description=description, colour=0xdfc118)
        # Send embedded message
        await channel.send(embed=embed)
        return

    def update_entries():
        """Update entries based on the current sort key and order"""
        nonlocal entries
        if sort_key == 'title':
            entries = user.watchlist.get_entries_sorted_by_title(reverse=not sort_ascending)
        elif sort_key == 'date_added':
            entries = user.watchlist.get_entries_sorted_by_date(reverse=not sort_ascending)
        elif sort_key == 'rating':
            entries = user.watchlist.get_entries_sorted_by_rating(reverse=not sort_ascending)

    def make_embed(page_entries: List[MovieEntry], page_number: int, show_sorting_info: bool = False) -> discord.Embed:
        # Generate the sorting description if requested
        if show_sorting_info:
            sort_criteria = {
                'title': 'Tytuł',
                'date_added': 'Data dodania',
                'rating': 'Ocena'
            }
            order = 'rosnąco' if sort_ascending else 'malejąco'
            sorting_info = f"**Sortowanie: {sort_criteria.get(sort_key, '')} ({order})**"
        else:
            sorting_info = ""

        field_title = 'Tytuł\n'
        field_date = 'Data dodania\n'
        field_rating = 'Ocena\n'
        for i, entry in enumerate(page_entries):
            e_title = entry.movie.title
            e_date = entry.date_added
            e_rating = '\u200B' if entry.rating is None else entry.rating
            e_number = i + 1 + (page_number - 1) * MAX_ROWS_WATCHLIST

            column_title = f"{e_number}\. {e_title}"
            column_date = f"{e_date}"
            column_rating = f"{e_rating}"

            if len(column_title) >= 50:
                column_title = column_title[:47] + "..."

            if (len(field_title) + len(column_title) + 1 > MAX_FIELD_LENGTH or
                    len(field_date) + len(column_date) + 1 > MAX_FIELD_LENGTH or
                    len(field_rating) + len(column_rating) + 1 > MAX_FIELD_LENGTH):
                break

            field_title += column_title + "\n"
            field_date += column_date + "\n"
            field_rating += column_rating + "\n"

        desc = f"Strona {page_number} z {pages_count}\n{sorting_info}"
        emb = construct_embedded_message(field_title, field_date, field_rating, title=title,
                                         description=desc, colour=0xdfc118)
        return emb

    pages = [entries[i:i + MAX_ROWS_WATCHLIST] for i in range(0, entries_count, MAX_ROWS_WATCHLIST)]
    pages_count = len(pages)
    current_page = 1
    sort_ascending = True  # Default sorting order
    sort_key = 'title'  # Default sorting key
    msg = None  # Initialize the message variable

    while True:  # Main loop
        # Prepare emojis based on the current page
        emoji_to_text = {}
        if pages_count > 1:
            if current_page > 1:
                emoji_to_text[emoji_previous_page] = "Wstecz"
            if current_page < pages_count:
                emoji_to_text[emoji_next_page] = "Dalej"
        emoji_to_text[emoji_sort] = "Sortuj"
        emoji_to_text[emoji_download] = "Pobierz listę"

        # Make embed and footer
        embed = make_embed(pages[current_page - 1], current_page)
        footer = make_footer(emoji_mapping=emoji_to_text)
        embed.set_footer(text=footer)

        if msg is None:  # If it's the first time, send a new message
            msg = await channel.send(embed=embed)
            user.message_id = msg.id
            user.movie_selection_list = [e.movie for e in entries]
        else:  # Otherwise, edit the existing message
            await msg.edit(embed=embed)

        # Get User reaction emoji
        payload = await get_user_reaction(msg, list(emoji_to_text.keys()), user, REACTION_TIMEOUT)
        if payload is None:
            return

        selected_emoji = str(payload.emoji)

        if selected_emoji == emoji_previous_page and current_page > 1:  # Previous
            current_page -= 1
        elif selected_emoji == emoji_next_page and current_page < pages_count:  # Next
            current_page += 1
        elif selected_emoji == emoji_sort:  # Sort
            while True:
                sort_options = {
                    'title': {emoji_sort_by_date_added: "Sortuj po Dacie dodania",
                              emoji_sort_by_rating: "Sortuj po Ocenie"},
                    'date_added': {emoji_sort_by_title: "Sortuj po Tytule", emoji_sort_by_rating: "Sortuj po Ocenie"},
                    'rating': {emoji_sort_by_title: "Sortuj po Tytule",
                               emoji_sort_by_date_added: "Sortuj po Dacie dodania"}
                }
                emoji_to_text = sort_options.get(sort_key, {})
                # Show sorting options
                if sort_ascending:
                    emoji_to_text[emoji_sort_descending] = "Sortuj malejąco"
                else:
                    emoji_to_text[emoji_sort_ascending] = "Sortuj rosnąco"
                emoji_to_text[emoji_sort_exit] = "Akceptuj"

                # Make embed and footer
                embed = make_embed(pages[current_page - 1], current_page, show_sorting_info=True)
                footer = make_footer(emoji_mapping=emoji_to_text)
                embed.set_footer(text=footer)

                # Send updated embed with new sorting
                await msg.edit(embed=embed)

                sort_payload = await get_user_reaction(msg, list(emoji_to_text.keys()), user, REACTION_TIMEOUT)
                if sort_payload is None:
                    return

                sort_selected_emoji = str(sort_payload.emoji)

                if sort_selected_emoji == emoji_sort_by_title:
                    sort_key = 'title'
                    update_entries()
                elif sort_selected_emoji == emoji_sort_by_date_added:
                    sort_key = 'date_added'
                    update_entries()
                elif sort_selected_emoji == emoji_sort_by_rating:
                    sort_key = 'rating'
                    update_entries()
                elif sort_selected_emoji == emoji_sort_descending:
                    sort_ascending = False
                    update_entries()
                elif sort_selected_emoji == emoji_sort_ascending:
                    sort_ascending = True
                    update_entries()
                elif sort_selected_emoji == emoji_sort_exit:
                    break  # Exit the sorting menu

                # Update pages and page count
                pages = [entries[i:i + MAX_ROWS_WATCHLIST] for i in range(0, len(entries), MAX_ROWS_WATCHLIST)]
                pages_count = len(pages)
                current_page = 1  # Reset to the first page
                user.movie_selection_list = [e.movie for e in entries]
        elif selected_emoji == emoji_download:  # Download list
            # Create the CSV file in memory
            csv_file = user.watchlist.get_csv(sort_key=sort_key, reverse=not sort_ascending)
            discord_file = File(fp=csv_file, filename=f"{user.display_name}.csv")
            await msg.clear_reactions()
            await msg.channel.send(file=discord_file)
            time.sleep(5)  # Use sleep to prevent spamming download requests

        # Update message after page change
        embed = make_embed(pages[current_page - 1], current_page)
        try:
            await msg.edit(embed=embed)
        except discord.NotFound as e:  # Message not found
            logging.warning(f"Message not found when attempting to edit: {e}. Message ID might be invalid or deleted.")
            msg = None  # Mark message as None to send a new one


async def get_user_reaction(
        message: discord.Message,
        emojis: List[str],
        controller: Optional[User] = None,
        timeout: Optional[float] = None,
        check: Callable[[discord.MessageInteraction], bool] | None = None
) -> Optional[discord.RawReactionActionEvent]:
    def check_default(payload: discord.RawReactionActionEvent):
        # CONDITIONS CHECK (1.user, 2.message, 3.emoji)
        user_id, msg_id, emoji = payload.user_id, payload.message_id, str(payload.emoji)
        id_list = [p.id for p in bot.g_users]
        return (
                (user_id == controller.id if controller else user_id in id_list)  # 1
                and (msg_id == message.id)  # 2
                and (emoji in emojis)  # 3
        )

    # Create task
    new_task = asyncio.create_task(bot.wait_for(
        "raw_reaction_add",
        timeout=timeout,
        check=check if check is not None else check_default
    ))

    async with bot.g_task_lock:
        if controller:
            # Cancel old task if exists
            old_task = controller.interaction_task
            if old_task and not old_task.done():
                old_task.cancel()
            # Save new task
            controller.interaction_task = new_task

    # Update reactions
    try:
        if message.channel.type != discord.ChannelType.private:
            await message.clear_reactions()
        for e in emojis:
            await message.add_reaction(e)
    except discord.NotFound as e:
        logging.warning(f"Failed to clear or add reactions. Message not found: {e}.")
        return
    except discord.HTTPException as e:
        logging.warning(f"Failed to clear or add reactions. HTTPException: {e}")

    # Wait for the reaction
    try:
        reaction_payload = await new_task
    except asyncio.CancelledError:
        logging.debug("Reaction task was cancelled.")
        return None
    except asyncio.TimeoutError:
        logging.debug(f"Reaction task timeout")
        return None
    return reaction_payload


async def get_user_text(
        controller: Optional[User] = None,
        timeout: Optional[float] = None,
        check: Callable[[discord.MessageInteraction], bool] | None = None
) -> Optional[discord.Message]:
    def check_default(message: discord.Message):
        # CONDITIONS CHECK (1.user, 2.message)
        user_id = message.author.id
        id_list = [p.id for p in bot.g_users]
        return (user_id == controller.id if controller else user_id in id_list) and (
                message.channel.id in TEXT_CHANNELS)

    # Create and update user task
    new_task = asyncio.create_task(bot.wait_for(
        'message',
        timeout=timeout,
        check=check if check is not None else check_default
    ))

    async with bot.g_task_lock:
        if controller:
            # Cancel old task if exists
            old_task = controller.interaction_task
            if old_task and not old_task.done():
                old_task.cancel()
            # Save new task
            controller.interaction_task = new_task

    # Wait for the text
    try:
        message_payload = await new_task
    except asyncio.CancelledError:
        logging.debug("Text task was cancelled.")
        return None
    except asyncio.TimeoutError:
        logging.debug(f"Text task timeout")
        return None
    return message_payload


def is_user(user_id: int):
    return any(user.id == user_id for user in bot.g_users)


def get_user(user_id: int):
    for user in bot.g_users:
        if user.id == user_id:
            return user
    return None


def construct_embedded_message(*fields: str, title: str = '', description: str = '', footer: str = '',
                               colour: int = 0x734ef8) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        colour=discord.Colour(colour),
        description=description,
    )
    for f in fields:
        embed.add_field(name="", value=f, inline=True)
    embed.set_footer(text=footer)
    return embed


def make_footer(text: str = None, show_back_text: bool = False, emoji_mapping: Optional[Dict[str, str]] = None) -> str:
    """Creates a footer string from emoji-to-text mapping."""
    footer_parts = []
    if emoji_mapping:
        footer_parts = [f"{emoji} {text}" for emoji, text in emoji_mapping.items()]
    if show_back_text:
        footer_parts.append("w - powrót")
    if text:
        footer_parts.append(text)
    return " | ".join(footer_parts)


bot.run(TOKEN)
