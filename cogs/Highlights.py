import re
import discord
from discord.ext import commands


class Highlights(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild or not msg.content or msg.author.bot:
            return
        async with self.bot.db_connect() as db:
            async with db.execute("SELECT * FROM highlight") as cur:
                highlights = await cur.fetchall()
            quoted = set()
            for user_id, query in highlights:
                if user_id not in quoted and user_id != msg.author.id and re.search(query, msg.content, re.IGNORECASE):
                    if user := self.bot.get_user(user_id):
                        if user.permissions_in(msg.channel).read_messages:
                            quoted.add(user_id)
                            try:
                                await self.bot.quote_message(msg, user, user, "highlight")
                            except discord.Forbidden:
                                await db.execute("DELETE FROM highlight WHERE user_id = ?", user_id)
                            except discord.HTTPException:
                                continue
                    else:
                        await db.execute("DELETE FROM highlight WHERE user_id = ?", user_id)
            await db.commit()

    @commands.command(aliases=["hl"])
    async def highlight(self, ctx, *, pattern: str):
        if len(pattern) > 50:
            return await ctx.send(await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlight_toolong", "error"))
        try:
            re.compile(pattern)
        except re.error:
            return await ctx.send(await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlight_invalid", "error"))
        try:
            await ctx.author.send()
        except discord.Forbidden:
            return await ctx.send(await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlight_dmsdisabled", "error"))
        except discord.HTTPException:
            pass
        async with self.bot.db_connect() as db:
            async with db.execute(
                "SELECT COUNT(query) FROM highlight WHERE user_id = ?", (user_id := ctx.author.id,)
            ) as cur:
                if (await cur.fetchone())[0] >= 10:
                    return await ctx.send(await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlight_limitexceeded", "error"))
            await db.execute("INSERT OR IGNORE INTO highlight VALUES (?, ?)", (user_id, pattern))
            await db.commit()
        await ctx.send(
            (await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlight_added", "success")).format(
                pattern.replace("`", "").replace("*", "")
            )
        )

    @commands.command(aliases=["highlights", "hllist"])
    async def highlightlist(self, ctx):
        if highlights := await self.bot.fetch(
            "SELECT query FROM highlight WHERE user_id = ?", (ctx.author.id,), one=False, single_column=True
        ):
            embed = discord.Embed(
                description="\n".join(f"`{highlight.replace('`', '')}`" for highlight in highlights),
                color=ctx.author.color.value or discord.Embed.Empty,
            )
            embed.set_author(
                name=await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlightlist_embedauthor"),
                icon_url=ctx.author.avatar_url,
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlightlist_nohighlights", "error"))

    @commands.command(aliases=["hlremove", "hldelete", "hldel"])
    async def highlightremove(self, ctx, *, pattern: str):
        async with self.bot.db_connect() as db:
            async with db.execute(
                "SELECT * FROM highlight WHERE user_id = ? AND query = ?", (user_id := ctx.author.id, pattern)
            ) as cur:
                if await cur.fetchone():
                    await db.execute("DELETE FROM highlight WHERE user_id = ? AND query = ?", (user_id, pattern))
                else:
                    async with db.execute(
                        "SELECT query FROM highlight WHERE user_id = ? AND query LIKE ?", (user_id, f"{pattern}%")
                    ) as cur:
                        if len(results := await cur.fetchall()) == 1:
                            await db.execute(
                                "DELETE FROM highlight WHERE user_id = ? AND query = ?", (user_id, pattern := results[0][0])
                            )
                        else:
                            return await ctx.send(
                                await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlightremove_notfound", "error")
                            )
                await db.commit()
        await ctx.send(
            (await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlightremove_removed", "success")).format(
                pattern.replace("`", "").replace("*", "")
            )
        )

    @commands.command(aliases=["hlclear"])

    async def highlightclear(self, ctx):
        async with self.bot.db_connect() as db:
            await db.execute("DELETE FROM highlight WHERE user_id = ?", (ctx.author.id,))
            await db.commit()
        await ctx.send(await self.bot.localize(ctx.guild, "HIGHLIGHTS_highlightclear_cleared", "success"))


def setup(bot):
    bot.add_cog(Highlights(bot))
