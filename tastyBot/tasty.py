import asyncio
import logging
from typing import cast

import discord
from discord.ext import commands

import wavelink


class Bot(commands.Bot):
    cleanupId = 0
    def __init__(self) -> None:
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True

        discord.utils.setup_logging(level=logging.INFO)
        super().__init__(command_prefix=".", intents=intents)

    async def setup_hook(self) -> None:
        nodes = [wavelink.Node(uri="http://localhost:2333", password="password")]

        # cache_capacity is EXPERIMENTAL. Turn it off by passing None
        await wavelink.Pool.connect(nodes=nodes, client=self, cache_capacity=None)

    async def on_ready(self) -> None:
        logging.info(f"Logged in: {self.user} | {self.user.id}")

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        logging.info(f"Wavelink Node connected: {payload.node!r} | Resumed: {payload.resumed}")

    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player: wavelink.Player | None = payload.player
        if not player:
            # Handle edge cases...
            return

        original: wavelink.Playable | None = payload.original
        track: wavelink.Playable = payload.track

        embed: discord.Embed = discord.Embed(color=13048441)
        embed.add_field(name="Now playing", value=f"{track.title}", inline=False)

        # embed: discord.Embed = discord.Embed(title="Now Playing")
        # embed.description = f"**{track.title}** by `{track.author}`"

        # if track.artwork:
        #     embed.set_image(url=track.artwork)

        # if original and original.recommended:
        #     embed.description += f"\n\n`This track was recommended via {track.source}`"

        # if track.album.name:
        #     embed.add_field(name="Album", value=track.album.name)
        if bot.cleanupId>0:
            try: 
                msg = await player.home.fetch_message(bot.cleanupId)
                await msg.delete() 
            except Exception as e: 
                print(f"error in clanup: {e}")

        msg = await player.home.send(embed=embed) #, view=skipBtn(ctx) but what is ctxx here?
        bot.cleanupId = msg.id


bot: Bot = Bot()

