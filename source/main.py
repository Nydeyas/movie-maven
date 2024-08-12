import asyncio
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

import discord
from discord import Message
from discord.ext import commands, tasks
from discord.ext.commands import Context
import os
import collect_data
from dotenv import load_dotenv
import logging

from source.classes.enums import UserState
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
)

# Bot activity status
activity = discord.Activity(type=discord.ActivityType.listening, name="m.help")

# Bot
bot = discord.ext.commands.Bot(command_prefix=["m.", "M."], activity=activity, case_insensitive=True, intents=intents,
                               help_command=help_command)

# Constants
TEXT_CHANNELS = [1267279190206451752, 1267248186410406023]  # Discord channels IDs where the bot will operate
USERS_PATH = "data/users"
MAX_ROWS_SEARCH = 12  # max number of rows showed in movie search
MAX_ROWS_WATCHLIST = 20  # max number of rows showed in watchlist
MAX_FIELD_LENGTH = 1024  # max length of the embed fields (up to 1024 characters limited by Discord)
MIN_MATCH_SCORE = 40  # minimum score of similarity in the search(0-100)


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


@bot.command(aliases=['list', 'lista', 'w', 'wl', 'l'], brief='Lista filmów użytkownika',
             description='Wyświetla listę filmów użytkownika wraz z ocenami')
async def watchlist(ctx: Context) -> None:
    if ctx.channel.id in TEXT_CHANNELS and not bot.g_locked:
        if not is_user(ctx.author.id):
            # Add new User
            bot.g_users.append(User(ctx.author))
        await watchlist_panel(ctx.message)


@bot.event
async def on_message(message: Message) -> None:
    if (
            not bot.g_locked
            and message.channel.id in TEXT_CHANNELS
            and is_user(message.author.id)
            and not message.content.startswith(tuple(bot.command_prefix))
    ):
        # Ignore bot's own messages
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
                    await handler(message, fetched_message)
                except discord.HTTPException as err:
                    logging.warning(f"[main.py]: Error fetching message ({message.channel}): {err}")
                    user.state = UserState.idle
            else:
                logging.warning(f"[main.py]: Unknown UserState: {state}")

    await bot.process_commands(message)


async def search_panel(user_message: Message) -> None:
    """Main panel of search engine"""
    ctx = await bot.get_context(user_message)
    user = get_user(ctx.author.id)
    result_movies = []
    i = 1

    title = f"Wyszukiwarka filmów ({user.display_name})"
    description = "**Info:**\nWpisz na czacie tytuł filmu do wyszukania lub numer z poniższej listy.\n" \
                  "Możesz także zastosować odpowiednie filtry za pomocą reakcji.\n\n**Ostatnio dodane**:\n\n"
    field_title = ''
    field_year_tags = ''
    field_rating = ''

    for site in list(bot.g_sites):
        site_name = f"**{str(site).upper()}:**\n"
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

        # Make list of last added movies
        site_movies = site.get_movies_sorted_by_date_added(max_items=MAX_ROWS_SEARCH, reverse=True)
        result_movies.extend(site_movies)

        for movie in site_movies:
            # Split removes alternative titles
            column_title = f"{i}\. {movie.title.split('/')[0]}"
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

    if not result_movies:
        description = "Brak filmów w bazie."
        embed = construct_embedded_message(title=title, description=description)
        # Send embedded message
        await user_message.channel.send(embed=embed)
        return

    # Send embedded message
    embed = construct_embedded_message(field_title, field_year_tags, field_rating,  title=title,
                                       description=description)
    msg = await user_message.channel.send(embed=embed)

    # Update User
    user.message_id = msg.id
    user.state = UserState.search_panel
    user.search_content = result_movies


