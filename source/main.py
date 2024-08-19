import asyncio
import time
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

from source.classes.enums import UserState
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
)

# Bot activity status
activity = discord.Activity(type=discord.ActivityType.listening, name="m.help")

# Bot
bot = discord.ext.commands.Bot(command_prefix=["m.", "M."], activity=activity, case_insensitive=True, intents=intents,
                               help_command=help_command)

# Constants
TEXT_CHANNELS = [1267279190206451752, 1267248186410406023]  # Discord channels IDs where the bot will operate
USERS_PATH = "data/users"
MAX_ROWS_SEARCH = 12  # Max number of rows showed in movie search
MAX_ROWS_WATCHLIST = 20  # Max number of rows showed in watchlist
MAX_FIELD_LENGTH = 1024  # Max length of the embed fields (up to 1024 characters limited by Discord)
MIN_MATCH_SCORE = 40  # Minimum score of similarity in the search(0-100)
REACTION_TIMEOUT = 600.0  # Time in seconds for bot to track reactions

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

    users_copy = [user.copy_without_task() for user in bot.g_users]
    collect_data.save_pkl(users_copy, f'{USERS_PATH}/users.pkl')

    z2 = datetime.now()
    logging.info("save_user_data(): " + str(z2 - z1))


@bot.command(aliases=['szukaj', 's', 'filmy', 'films', 'movies'], brief='Wyszukiwanie filmów',
             description='Wyszukuje tytuł filmu na podstawie wpisanej frazy')
async def search(ctx: Context) -> None:
    if ctx.channel.id in TEXT_CHANNELS and not bot.g_locked:
        if not is_user(ctx.author.id):
            # Add new User
            bot.g_users.append(User(ctx.author.id, ctx.author.name, ctx.author.display_name))
        await search_panel(ctx.message)


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
    await handle_user_input(message, user)
    await execute_state_handler(message, user)

    await bot.process_commands(message)


async def handle_user_input(message: Message, user) -> None:
    """Handles user input based on the user's current state."""
    old_state = user.state
    blacklist = [UserState.idle, UserState.rate_movie]

    if old_state in blacklist:
        logging.debug(f"Input: '{message.content}', Old State: '{old_state}' (blacklisted for user input)")
        return

    if message.content.isdecimal():  # Numeric
        user.state = UserState.movie_details
    else:  # Not numeric
        if old_state != UserState.watchlist_panel:
            user.state = UserState.search_result
    logging.debug(f"Input: '{message.content}', Old State: '{old_state}', New state: '{user.state}'")


async def execute_state_handler(message: Message, user) -> None:
    """Executes the function corresponding to the user's current state."""
    state_functions = {
        UserState.search_panel: search_panel,
        UserState.search_result: search_result,
        UserState.movie_details: movie_details,
    }
    blacklist = [UserState.idle, UserState.rate_movie, UserState.watchlist_panel]
    state = user.state

    if state in blacklist:
        logging.debug(f"No handler was executed ('{state}' is blacklisted for handler )")
        return

    handler = state_functions.get(state)
    if not handler:
        logging.warning(f"Unknown UserState: {state}")
        return

    try:
        fetched_message = await message.channel.fetch_message(user.message_id)
        logging.debug(f"Running handler: {handler.__name__}, Channel: '{str(message.channel)}'")
        await handler(message, fetched_message)
    except discord.HTTPException as err:
        logging.warning(f"Error fetching message ({message.channel}): {err}")
        user.state = UserState.idle


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
    embed = construct_embedded_message(field_title, field_year_tags, field_rating, title=title,
                                       description=description)
    msg = await user_message.channel.send(embed=embed)

    # Update User
    user.message_id = msg.id
    user.state = UserState.search_panel
    user.movie_selection_list = result_movies


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
    user.movie_selection_list = result_movies

    # Delete User message, Edit Bot message
    await user_message.delete()
    await bot_message.edit(embed=embed)


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

    selected_movie = user.movie_selection_list[input_int - 1]

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
    embed = construct_embedded_message(title=selected_movie.title, description=description)
    embed.set_image(url=selected_movie.image_link)

    # Prepare reaction emojis
    if user.watchlist.has_movie(selected_movie):
        emoji_to_text = {remove_from_watchlist_emoji: "Usuń z listy filmów", rate_movie_emoji: "Oceń film"}
    else:
        emoji_to_text = {add_to_watchlist_emoji: "Zapisz na liście filmów"}

    # Set footer, Delete User message, Edit Bot message
    footer_text = make_footer(emoji_to_text)
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
            await rate_movie(user_message, bot_message)
            time.sleep(2)
            user.state = UserState.movie_details
        # Update message
        footer_text = make_footer(emoji_to_text)
        embed.set_footer(text=footer_text)
        await msg.edit(embed=embed)


