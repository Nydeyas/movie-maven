import asyncio
from typing import List

import discord
from discord import Message
from discord.ext import commands, tasks
from discord.ext.commands import Context
import os
from difflib import SequenceMatcher
from Levenshtein import distance
from collect_data import collect_data
from dotenv import load_dotenv

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
@bot.event
async def on_ready() -> None:
    print(f'Logged as: {bot.user}')
    await update_data()
    print("g_data size: ", len(bot.g_data))


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


bot.run(TOKEN)
