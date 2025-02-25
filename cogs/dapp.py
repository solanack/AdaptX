import discord
from discord.ext import commands

class DAppCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    @commands.command(name="linkwallet")
    async def linkwallet(self, ctx, wallet_address: str):
        """Links a Solana wallet to a Discord user (placeholder for signature verification)."""
        self.db.execute('INSERT OR REPLACE INTO users (id, wallet) VALUES (?, ?)', (ctx.author.id, wallet_address))
        self.db.commit()
        await ctx.send("Wallet linked (placeholder for verification).")

    @commands.command(name="stake")
    async def stake(self, ctx, amount: float):
        """Initiates staking (placeholder)."""
        cursor = self.db.execute('SELECT wallet FROM users WHERE id = ?', (ctx.author.id,))
        row = cursor.fetchone()
        if not row:
            await ctx.send("Please link your wallet first with /linkwallet.")
            return
        wallet = row[0]
        await ctx.send(f"Staking {amount} SOL from {wallet} (placeholder).")

async def setup(bot):
    await bot.add_cog(DAppCog(bot))