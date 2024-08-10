import asyncio
from datetime import datetime
import discord
from discord import Message
from discord.ext import commands, tasks
from discord.ext.commands import Context
import os
from difflib import SequenceMatcher
from Levenshtein import distance
import collect_data
from dotenv import load_dotenv

from source.classes.enums import UserState
from source.classes.user import User

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
bot = discord.ext.commands.Bot(command_prefix=["m."], activity=activity, case_insensitive=True, intents=intents,
                               help_command=help_command)

# Constants
USERS_PATH = "data/users"
# Global Bot values
bot.g_locked = False
bot.g_users = collect_data.load_pkl(f'{USERS_PATH}/users.pkl', [])  # List of Users with Movies lists.
bot.g_sites = []  # List of Sites with Movies data


@bot.event
async def on_ready() -> None:
    print(f'Logged as: {bot.user}')

    # Start tasks
    update_site_data.start()
    save_user_data.start()


@tasks.loop(hours=12)
async def update_site_data() -> None:
    print("Collecting data...")
    data = await collect_data.collect_data()

    print("Loading data...")
    bot.g_locked = True  # bot controls blocked
    await asyncio.sleep(3)  # wait in case of handle state running
    bot.g_sites = data
    bot.g_locked = False
    print(f"Using sites: {', '.join(w.name for w in bot.g_sites)}")


@tasks.loop(seconds=120)
async def save_user_data() -> None:
    z1 = datetime.now()

    collect_data.save_pkl(bot.g_users, f'{USERS_PATH}/users.pkl')

    z2 = datetime.now()
    print("save_user_data(): " + str(z2 - z1))

bot.run(TOKEN)
