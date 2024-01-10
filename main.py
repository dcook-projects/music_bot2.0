import discord
from discord.ext import commands
import music
import config
import asyncio
import logging

cogs = [music]
client = commands.Bot(command_prefix="$", intents=discord.Intents.all(), case_insensitive=True)


async def main():
    async with client:
        client.loop.create_task(music.setup(client))
        await client.start(config.BOT_TOKEN)

asyncio.run(main())