class skipBtn(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__()
        self.ctx = ctx
    @discord.ui.button(emoji="⏩")
    async def onClick(self, interaction: discord.Interaction, button: discord.ui.Button):
        await skip(self.ctx, 1)
        await interaction.response.defer()

class nextBtn(discord.ui.View):
    def __init__(self, text, ctx: commands.Context):
        super().__init__()
        self.text = text
        self.ctx = ctx
    @discord.ui.button(emoji="◀️")
    async def prevClick(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client:
            embed = interaction.message.embeds[0]
            name = embed.fields[0].name
            dividend = int(name.split(" ")[1].split("/")[0])
            divider = int(name.split(" ")[1].split("/")[1])
            if dividend - 1 >= 1:    
                newEmbed = discord.Embed(color=13048441)
                newEmbed.add_field(name=f"Queue {dividend-1}/{divider}",value=self.text[dividend-2], inline=False) #-2 cause 1/2 is actually 0/1
                await interaction.message.edit(embed=newEmbed,view=nextBtn(self.text, self.ctx)) #discord.ui.View.from_message(interaction.message)
        await interaction.response.defer()

    @discord.ui.button(emoji="▶️")
    async def nextClick(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client:
            embed = interaction.message.embeds[0]
            name = embed.fields[0].name
            dividend = int(name.split(" ")[1].split("/")[0])
            divider = int(name.split(" ")[1].split("/")[1])
            if dividend + 1 <= divider:    
                newEmbed = discord.Embed(color=13048441)
                newEmbed.add_field(name=f"Queue {dividend+1}/{divider}",value=self.text[dividend], inline=False)
                await interaction.message.edit(embed=newEmbed, view=nextBtn(self.text, self.ctx))
        await interaction.response.defer()

@bot.command(aliases=['p'], brief='add song to queue')
async def play(ctx: commands.Context, *, query: str = commands.parameter(description="song name | youtube url | spotify url")) -> None:
    """Play a song with the given query."""
    if not ctx.guild:
        return

    player: wavelink.Player
    player = cast(wavelink.Player, ctx.voice_client)  # type: ignore

    if not player:
        try:
            player = await ctx.author.voice.channel.connect(cls=wavelink.Player)  # type: ignore
        except AttributeError:
            await ctx.send("Please join a voice channel first before using this command.")
            return
        except discord.ClientException:
            await ctx.send("I was unable to join this voice channel. Please try again.")
            return

    # Turn on AutoPlay to enabled mode.
    # enabled = AutoPlay will play songs for us and fetch recommendations...
    # partial = AutoPlay will play songs for us, but WILL NOT fetch recommendations...
    # disabled = AutoPlay will do nothing...
    player.autoplay = wavelink.AutoPlayMode.partial #I disabled it

    # Lock the player to this channel...
    if not hasattr(player, "home"):
        player.home = ctx.channel
    elif player.home != ctx.channel:
        await ctx.send(f"You can only play songs in {player.home.mention}, as the player has already started there.")
        return

    # This will handle fetching Tracks and Playlists...
    # Seed the doc strings for more information on this method...
    # If spotify is enabled via LavaSrc, this will automatically fetch Spotify tracks if you pass a URL...
    # Defaults to YouTube for non URL based queries...
    tracks: wavelink.Search = await wavelink.Playable.search(query)
    if not tracks:
        await ctx.send(f"{ctx.author.mention} - Could not find any tracks with that query. Please try again.")
        return
    embed=discord.Embed(color=13048441)
    if isinstance(tracks, wavelink.Playlist):
        # tracks is a playlist...

        added: int = await player.queue.put_wait(tracks)
        embed.add_field(name=f"{added} tracks added to q", value=f"from playlist ", inline=False)
        await ctx.send(embed=embed)
    else:
        track: wavelink.Playable = tracks[0]
        await player.queue.put_wait(track)
        embed.add_field(name=f"Track added to q: position {player.queue.count}", value=f"{track.title}")
        await ctx.send(embed=embed)

    if not player.playing:
        # Play now since we aren't playing anything...
        await player.play(player.queue.get(), volume=30)

    # Optionally delete the invokers message...
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass


@bot.command(aliases=['s'], brief='skip one or n songs in queue')
async def skip(ctx: commands.Context, n = commands.parameter(default=0, description="number of songs")) -> None:
    """Skip the current song."""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
    if not player:
        return
    ##added
    while(n>1):
        if player.queue.count>0:
            player.queue.get()
        n-=1
    ##
    await player.skip(force=True)

@bot.command()
async def volume(ctx: commands.Context, value: int) -> None:
    """Change the volume of the player."""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
    if not player:
        return

    await player.set_volume(value)
    await ctx.message.add_reaction("\u2705")


@bot.command(aliases=["dc"], brief='clear the queue, stop the music payer')
async def leave(ctx: commands.Context) -> None:
    """Disconnect the Player."""
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
    if not player:
        return
    if bot.cleanupId>0:
        try: 
            msg = await player.channel.fetch_message(bot.cleanupId) #no ctx
            await msg.edit(embed=msg.embeds[0],view=None)
        except Exception as e: 
            print(f"error in clean when leave: {e}")
    await player.disconnect()

@bot.command(aliases=['l'], brief='shows the queue')
async def list(ctx: commands.Context):
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
    if not player:
        return
    embed=discord.Embed(color=13048441)
    if player.queue.is_empty:
        embed.add_field(name="Queue",value="is empty")
        await ctx.send(embed=embed)
    else:
        queue = player.queue.copy()
        part = 0
        count = 0
        text = ["`"]
        for track in queue:
            count +=1
            trackMin = int(track.length//60)
            trackSec = "0"+str(int(track.length%60)) if int(track.length%60) < 10 else int(track.length%60)
            if len(text[part] + f"{count}. {track.title} [{trackMin}:{trackSec}]\n") > 1000:
                text[part] += "`"
                part+=1
                text.append("`")
            text[part] += f"{count}. {track.title} [{trackMin}:{trackSec}]\n"
        text[part]+="`"

        embed.add_field(name=f"Queue 1/{part+1}",value=text[0], inline=False) #iyviviobkoinobu
        await ctx.send(embed=embed, view=nextBtn(text, ctx))

@bot.command(brief='skip to the part of the song')
#async def seek(ctx: commands.Context, time: str ): #expand to 1:10:10?
async def seek(ctx: commands.Context, time: str = commands.parameter(description="in {mm:ss} format")):
    player: wavelink.Player = cast(wavelink.Player, ctx.voice_client)
    if not player:
        return
    minutes = int(time[:time.find(':')])
    seconds = int(time[time.find(':')+1:])
    msec = (minutes*60 + seconds)*1000
    if player.is_playing():
        await player.seek(msec)

@bot.tree.context_menu(name="play")
async def sus(interaction: discord.Interaction, message: discord.Message):
    id = message.content.find('.p ')+len('.p ') if message.content.find('.p ') >= 0 else 0
    ctx = await commands.Context.from_interaction(interaction)
    await play(ctx,query=message.content[id:])
    #await interaction.response.defer()
    #print(message.content[id:])

@bot.tree.context_menu(name="go voice")
async def voice(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(f"{member.mention} go voice")

@bot.command(hidden=True)
async def upd(self):
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"error in upd: {e}")


async def main() -> None:
    async with bot:
        await bot.start('TOKEN')


asyncio.run(main())
