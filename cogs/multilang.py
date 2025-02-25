from typing import Union
import discord
from discord.ext import commands
from googletrans import Translator

class MultiLangCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.translator = Translator()

    @commands.command(name="setlanguage")
    async def setlanguage(self, ctx, language: str):
        """Sets a user's preferred language (e.g., 'es' for Spanish)."""
        self.db.execute('INSERT OR REPLACE INTO users (id, language) VALUES (?, ?)', (ctx.author.id, language))
        self.db.commit()
        await ctx.send(f"Language set to {language}.")

    async def send_translated(self, interaction, message):
        cursor = self.db.execute('SELECT language FROM users WHERE id = ?', (interaction.user.id,))
        row = cursor.fetchone()
        lang = row[0] if row else 'en'
        if lang != 'en':
            translated = self.translator.translate(message, dest=lang).text
            await interaction.followup.send(translated)
        else:
            await interaction.followup.send(message)

async def setup(bot):
    await bot.add_cog(MultiLangCog(bot))