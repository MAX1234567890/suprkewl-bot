# -*- coding: utf-8 -*-

"""
Copyright (C) 2019 laggycomputer

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import datetime
import inspect
import itertools
import os
import pkg_resources
import platform
import time

import discord
from discord.ext import commands
import pygit2

from .utils import linecount
from .utils import time as t_utils
import config


# Largely from R. Danny.
def format_commit(commit):
    short, _, _ = commit.message.partition("\n")
    short_sha2 = commit.hex[0:6]
    commit_tz = datetime.timezone(
        datetime.timedelta(minutes=commit.commit_time_offset))
    commit_time = datetime.datetime.fromtimestamp(
        commit.commit_time).replace(tzinfo=commit_tz)

    offset = t_utils.human_timedelta(commit_time.astimezone(
        datetime.timezone.utc).replace(tzinfo=None), accuracy=1)
    return f"[`{short_sha2}`](https://github.com/laggycomputer/suprkewl-bot/commit/{commit.hex} \"Boo!\")" \
        f" {short} ({offset})"


def get_last_commits(count=5):
    try:
        repo = pygit2.Repository("../.git")
    except pygit2.GitError:
        repo = pygit2.Repository(".git")
    commits = list(itertools.islice(
        repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL), count))
    return "\n".join(format_commit(c) for c in commits)


def current_time():
    year, month, dayofmonth, hour, minute, second, dayofweek, _, isdst = time.localtime()
    week = ["Sunday", "Monday", "Tuesday",
            "Wednesday", "Thursday", "Friday", "Saturday"]
    dayofweek = week[dayofweek]
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "November", "December"
    ]
    month = months[month]
    disptime = f"{dayofweek}, {month} {dayofmonth}, {year}; {hour}:{minute}:{second}, Pacific Standard Time"
    if isdst:
        disptime += " (DST)"

    return disptime


async def get_build_status(cs):
    repo_id = 9109252
    token = config.travis_token
    headers = {"Travis-API-Version": "3", "Authorization": f"token {token}"}
    async with cs.get(f"https://api.travis-ci.com/repo/{repo_id}/branches", headers=headers) as resp:
        text = await resp.json()
        branches = text["branches"]
    ret = {}

    for branch in branches:
        key = branch["name"]
        ret[key] = {}

        duration = branch["last_build"]["duration"]

        started_at, finished_at = branch["last_build"]["started_at"], branch["last_build"]["finished_at"]

        if finished_at is not None:
            if duration >= 60:
                minutes, seconds = divmod(duration, 60)
                duration = f"{minutes} minutes"

                if seconds:
                    duration += f" and {seconds} seconds"
            else:
                duration = str(duration) + " seconds"

            build_status = branch["last_build"]["state"].title()
            val = f"{build_status} after {duration}"

            finished_at = finished_at.rstrip("Z")
            date, time_ = finished_at.split("T")
            date = date.split("-")
            time_ = time_.split(":")

            date = tuple(int(v) for v in date)
            time_ = tuple(int(v) for v in time_)

            year, month, dayofmonth = date
            hour, minute, second = time_

            dt = datetime.datetime(year, month, dayofmonth, hour, minute, second)
            offset = t_utils.human_timedelta(dt, accuracy=1)

            val += ", " + offset

            ret[key]["status"] = val
        else:
            val = "Build in progress"
            if started_at is not None:
                started_at = started_at.rstrip("Z")
                date, time_ = started_at.split("T")
                date = date.split("-")
                time_ = time_.split(":")

                date = tuple(int(v) for v in date)
                time_ = tuple(int(v) for v in time_)

                year, month, dayofmonth = date
                hour, minute, second = time_

                dt = datetime.datetime(year, month, dayofmonth, hour, minute, second)
                offset = t_utils.human_timedelta(dt, accuracy=1)

                val += " from " + offset

            ret[key]["status"] = val

        ret[key]["id"] = branch["last_build"]["id"]
    return ret


class About(commands.Cog):

    @commands.command(aliases=["github", "branches"])
    async def git(self, ctx):
        """Get info about the Git repository for this bot."""

        emb = discord.Embed(name="GitHub info", color=ctx.bot.embed_color, description=get_last_commits())
        fieldval = []
        build_status = await get_build_status(ctx.bot.http2)
        for branch_name in build_status:
            fieldval.append(
                f"`{branch_name}`: [{build_status[branch_name]['status']}]"
                f"(https://travis-ci.com/laggycomputer/suprkewl-bot/builds/{build_status[branch_name]['id']}"
                f" \"Boo!\")"
            )
        emb.add_field(name="Build status", value="\n".join(fieldval))
        emb.set_thumbnail(url=ctx.bot.user.avatar_url)
        emb.set_author(
            name=ctx.bot.user.name,
            icon_url=ctx.bot.user.avatar_url
        )
        emb.set_footer(
            text=f"{ctx.bot.embed_footer} Requested by {ctx.author}",
            icon_url=ctx.author.avatar_url
        )

        await ctx.send(embed=emb)

    @commands.command()
    async def stats(self, ctx):
        """Get some bot stats."""

        emb = discord.Embed(name="Bot status", color=ctx.bot.embed_color)
        emb.add_field(name="Line count", value=linecount())
        cmds_used = ctx.bot.commands_used
        msgs_seen = ctx.bot.messages_seen
        emb.add_field(
            name="Stats",
            value=f"{cmds_used} commands used since start, {msgs_seen} messages seen since start, {len(ctx.bot.users)}"
            f" users, {len(ctx.bot.guilds)} guilds, {len(ctx.bot.commands)} commands"
        )

        emb.set_thumbnail(url=ctx.bot.user.avatar_url)
        emb.set_author(
            name=ctx.bot.user.name,
            icon_url=ctx.bot.user.avatar_url
        )
        emb.set_footer(
            text=f"{ctx.bot.embed_footer} Requested by {ctx.author}",
            icon_url=ctx.author.avatar_url
        )

        await ctx.send(embed=emb)

    @commands.command(aliases=["info"])
    async def about(self, ctx):
        """Give some general bot info."""

        async with ctx.typing():
            emb = discord.Embed(name="Bot info", color=ctx.bot.embed_color)

            emb.add_field(name="Support Server", value="[Here](https://www.discord.gg/CRBBJVY \"Boo!\")")
            emb.add_field(name="System Time", value=current_time())
            emb.add_field(name="Processor Type", value=platform.machine().lower())
            emb.add_field(
                name="OS version (short)",
                value=platform.system() + " " + platform.release()
            )
            emb.add_field(
                name="OS version (long)",
                value=platform.platform(aliased=True)
            )
            emb.add_field(
                name="Python Version", value=f"Python {platform.python_branch()},"
                f" build date {platform.python_build()[1]}"
            )
            emb.add_field(
                name="discord.py version",
                value=pkg_resources.get_distribution("discord.py").version
            )
            emb.add_field(
                name="Jishaku version",
                value=pkg_resources.get_distribution("jishaku").version
            )
            emb.add_field(name="Processor name", value=platform.processor())
            emb.add_field(
                name="Current server count",
                value=str(len(ctx.bot.guilds))
            )
            owner_id = ctx.bot.owner_id
            if ctx.guild is not None:
                owner = await ctx.guild.fetch_member(owner_id)
            else:
                owner = None
            if owner is not None:
                emb.add_field(name="Bot owner", value=f"<@{owner_id}>")
            emb.set_thumbnail(url=ctx.bot.user.avatar_url)
            emb.set_author(
                name=ctx.bot.user.name,
                icon_url=ctx.bot.user.avatar_url
            )
            emb.set_footer(
                text=f"{ctx.bot.embed_footer} Requested by {ctx.author}",
                icon_url=ctx.author.avatar_url
            )

        await ctx.send(embed=emb)

    @commands.command()
    async def ping(self, ctx):
        """Check the bot's latency."""

        latency = ctx.bot.latency * 1000
        latency = round(latency, 4)
        emb = discord.Embed(
            description=f":ping_pong: My current latency is {latency} milliseconds.", color=ctx.bot.embed_color)
        fp = discord.File("../assets/catping.gif", "image.gif")
        emb.set_image(
            url="attachment://image.gif"
        )

        await ctx.send(embed=emb, file=fp)

    # From R. Danny
    @commands.command(
        description="Use dots or spaces to find source code for subcommands, e.g. `clear info` or `clear.info`."
    )
    async def source(self, ctx, *, command=None):
        """Find my source code for a specific command."""

        source_url = "https://github.com/laggycomputer/suprkewl-bot/blob/untested"
        if command is None:
            return await ctx.send(source_url)

        if command == "help":
            src = type(ctx.bot.help_command)
            module = src.__module__
            filename = inspect.getsourcefile(src)
        else:
            obj = ctx.bot.get_command(command.replace(".", " "))
            if obj is None:
                return await ctx.send("Could not find command.")

            # since we found the command we're looking for, presumably anyway, let's
            # try to access the code itself
            src = obj.callback.__code__
            module = obj.callback.__module__
            filename = src.co_filename

        lines, firstlineno = inspect.getsourcelines(src)
        if not module.startswith("discord"):
            if module.startswith("jishaku"):
                source_url = "https://github.com/Gorialis/jishaku"
                location = module.replace(".", "/") + ".py"
            else:
                location = os.path.relpath(filename).replace("\\", "/")
        else:
            location = module.replace(".", "/") + ".py"
            source_url = 'https://github.com/Rapptz/discord.py/blob/master'

        final_url = f"<{source_url}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>"

        await ctx.send(final_url)


def setup(bot):
    bot.add_cog(About())