async def search_result(user_message: Message, bot_message: Message) -> None:
    """Search result panel shown (List of movies)"""
    user = get_user(user_message.author.id)
    user_input = user_message.content
    result_movies = []
    i = 1

    title = f"Wyszukiwarka filmów ({user.display_name})"
    description = "**Znalezione wyniki:**\n\n"
    field_title = ''
    field_year_tags = ''
    field_rating = ''

    for site in list(bot.g_sites):
        site_name = f"**{str(site).upper()}:**\n"
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

        site_movies = site.search_movies(phrase=user_input, max_items=MAX_ROWS_SEARCH, min_match_score=MIN_MATCH_SCORE)
        result_movies.extend(site_movies)

        for movie in site_movies:
            # Split removes alternative titles
            column_title = f"{i}\. {movie.title.split('/')[0]}"
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

    if not result_movies:
        description = "Nie znaleziono pasujących wyników."
        embed = construct_embedded_message(title=title, description=description)
        await user_message.delete()
        await bot_message.edit(embed=embed)
        return

    # Send embedded message
    embed = construct_embedded_message(field_title, field_year_tags, field_rating, title=title,
                                       description=description)
    # Update User
    user.search_content = result_movies

    # Delete User message, Edit Bot message
    await user_message.delete()
    await bot_message.edit(embed=embed)


async def movie_details(user_message: Message, bot_message: Message) -> None:
    """Individual movie panel"""
    user = get_user(user_message.author.id)

    if not user:
        title = "Wyszukiwarka filmów (Brak użytkownika)"
        description = "**Użytkownik nie istnieje.**\n\n"
        embed = construct_embedded_message(title=title, description=description, footer='(w - wróć)')
        await user_message.delete()
        await bot_message.edit(embed=embed)
        return

    title = f"Wyszukiwarka filmów ({user.display_name})"
    input_int = int(user_message.content)

    if input_int not in range(1, len(user.search_content) + 1):
        description = "**Wprowadzono liczbę poza zakresem.**\n\n"
        embed = construct_embedded_message(title=title, description=description, footer='(w - wróć)')
        await user_message.delete()
        await bot_message.edit(embed=embed)
        return

    selected_movie = user.search_content[input_int - 1]

    description = (
        f"**{selected_movie.year}r\u2004|\u2004{selected_movie.length}min\u2004|\u2004{selected_movie.tags}**\n\n"
        f"{selected_movie.description}\n\n"
        f"**Ocena: {selected_movie.rating}/10**\n"
        f"{selected_movie.votes} głosów\n\n"
        f"Format: {selected_movie.show_type}\n"
        f"Kraje: {selected_movie.countries}\n\n"
        f"Link: {selected_movie.link}\n\n"
    )

    # Make embedded message
    embed = construct_embedded_message(title=selected_movie.title, description=description, footer='(w - wróć)')

    # Set Embed's image
    embed.set_image(url=selected_movie.image_link)

    # Delete User message, Edit Bot message
    await user_message.delete()
    await bot_message.edit(embed=embed)


async def watchlist_panel(user_message: Message) -> None:
    """Main panel of search engine"""
    ctx = await bot.get_context(user_message)
    user = get_user(ctx.author.id)
    title = f"Lista filmów użytkownika {user.display_name}"
    entries = user.watchlist.get_entries_sorted_by_title()

    if not entries:
        description = "**Twoja lista jest pusta.**\n" \
                      "Skorzystaj z komendy **m.szukaj**, aby wyszukać i dodać wybrane przez siebie filmy."
        embed = construct_embedded_message(title=title, description=description)
        # Send embedded message
        await user_message.channel.send(embed=embed)
        return

    # Make description
    field_title = 'Tytuł\n'
    field_date = 'Data dodania\n'
    field_rating = 'Ocena\n'
    for i, entry in enumerate(entries):
        e_title = entry.movie.title
        e_date = entry.date_added
        e_rating = entry.rating

        # Split removes alternative titles
        column_title = f"{i + 1}\. {e_title}"
        column_date = f"{e_date}"
        column_rating = f"{e_rating}"

        # Limit Row Width
        if len(column_title) >= 53:
            column_title = column_title[:50] + "..."

        # Check field length limit
        if (len(field_title) + len(column_title) + 1 > MAX_FIELD_LENGTH or
                len(field_date) + len(column_date) + 1 > MAX_FIELD_LENGTH or
                len(field_rating) + len(column_rating) + 1 > MAX_FIELD_LENGTH):
            break

        field_title += column_title + "\n"
        field_date += column_date + "\n"
        field_rating += column_rating + "\n"

    description = ""
    embed = construct_embedded_message(field_title, field_date, field_rating,  title=title,
                                       description=description)

    # Send embedded message
    msg = await user_message.channel.send(embed=embed)

    # Update User
    user.message_id = msg.id
    user.state = UserState.watchlist_panel
    user.search_content = [e.movie for e in entries]


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


bot.run(TOKEN)