async def rate_movie(user_message: Message, bot_message: Optional[Message] = None) -> None:
    # Prompt user to enter rating
    user = get_user(user_message.author.id)
    user.state = UserState.rate_movie
    input_int = int(user_message.content)
    selected_movie = user.movie_selection_list[input_int - 1]

    await bot_message.clear_reactions()
    rating_prompt = "Wybierz ocenę filmu (1-10):"
    rating_embed = construct_embedded_message(title="Oceń Film", description=rating_prompt)
    await bot_message.edit(embed=rating_embed)

    # Wait for user to enter a rating
    response = await get_user_text(
        user,
        REACTION_TIMEOUT,
        check=(
            lambda m: m.author == user_message.author
            and m.content.replace('.', '', 1).isdigit()
            and 1 <= float(m.content) <= 10
            and m.channel.id == bot_message.channel.id
        )
    )
    if response is None:
        timeout_description = "Czas na ocenę filmu upłynął."
        rating_embed = construct_embedded_message(title="Oceń Film", description=timeout_description)
        await bot_message.edit(embed=rating_embed)
        return

    # Update rating
    new_rating = int(response.content) if response.content.isdigit() else round(float(response.content), 1)
    user.watchlist.update_rating(selected_movie, new_rating)

    # Confirm rating update
    confirm_description = f"Film został oceniony na {new_rating}/10."
    rating_embed = construct_embedded_message(title="Oceniono Film", description=confirm_description)
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
    user = get_user(ctx.author.id)
    title = f"Lista filmów ({user.display_name})"

    entries = user.watchlist.get_entries_sorted_by_title()  # Default sort by title
    entries_count = len(entries)

    if not entries:
        description = "**Twoja lista jest pusta.**\n" \
                      "Skorzystaj z komendy **m.szukaj**, aby wyszukać i dodać wybrane przez siebie filmy."
        embed = construct_embedded_message(title=title, description=description, colour=0xdfc118)
        # Send embedded message
        await user_message.channel.send(embed=embed)
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
            sorting_info = f"**Sortowanie: {sort_criteria[sort_key]} ({order})**"
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
        footer = make_footer(emoji_to_text)
        embed.set_footer(text=footer)

        if msg is None:  # If it's the first time, send a new message
            msg = await user_message.channel.send(embed=embed)
            user.state = UserState.watchlist_panel
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
                footer = make_footer(emoji_to_text)
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
    # Update reactions
    if controller or not emojis:
        try:
            if message.channel.type != discord.ChannelType.private:
                await message.clear_reactions()
            for e in emojis:
                await message.add_reaction(e)
        except discord.NotFound as e:  # Message not found
            logging.warning(f"Failed to add reactions. Message not found: {e}. Message ID might be invalid or deleted.")

    # CONDITIONS CHECK (1.user, 2.message, 3.emoji)
    def check_default(payload: discord.RawReactionActionEvent):
        user_id, msg_id, emoji = payload.user_id, payload.message_id, str(payload.emoji)
        id_list = [p.id for p in bot.g_users]
        return (
                (user_id == controller.id if controller else user_id in id_list)  # 1
                and (msg_id == message.id)  # 2
                and (emoji in emojis)  # 3
        )

    # Create and update user task
    new_task = asyncio.create_task(bot.wait_for(
            "raw_reaction_add",
            timeout=timeout,
            check=check if check is not None else check_default
        )
    )
    if controller:
        old_task = controller.interaction_task
        if old_task and not old_task.done():
            logging.debug(f"Cancelling task: name={old_task.get_name()}")
            old_task.cancel()
        controller.interaction_task = new_task

    # Wait for the reaction
    try:
        reaction_payload = await new_task
    except asyncio.TimeoutError as e:
        logging.debug(f"Wait for reaction timeout: {e}")
        return None
    return reaction_payload


async def get_user_text(
        controller: Optional[User] = None,
        timeout: Optional[float] = None,
        check: Callable[[discord.MessageInteraction], bool] | None = None
) -> Optional[discord.Message]:

    # CONDITIONS CHECK (1.user, 2.message)
    def check_default(message: discord.Message):
        user_id = message.author.id
        id_list = [p.id for p in bot.g_users]
        return(user_id == controller.id if controller else user_id in id_list) and (message.channel.id in TEXT_CHANNELS)

    # Create and update user task
    new_task = asyncio.create_task(bot.wait_for(
            'message',
            timeout=timeout,
            check=check if check is not None else check_default
        )
    )
    if controller:
        old_task = controller.interaction_task
        if old_task and not old_task.done():
            logging.debug(f"Cancelling task: name={old_task.get_name()}")
            old_task.cancel()
        controller.interaction_task = new_task

    # Wait for the text
    try:
        message_payload = await new_task
    except asyncio.TimeoutError:
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


def make_footer(emoji_mapping: Dict[str, str]) -> str:
    """Creates a footer string from emoji-to-text mapping."""
    footer_parts = [f"{emoji} {text}" for emoji, text in emoji_mapping.items()]
    return " | ".join(footer_parts)


bot.run(TOKEN)
