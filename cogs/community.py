import discord
from discord.ext import commands
import datetime

class CommunityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="scheduleama")
    async def scheduleama(self, ctx, topic: str, date: str):
        """Schedules an AMA as a Discord event."""
        guild = ctx.guild
        try:
            start_time = datetime.datetime.fromisoformat(date)
            event = await guild.create_scheduled_event(
                name=f"AMA: {topic}",
                description="Join us for an AMA!",
                start_time=start_time,
                end_time=start_time + datetime.timedelta(hours=1),
                entity_type=discord.EntityType.voice,
                location="Voice Channel"
            )
            await ctx.send(f"AMA scheduled: {event.url}")
        except ValueError:
            await ctx.send("Invalid date format. Use ISO format (e.g., '2023-12-01T15:00:00').")

async def setup(bot):
    await bot.add_cog(CommunityCog(bot))