import discord
from discord.ext import commands

class GamificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        self.db.execute('INSERT OR IGNORE INTO users (id, points) VALUES (?, 0)', (message.author.id,))
        self.db.execute('UPDATE users SET points = points + 1 WHERE id = ?', (message.author.id,))
        self.db.commit()

    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx):
        """Displays top 5 users by points."""
        cursor = self.db.execute('SELECT id, points FROM users ORDER BY points DESC LIMIT 5')
        top_users = cursor.fetchall()
        embed = discord.Embed(title="Leaderboard")
        for i, (user_id, points) in enumerate(top_users, 1):
            user = await self.bot.fetch_user(user_id)
            embed.add_field(name=f"{i}. {user.name}", value=f"{points} points", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(GamificationCog(bot))