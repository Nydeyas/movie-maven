import asyncio
from datetime import datetime
from typing import Dict, List
from logging.handlers import TimedRotatingFileHandler

import discord
from discord import Message
from discord.ext import commands, tasks
from discord.ext.commands import Context
import os
from difflib import SequenceMatcher
from Levenshtein import distance
import collect_data
from dotenv import load_dotenv
import logging

from source.classes.enums import UserState
from source.classes.movie import Movie
from source.classes.user import User

# Logging
# Set up the log file handler to rotate daily
log_file_handler = TimedRotatingFileHandler(
    filename='logs/logfile.log',   # Active log file
    when='midnight',               # When to rotate
    interval=1,                    # Interval for rotation
    backupCount=10000,             # Number of backup files to keep
    encoding='utf-8',              # Encoding of the log file
    utc=False                      # UTC or local time
)
# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        log_file_handler,
        logging.StreamHandler()
    ]
)

load_dotenv()  # Load environment variables from .env file

# Intents and token
intents = discord.Intents.default()
intents.message_content = True
TOKEN = os.getenv('TOKEN')

# Change the no_category default string
help_command = commands.DefaultHelpCommand(
    no_category='Commands',
)

# Bot activity status
activity = discord.Activity(type=discord.ActivityType.listening, name="m.help")

# Bot
bot = discord.ext.commands.Bot(command_prefix=["m.", "M."], activity=activity, case_insensitive=True, intents=intents,
                               help_command=help_command)

# Constants
TEXT_CHANNELS = [1267279190206451752, 1267248186410406023]  # Discord channels IDs where the bot will operate
USERS_PATH = "data/users"
MAX_ROWS = 12  # max number of rows showed in the movie search
REQUIRED_MATCH_SCORE = 40  # minimum score of similarity in the search(0-100)

# Global Bot values
bot.g_locked = False
bot.g_users = collect_data.load_pkl(f'{USERS_PATH}/users.pkl', [])  # List of Users with Movies lists.
bot.g_sites = []  # List of Sites with Movies data


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

    collect_data.save_pkl(bot.g_users, f'{USERS_PATH}/users.pkl')

    z2 = datetime.now()
    logging.info("save_user_data(): " + str(z2 - z1))


@bot.command(aliases=['szukaj', 's', 'filmy', 'films', 'movies'], brief='Wyszukiwanie filmów',
             description='Wyszukuje tytuł filmu na podstawie wpisanej frazy')
async def search(ctx: Context) -> None:
    if ctx.channel.id in TEXT_CHANNELS and not bot.g_locked:
        if not is_user(ctx.author.id):
            # Add new User
            bot.g_users.append(User(ctx.author))
        await search_panel(ctx.message)


@bot.event
async def on_message(message: Message) -> None:
    if (
            not bot.g_locked
            and message.channel.id in TEXT_CHANNELS
            and is_user(message.author.id)
            and not message.content.startswith(tuple(bot.command_prefix))
    ):
        if message.author == bot.user:
            return

        user = get_user(message.author.id)

        # Handle User State
        if user.state in {UserState.search_panel, UserState.search_result}:
            if message.content.isnumeric() and int(message.content) in range(1, len(user.search_content) + 1):
                user.state = UserState.movie_details
            else:
                user.state = UserState.search_result

            state = user.state

            # Function mappings
            state_functions = {
                UserState.search_result: search_result,
                UserState.movie_details: movie_details,
            }
            handler = state_functions.get(state, None)
            if handler:
                # Find bot message
                try:
                    fetched_message = await message.channel.fetch_message(user.message_id)
                    logging.info(f"[main.py]: Message found ({str(message.channel)})")
                except discord.HTTPException as err:
                    logging.warning(f"[main.py]: Error fetching message ({message.channel}): {err}")
                    user.state = UserState.idle
                else:
                    await handler(message, fetched_message)
            else:
                logging.warning(f"[main.py]: Unknown UserState: {state}")

    await bot.process_commands(message)


async def search_panel(user_message: Message) -> None:
    """Main panel of search engine"""
    ctx = await bot.get_context(user_message)
    title = "Wyszukiwarka filmów"
    sites = bot.g_sites

    if sites and sites[0].movies:
        # Make list of movies
        movies = []
        for i in range(1, MAX_ROWS + 1):
            m = sites[0].movies[-i]
            movies.append(m)

        # Make description
        field_title = ''
        field_year_tags = ''
        field_rating = ''
        for i, movie in enumerate(movies):
            m_title = movie.title
            m_year = movie.year
            m_tags = movie.tags
            m_rating = movie.rating

            # Split removes alternative titles
            column_title = f"{i + 1}\. {m_title.split('/')[0]}"
            column_year_tags = f"{m_year}\u2003{m_tags}"
            column_rating = f"{m_rating}"

            if len(column_title) >= 37:
                column_title = column_title[:34] + "..."
            if len(column_year_tags) >= 26:
                column_year_tags = column_year_tags[:24].rstrip(",") + "..."

            field_title += column_title + "\n"
            field_year_tags += column_year_tags + "\n"
            field_rating += column_rating + "\n"

        description = "**Info:**\nWpisz na czacie tytuł filmu do wyszukania lub numer z poniższej listy.\n" \
                      "Możesz także zastosować odpowiednie filtry za pomocą reakcji.\n\n**Ostatnio dodane**:\n\n"
        embed = construct_embedded_message(field_title, field_year_tags, field_rating,  title=title,
                                           description=description)

        # Send embedded message
        msg = await user_message.channel.send(embed=embed)

        # Update User
        user = get_user(ctx.author.id)
        user.message_id = msg.id
        user.state = UserState.search_panel
        user.search_content = movies
    else:
        description = "Brak filmów w bazie."
        embed = construct_embedded_message(title=title, description=description)
        # Send embedded message
        await user_message.channel.send(embed=embed)


