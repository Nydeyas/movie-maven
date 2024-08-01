import asyncio
from typing import List

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

# Set bot activity status
activity = discord.Activity(type=discord.ActivityType.listening, name="m.help")

# Bot
bot = discord.ext.commands.Bot(command_prefix=["m."], activity=activity, case_insensitive=True, intents=intents,
                               help_command=help_command)
bot.g_websites = {}  # List of Website objects with data
# Constants
USERS_PATH = "data/users"
# Global Bot values
bot.g_users = collect_data.load_pkl(f'{USERS_PATH}/users.pkl', [])  # List of Users with Movies lists.
@bot.event
async def on_ready() -> None:
    print(f'Logged as: {bot.user}')
    await update_data()
    print("g_data size: ", len(bot.g_data))
    # Start tasks
    save_user_data.start()


@tasks.loop(minutes=120)
async def update_data() -> None:
    print("Collecting data...")
    data = await collect_data.collect_data()

    print("Loading data...")
    bot.g_state = 0  # bot controls blocked
    await asyncio.sleep(5)  # wait in case of handle state running
    bot.g_websites = data
    bot.g_state = 1
    print(f"Using websites: {', '.join(w.name for w in bot.g_websites)}")


@tasks.loop(seconds=120)
async def save_user_data() -> None:
    z1 = datetime.now()

    collect_data.save_pkl(bot.g_users, f'{USERS_PATH}/users.pkl')

    z2 = datetime.now()
    print("save_user_data(): " + str(z2 - z1))

bot.run(TOKEN)
