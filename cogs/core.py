import discord
from discord import app_commands
from discord.ext import commands

class CoreCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.adaptx = bot.adaptx

    @app_commands.command(name="idea", description="Generate a Solana-focused tweet idea.")
    async def idea(self, interaction: discord.Interaction, topic: str = "Solana trends"):
        await interaction.response.defer(thinking=True)
        idea = await self.adaptx.generate_post_ideas(topic)
        await self.send_translated(interaction, f"📝 **Idea:** {idea}")

    @app_commands.command(name="ask", description="Ask a Solana-related question.")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer(thinking=True)
        answer = await self.adaptx.ask_question(question)
        await self.send_translated(interaction, f"❓ **Q:** {question}\n💡 **A:** {answer}")

    @app_commands.command(name="analyze", description="Analyze a Solana transaction.")
    async def analyze(self, interaction: discord.Interaction, tx_hash: str):
        await interaction.response.defer(thinking=True)
        result = await self.adaptx.analyze_transaction(tx_hash)
        message = result["analysis"] if "analysis" in result else result["error"]
        await self.send_translated(interaction, message)

    @app_commands.command(name="walletanalysis", description="Analyze a Solana wallet's holdings.")
    async def walletanalysis(self, interaction: discord.Interaction, wallet_address: str):
        await interaction.response.defer(thinking=True)
        analysis = await self.adaptx.analyze_wallet(wallet_address)
        await self.send_translated(interaction, analysis)

    @app_commands.command(name="price", description="Get Solana's price and stats (or specify another crypto).")
    async def price(self, interaction: discord.Interaction, crypto: str = "solana"):
        await interaction.response.defer(thinking=True)
        price_info = await self.adaptx.get_crypto_price_coingecko(crypto)
        await self.send_translated(interaction, price_info)

    @app_commands.command(name="networkstats", description="Get real-time Solana network statistics.")
    async def networkstats(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        stats = await self.adaptx.get_solana_network_stats()
        await self.send_translated(interaction, stats)

    @app_commands.command(name="scheduleama", description="Schedule an AMA with a Solana developer or project.")
    async def scheduleama(self, interaction: discord.Interaction, topic: str, date: str):
        message = f"📅 **AMA Scheduled:**\nTopic: {topic}\nDate: {date}\nStay tuned for more details!"
        await self.send_translated(interaction, message)

    @app_commands.command(name="governance", description="Discuss current Solana governance proposals.")
    async def governance(self, interaction: discord.Interaction):
        message = "🗳️ **Solana Governance:**\nCheck out the latest proposals at [Solana Governance](https://solanavoting.com).\nDiscuss and share your thoughts here!"
        await self.send_translated(interaction, message)

    @app_commands.command(name="usecases", description="Highlight Solana projects with real-world applications.")
    async def usecases(self, interaction: discord.Interaction):
        projects = [
            "• **Helium**: Decentralized wireless network.\n",
            "• **Audius**: Decentralized music streaming.\n",
            "• **Star Atlas**: Blockchain-based gaming metaverse.\n",
            "• **Mango Markets**: Decentralized exchange with leverage trading.\n",
        ]
        message = "🌍 **Solana Real-World Use Cases:**\n" + "\n".join(projects)
        await self.send_translated(interaction, message)

    async def send_translated(self, interaction, message):
        multilang_cog = self.bot.get_cog('MultiLangCog')
        if multilang_cog:
            await multilang_cog.send_translated(interaction, message)
        else:
            await interaction.followup.send(message)

async def setup(bot):
    await bot.add_cog(CoreCog(bot))