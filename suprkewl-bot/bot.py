# -*- coding: utf-8 -*-

"""
The MIT License (MIT)
Copyright (c) 2018-2019 laggycomputer
Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

import asyncio
import platform
import random
import traceback

import aiohttp
import aiosqlite
import discord
from discord.ext import commands
from ext.utils import apiToHuman, plural

import config
import redis


class theBot(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.redis = None
        self.http2 = None

        self.bg_task = self.loop.create_task(self.playingstatus())

        startup_extensions = [
            "jishaku", "ext.text", "ext.rand", "ext.docs", "ext.mod", "ext.info", "ext.help", "ext.config", "ext.admin"
        ]

        for extension in startup_extensions:
            try:
                self.load_extension(extension)
                print(f"Loaded cog {extension}.")
            except Exception as e:
                exc = f"{e.__name__}: {e}"
                print(f"Failed to load extension {extension}\n{exc}")

    async def on_ready(self):
        if not self.redis:
            self.redis = redis.Redis()
            await self.redis.connect()
        if not self.http2:
            self.http2 = aiohttp.ClientSession()

        print(f"Logged in as {self.user.name} (UID {self.user.id}) | Connected to {len(self.guilds)} servers and their combined {len(set(self.get_all_members()))} members")
        print("-" * 8)
        print(f"Current discord.py version: {discord.__version__} | Current Python version: {platform.python_version()}")
        print("-" * 8)
        print(f"Use this link to invite this bot:")
        print(f"https://discordapp.com/oauth2/authorize?client_id={self.user.id}&scope=bot&permissions=8")
        print("-" * 8)

    async def on_message(self, message):
        if not self.is_ready():
            return
        try:
            print(f"Got message '{message.content}'")
        except UnicodeDecodeError:
            print("Message content not printable")

        if len(message.embeds) > 0:
            embeds = ""
            for emb in message.embeds:
                embeds += str(emb.to_dict())
            print(f"With embed(s):\n{embeds}")

        print(f"From @{message.author}")
        print(f"In server {message.guild}")
        print(f"In channel {message.channel}")

        if message.author.bot:
            return
        else:
            await self.track_message(f"tracked_message {message.id}")

            if isinstance(message.channel, discord.abc.GuildChannel):
                if message.channel.permissions_for(message.guild.me).send_messages:
                    if message.content.startswith(message.guild.me.mention):
                        ping_images = [
                            "https://cdn.discordapp.com/emojis/389570423450370048.png",
                            "https://cdn.discordapp.com/attachments/541876503814733836/557088019073466408/unknown.png",
                            "https://media.tenor.com/images/cca1d4bbb1216e46645d368050c020ac/tenor.gif",
                            "https://media.tenor.com/images/2ccae15299d6f3345a45306214b9baea/tenor.gif"
                        ]
                        desc = plural(await get_pre(self, message))
                        emb = discord.Embed(
                            color=0xf92f2f,
                            description=f":eyes: Who pinged? My prefix(es) is/are `{desc}`. If you are in a DM with me, I do not require a prefix."
                        )
                        emb.set_image(url=random.choice(ping_images))

                        await message.channel.send(embed=emb)

                    owner = (await self.application_info()).owner
                    m1 = f"<@!{owner.id}>"
                    m2 = f"<@{owner.id}>"
                    if (message.content.startswith(m1) or message.content.startswith(m2)) and message.author != owner:
                        await message.channel.send("<:angryping:564532599918297117>")

                    await self.process_commands(message)

                else:
                    if message.content.startswith(config.prefix):
                        await message.author.send(":x: I can't send messages there! Perhaps try again elsewhere?")
            else:
                await self.process_commands(message)


    async def track_message(self, message):
        if await self.redis.exists(message):
            return

        await self.redis.rpush(message, 0)
        await self.redis.expire(message, 3600)

    async def on_raw_message_edit(self, payload):
        if not self.is_ready():
            return

        if "content" not in payload.data:
            return

        channel = self.get_channel(int(payload.data["channel_id"]))

        if channel is None:
            return

        message = channel._state._get_message(payload.message_id)
        if message is None:
            try:
                message = await channel.fetch_message(payload.message_id)
            except discord.HTTPException:
                return

        if await self.redis.exists(f"tracked_message {payload.message_id}"):
            await self.clear_messages(f"tracked_message {payload.message_id}")
        await self.process_commands(message)

    async def on_raw_message_delete(self, payload):
        if not self.is_ready():
            return

        if await self.redis.exists(payload.message_id):
            await self.clear_messages(payload.message_id)
            await self.redis.delete(payload.message_id)

    async def clear_messages(self, tracked_message):
        for message_data in await self.redis.lrange(tracked_message, 1, -1):
            channel_id, message_id = message_data.split(":")
            try:
                await self.http.delete_message(
                    int(channel_id), int(message_id))
            except discord.NotFound:
                pass

        await self.redis.execute("LTRIM", tracked_message, 0, 0)

    async def register_response(self, response, request):
        if await self.redis.exists(f"tracked_message {request.id}"):
            await self.redis.rpush(
                f"tracked_message {request.id}",
                f"{response.channel.id}:{response.id}"
            )

    async def on_guild_join(self, guild):
        async with aiosqlite.connect(config.db_path) as db:
            await db.execute(f"INSERT INTO guilds (id, prefix) VALUES ({guild.id}, '{config.prefix}');")

    async def on_guild_remove(self, guild):
        async with aiosqlite.connect(config.db_path) as db:
            await db.execute(f"DELETE FROM guilds WHERE id = {guild.id};")

    async def playingstatus(self):

        await self.wait_until_ready()

        playing_statuses = [
            " ",
            "and plotting pranks",
            "at a robot party, brb in a bit",
            "being improved!",
            "being open source",
            "being SuprKewl!",
            "chess with Kasparov",
            "creeping through the shadows",
            "eating robot food, brb",
            "github.com/laggycomputer/suprkewl-bot",
            "helping the community",
            "I don't game...",
            "idling",
            "living under the MIT license!",
            "mafia",
            "meme-scrolling",
            "ping and run",
            "tag with other robots",
            "the attention game",
            "waiting for you to call me!",
            "werewolf",
            "with my dad, Too Laggy",
            "with my Raspberry Pi",
            "with the community",
            "with the Discord API"
        ]

        while self.is_ready():
            status = f"{random.choice(playing_statuses)} | lurking in {len(self.guilds)} servers and watching over {len(self.users)} users..."

            await self.change_presence(activity=discord.Game(name=status), status=discord.Status.idle)
            await asyncio.sleep(120)

    async def on_command_error(self, ctx, error):

        if hasattr(ctx.command, "on_error"):
            return

        ignored = (commands.CommandNotFound, commands.UserInputError)

        error = getattr(error, "original", error)

        def permsList(perms):

            if len(perms) == 0:
                return None
            else:
                if len(perms) == 1:
                    return apiToHuman[perms[0]]
                else:
                    fmt = ""
                    for i in range(0, len(perms)):
                        fmt += apiToHuman[i]
                        fmt += ", "
                        fmt += f"and {perms[-1]}"

                    return fmt

        if isinstance(error, ignored):
            return

        elif isinstance(error, commands.DisabledCommand):

            emb = discord.Embed(color=0xf92f2f)
            emb.add_field(name="Disabled Command", value=f":x: `{ctx.prefix}{ctx.command}` has been disabled!")
            emb.set_thumbnail(url=self.user.avatar_url)
            emb.set_author(name=self.user.name, icon_url=self.user.avatar_url)
            emb.set_footer(text=f"{self.description} Requested by {ctx.author}", icon_url=ctx.author.avatar_url)

            return await ctx.send(embed=emb)

        elif isinstance(error, commands.NoPrivateMessage):

            emb = discord.Embed(color=0xf92f2f)
            emb.add_field(name="This command is disabled in DMs", value=f":x: `{ctx.prefix}{ctx.command}` can only be used in servers, not in DMs or DM groups.")
            emb.set_thumbnail(url=self.user.avatar_url)
            emb.set_author(name=self.user.name, icon_url=self.user.avatar_url)
            emb.set_footer(text=f"{self.description} Requested by {ctx.author}", icon_url=ctx.author.avatar_url)

            return await ctx.send(embed=emb)

        elif isinstance(error, commands.CommandOnCooldown):

            retry = round(error.retry_after, 2)

            emb = discord.Embed(color=0xf92f2f)
            emb.add_field(name="Command on Cooldown",
                          value=f"Woah there! You just triggered a cooldown trying to run `{ctx.prefix}{ctx.command}`. I'll let you know you can start it after the cooldown of {retry} seconds is over.")
            emb.set_thumbnail(url=self.user.avatar_url)
            emb.set_author(name=self.user.name, icon_url=self.user.avatar_url)
            emb.set_footer(text=f"{self.description} Requested by {ctx.author}", icon_url=ctx.author.avatar_url)

            msg = await ctx.send(embed=emb)

            await asyncio.sleep(retry)

            await ctx.send(f"{ctx.author.mention} The cooldown is over!")

            return msg

        elif isinstance(error, commands.MissingPermissions):

            emb = discord.Embed(color=0xf92f2f)
            missingPerms = permsList(error.missing_perms)
            emb.add_field(name="User Missing Permissions", value=f":x: Permission denied to run `{ctx.prefix}{ctx.command}`. You need to be able to {missingPerms}.")
            emb.set_thumbnail(url=self.user.avatar_url)
            emb.set_author(name=self.user.name, icon_url=self.user.avatar_url)
            emb.set_footer(text=f"{self.description} Requested by {ctx.author}", icon_url=ctx.author.avatar_url)

            return await ctx.send(embed=emb)

        elif isinstance(error, commands.BotMissingPermissions):

            emb = discord.Embed(color=0xf92f2f)
            missingPerms = permsList(error.missing_perms)
            emb.add_field(name="Bot Missing Permissions", value=f":x: I don't have the proper permissions to run `{ctx.prefix}{ctx.command}`. I need to be allowed to {missingPerms}.")
            emb.set_thumbnail(url=self.user.avatar_url)
            emb.set_author(name=self.user.name, icon_url=self.user.avatar_url)
            emb.set_footer(text=f"{self.description} Requested by {ctx.author}", icon_url=ctx.author.avatar_url)

            return await ctx.send(embed=emb)

        print(f"Ignoring exception in command {ctx.prefix}{ctx.command}:")

        traceback.print_exception(type(error), error, error.__traceback__)

    async def logout(self):
        if not self.http2.closed:
            await self.http2.close()
            await asyncio.sleep(0)

        await super().logout()


async def get_pre(bot, message):
    pre = [config.prefix]
    if isinstance(message.channel, discord.DMChannel):
        pre.append("")
    elif isinstance(message.channel, discord.TextChannel):
        async with aiosqlite.connect(config.db_path) as db:
            async with db.execute(f"SELECT prefix FROM guilds WHERE id = {message.guild.id};") as cur:
                fetched = (await cur.fetchall())[0][0]
            if fetched not in pre:
                pre.append(fetched[0][0])

    return pre