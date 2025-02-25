import discord
from discord.ext import commands

class DashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.adaptx = bot.adaptx

    @commands.command(name="dashboard")
    async def dashboard(self, ctx):
        """Displays a user's wallet dashboard."""
        cursor = self.db.execute('SELECT wallet FROM users WHERE id = ?', (ctx.author.id,))
        row = cursor.fetchone()
        if not row:
            await ctx.send("Please link your wallet first with /linkwallet.")
            return
        wallet_address = row[0]
        analysis = await self.adaptx.analyze_wallet(wallet_address)
        await ctx.send(analysis)

async def setup(bot):
    await bot.add_cog(DashboardCog(bot))