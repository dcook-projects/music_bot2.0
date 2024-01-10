import discord
from discord.ext import commands
import youtube_dl
import pafy
import asyncio


def check_if_bot_author(ctx):
    return ctx.message.author.id == 149795176741601280


class Music(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.song_queue = {}
        self.setup()

    def setup(self):
        for guild in self.client.guilds:
            self.song_queue[guild.id] = []

    async def check_queue(self, ctx):
        if ctx.voice_client is not None:  # this can be None if the client disconnects in the middle of a song
            success = False
            ctx.voice_client.stop()  # Without this, if the queue empties out after having songs in it, adding a song to the empty queue will put it into the queue instead of playing it
            while len(self.song_queue[
                          ctx.guild.id]) > 0 and not success:  # checks if there is a song in the queue and the previous attempt to play a song failed
                success = await self.play_song(ctx,
                                               self.song_queue[ctx.guild.id][0])  # plays the next song in the queue
                self.song_queue[ctx.guild.id].pop(0)  # pop the next song from the list

    async def search_song(self, amount, song, get_url=False):
        YDL_OPTIONS = {"format": "bestaudio",
                       "quiet": True
                       }

        # info contains the results of the search
        info = await self.client.loop.run_in_executor(None, lambda: youtube_dl.YoutubeDL(YDL_OPTIONS).extract_info(
            f"ytsearch{amount}:{song}",
            download=False))  # run_in_executor unblocks the function be because waiting for data from youtube blocks
        if len(info["entries"]) == 0:
            return None
        else:
            return [entry["webpage_url"] for entry in info["entries"]] if get_url else info

    # Returns true if the song was found and can be played, or false if there was an error
    async def play_song(self, ctx,
                        song):  # song is the url of the youtube video, not the one we actually want to use to download something
        FFMPEG_OPTIONS = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                          "options": "-vn"}

        try:
            # url contains the actual URL we want to use to download something
            url = pafy.new(song).getbestaudio().url
            source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
            ctx.voice_client.play(source, after=lambda error: self.client.loop.create_task(self.check_queue(ctx)))
            return True
        except OSError as e:
            await ctx.send("There was an error playing the current song. Skipping")
            return False
        except discord.errors.DiscordException as e:
            print(e)
            return False
        except discord.ext.commands.errors.CommandInvokeError as e:
            print(e)
            return False
        except Exception as ee:
            print("General Error")
            print(ee)
            return False

    """---------------------------------LISTENERS---------------------------------------------------"""

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        INACTIVITY_TIME_LIMIT = 900
        if not member.id == self.client.user.id:
            return
        elif before.channel is None:
            voice = after.channel.guild.voice_client
            time = 0
            while True:
                await asyncio.sleep(1)
                time = time + 1
                if voice.is_playing() and not voice.is_paused():
                    time = 0
                if time == INACTIVITY_TIME_LIMIT:
                    await voice.disconnect()
                if not voice.is_connected():
                    break

    """--------------------------------COMMANDS-----------------------------------------------------"""

    @commands.command(help="causes the bot to join the channel you are currently in")
    async def join(self, ctx):
        if ctx.author.voice is None:
            return await ctx.send("You are not in a voice Channel!")

        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)

    @commands.command(help="Bot author command only. Disconnects the bot from the voice channel")
    @commands.check(check_if_bot_author)
    async def disconnect(self, ctx):
        if ctx.voice_client is None:
            return

        if ctx.voice_client is not None:
            self.song_queue[ctx.guild.id] = []
            await ctx.voice_client.disconnect()

    @commands.command(help="Pauses the audio. type !resume to pick up where the audio left off.")
    async def pause(self, ctx):
        if ctx.voice_client is None:
            return

        if ctx.author.voice is None or ctx.author.voice.channel.id != ctx.voice_client.channel.id:
            return

        if ctx.voice_client is not None:
            ctx.voice_client.pause()
            await ctx.send("Paused ⏸️")

    @commands.command(help="Resumes audio at the spot left off by the previous !pause command")
    async def resume(self, ctx):
        if ctx.voice_client is None:
            return

        if ctx.author.voice is None or ctx.author.voice.channel.id != ctx.voice_client.channel.id:
            return

        if ctx.voice_client is not None:
            ctx.voice_client.resume()
            await ctx.send("Resume ▶️")

    @commands.command(name="p",
                      help="plays the audio of the youtube video at the given URL, or searches youtube if the video isn't a link")
    async def play(self, ctx, *, song=None):
        MAX_QUEUE_LENGTH = 15  # set the maximum queue length to 15, to avoid someone spamming it
        if song is None:
            return await ctx.send("You must include a song to play")

        if ctx.voice_client is None:
            return await ctx.send("I must be in a voice channel to play a song")

        if ctx.author.voice is None or ctx.author.voice.channel.id != ctx.voice_client.channel.id:
            return

        # handle song when song isn't a url
        if not ("youtube.com/watch" in song or "https://youtu.be" in song):
            result = await self.search_song(1, song, get_url=True)
            print("Result:")
            print(result)
            if result is None:
                return await ctx.send("Sorry, I could not find the given song.")

            song = result[0]

        if ctx.voice_client.source is not None:  # if the client is playing, add it to the queue
            length = len(self.song_queue[ctx.guild.id])

            if length < MAX_QUEUE_LENGTH:
                self.song_queue[ctx.guild.id].append(song)
                return await ctx.send(f"{song} added to the queue at position {length + 1}")
            else:
                return await ctx.send("Queue is full, please wait to add more songs")

        await self.play_song(ctx, song)
        await ctx.send(f"Now playing: {song}")

    @commands.command(help="Displays the songs currently in the queue")
    async def queue(self, ctx):
        if len(self.song_queue[ctx.guild.id]) == 0:
            return await ctx.send("There are currently no songs in the queue.")

        embed = discord.Embed(title="Song Queue", description="", color=discord.Color.dark_gold())
        i = 1
        for url in self.song_queue[ctx.guild.id]:
            embed.description += f"{i}) {url}\n"
            i += 1

        embed.set_footer(text="End of song queue.")
        await ctx.send(embed=embed)

    @commands.command(
        help="Starts a vote to skip the current song. Users in the voice channel have 15 seconds to cast their vote."
             "The song will be skipped if at least 70% of the votes are in favor of skipping.")
    async def skip(self, ctx):
        if ctx.voice_client is None:
            return await ctx.send("I am not playing a song.")

        if ctx.author.voice is None:
            return await ctx.send("You are not connected to a voice channel.")

        if ctx.author.voice.channel.id != ctx.voice_client.channel.id:
            return await ctx.send("I am not playing any songs for you.")

        poll = discord.Embed(title=f"Vote to skip song by - {ctx.author.name}",
                             description="**70% of the voice channel must vote to skip for it to pass.**",
                             color=discord.Color.blue())

        poll.add_field(name="Skip", value=":white_check_mark:")
        poll.add_field(name="Stay", value=":no_entry_sign:")
        poll.set_footer(text="Voting ends in 15 seconds.")

        poll_msg = await ctx.send(
            embed=poll)  # only returns temporary message, we need to get the cached message to get the reactions
        poll_id = poll_msg.id  # This should be unnecessary, but is make poll_msg work

        await poll_msg.add_reaction(u"\u2705")  # vote yes
        await poll_msg.add_reaction(u"\U0001F6AB")  # vote no
        await asyncio.sleep(15)  # give 15 seconds to vote

        poll_msg = await ctx.channel.fetch_message(poll_id)  # get the poll results
        votes = {u"\u2705": 0, u"\U0001F6AB": 0}  # contains the reactions we want to count
        reacted = []  # list of users who have had their vote counted

        for reaction in poll_msg.reactions:  # go through the reactions
            if reaction.emoji in [u"\u2705", u"\U0001F6AB"]:  # if the reaction is one we care about
                async for user in reaction.users():  # go through the users that reacted
                    # make sure the user that reacted is in the voice channel, hasn't already had their vote counted, and isn't the bot
                    if user.voice.channel.id == ctx.voice_client.channel.id and user.id not in reacted and not user.bot:
                        votes[reaction.emoji] += 1
                        reacted.append(user.id)

        skip_song = False
        if votes[u"\u2705"] > 0:  # if at least one yes vote
            if votes[u"\U0001F6AB"] == 0 or votes[u"\u2705"] / (votes[u"\u2705"] + votes[u"\U0001F6AB"]) > 0.69:  # if there were no "No" votes or at least 70% "yes" votes
                print("Yes: {}\tNo: {}".format(votes[u"\u2705"], votes[u"\U0001F6AB"]))
                skip_song = True
                embed = discord.Embed(title="Skip Successful",
                                      description="***Voting to skip the current song was successful, skipping now.***",
                                      color=discord.Color.green())

        if not skip_song:
            embed = discord.Embed(title="Skip Failed",
                                  description="*Voting to skip the current song has failed.*\n\n***Voting failed, the vote requires at least 70% of the members to skip.***",
                                  colour=discord.Colour.red())

        embed.set_footer(text="Voting has ended.")

        await poll_msg.clear_reactions()  # clear the poll
        await poll_msg.edit(embed=embed)

        if skip_song:
            ctx.voice_client.stop()  # get the next song in the queue


async def setup(client):
    await client.wait_until_ready()
    await client.add_cog(Music(client))