async def search_result(user_message: Message, bot_message: Message) -> None:
    """Search result panel shown (List of movies)"""
    user_input = user_message.content
    user = get_user(user_message.author.id)

    title = "Wyszukiwarka filmów"

    # Search for movie matches in all sites
    movie_matches: Dict[Movie, float] = {}
    for site in list(bot.g_sites):
        for movie in site.movies:
            smp = simple_match_percentage(user_input.lower(), movie.title.lower())
            ldp = levenshtein_distance_percentage(user_input.lower(), movie.title.lower())
            lcsp = longest_common_substring_percentage(user_input.lower(), movie.title.lower())
            match_score = 25 * smp + 5 * ldp + 70 * lcsp
            movie_matches[movie] = match_score

    if movie_matches:
        # Sort dict by match score
        movie_matches_sorted = sorted(movie_matches.items(), key=lambda x: x[1], reverse=True)
        # Filter results
        movie_matches_sorted = movie_matches_sorted[:MAX_ROWS]
        movies: List[Movie] = [movie for movie, score in movie_matches_sorted if score >= REQUIRED_MATCH_SCORE]

        # Make description
        description = "**Znalezione wyniki:**\n\n"
        field_title = ''
        field_year_tags = ''
        field_rating = ''

        for i, movie in enumerate(movies):
            m_title = movie.title
            m_year = movie.year
            m_tags = movie.tags
            m_rating = movie.rating

            # Split removes alternative titles
            column_title = f"{i + 1}\. {m_title.split('/')[0]}"
            column_year_tags = f"{m_year}\u2003{m_tags}"
            column_rating = f"{m_rating}"

            if len(column_title) >= 37:
                column_title = column_title[:34] + "..."
            if len(column_year_tags) >= 26:
                column_year_tags = column_year_tags[:23].rstrip(",") + "..."

            field_title += column_title + "\n"
            field_year_tags += column_year_tags + "\n"
            field_rating += column_rating + "\n"

        # Send embedded message
        embed = construct_embedded_message(field_title, field_year_tags, field_rating, title=title,
                                           description=description)
        # Update User
        user.search_content = movies

    else:
        description = "Nie znaleziono pasujących wyników."
        embed = construct_embedded_message(title=title, description=description)

    # Delete User message, Edit Bot message
    await user_message.delete()
    await bot_message.edit(embed=embed)


async def movie_details(user_message: Message, bot_message: Message) -> None:
    """Individual movie panel"""
    input_int = int(user_message.content)
    user = get_user(user_message.author.id)
    search_content = user.search_content

    title = "Wyszukiwarka filmów"

    if input_int in range(1, len(search_content) + 1):

        selected_movie = search_content[input_int - 1]

        m_title = selected_movie.title
        m_description = selected_movie.description
        m_show_type = selected_movie.show_type
        m_tags = selected_movie.tags
        m_year = selected_movie.year
        m_length = selected_movie.length
        m_rating = selected_movie.rating
        m_votes = selected_movie.votes
        m_countries = selected_movie.countries
        m_link = selected_movie.link
        m_image_link = selected_movie.image_link
        title = m_title
        # Make description
        description = f"**{m_year}r\u2004|\u2004{m_length}min\u2004|\u2004{m_tags}\n\n**" \
                      f"{m_description}\n\n" \
                      f"**Ocena: {m_rating}/10**\n" \
                      f"{m_votes} głosów\n\n" \
                      f"Format: {m_show_type}\n" \
                      f"Kraje: {m_countries}\n\n" \
                      f"Link: {m_link}\n\n"

        # Make embedded message
        embed = construct_embedded_message(title=title, description=description, footer='(w - wróć)')

        # Set Embed's image
        embed.set_image(url=m_image_link)

    elif not user:
        description = "**Użytkownik nie istnieje.**\n\n"
        embed = construct_embedded_message(title=title, description=description, footer='(w - wróć)')
    else:
        description = "**Wprowadzono liczbę poza zakresem.**\n\n"
        embed = construct_embedded_message(title=title, description=description, footer='(w - wróć)')

    # Delete User message, Edit Bot message
    await user_message.delete()
    await bot_message.edit(embed=embed)


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


def simple_match_percentage(s1: str, s2: str) -> float:
    """Computes the simple comparison of s1 and s2"""
    assert min(len(s1), len(s2)) > 0, "One of the given string is empty"
    s1_split = s1.split(" ")
    result = [1 for x in s1_split if x in s2]
    return len(result) / len(s1_split)


def longest_common_substring(s1: str, s2: str) -> str:
    """Computes the longest common substring of s1 and s2"""
    seq_matcher = SequenceMatcher(isjunk=None, a=s1, b=s2)
    match = seq_matcher.find_longest_match(0, len(s1), 0, len(s2))

    if match.size:
        return s1[match.a: match.a + match.size]
    else:
        return ""


def longest_common_substring_percentage(s1: str, s2: str) -> float:
    """Computes the longest common substring percentage of s1 and s2"""
    assert min(len(s1), len(s2)) > 0, "One of the given string is empty"
    return len(longest_common_substring(s1, s2)) / min(len(s1), len(s2))


def levenshtein_distance_percentage(s1: str, s2: str) -> float:
    """
    Computes the Levenshtein distance.
    Used for misspelled or slightly changed strings.
    """

    assert min(len(s1), len(s2)) > 0, "One of the given string is empty"
    return 1. - distance(s1, s2) / max(len(s1), len(s2))


bot.run(TOKEN)
