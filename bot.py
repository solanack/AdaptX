import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from collections import defaultdict
import json
import openai
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
import time

# Blockchain libraries
from solana.rpc.async_api import AsyncClient
from web3 import Web3
from web3.middleware import geth_poa_middleware

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SolShieldX")

# Load environment variables from .env file
load_dotenv()

# Retrieve API keys and tokens from environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INFURA_API_KEY = os.getenv("INFURA_API_KEY")

# Configure OpenAI with the API key
openai.api_key = OPENAI_API_KEY

# Set up Discord bot intents and command prefix
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Required to read message content
bot = commands.Bot(command_prefix="!", intents=intents)

class SolShieldX:
    def __init__(self):
        # Initialize blockchain clients
        self.solana_client = AsyncClient("https://api.mainnet-beta.solana.com")
        self.web3_eth = Web3(Web3.HTTPProvider(f"https://mainnet.infura.io/v3/{INFURA_API_KEY}"))
        self.web3_eth.middleware_onion.inject(geth_poa_middleware, layer=0)

        # Threat detection data (if needed for future features)
        self.threat_db = defaultdict(set)
        self.load_threat_data()

        # Cache for OpenAI responses to save on API calls.
        # The cache maps a key string to a tuple: (timestamp, response)
        self.cache = {}

    def load_threat_data(self):
        """Load threat data from a JSON file."""
        try:
            with open("threat_feeds.json") as f:
                data = json.load(f)
                self.threat_db.update(data.get("addresses", {}))
        except Exception as e:
            logger.warning(f"Error loading threat data: {e}")

    async def cached_call(self, key: str, generator, ttl: int = 3600):
        """
        Checks the cache for an existing response.
        If a valid cached value exists (within TTL seconds), returns it.
        Otherwise, generates a new value and caches it.
        """
        now = time.time()
        if key in self.cache:
            ts, value = self.cache[key]
            if now - ts < ttl:
                logger.info(f"Using cached value for key: {key}")
                return value
        value = await asyncio.to_thread(generator)
        self.cache[key] = (now, value)
        return value

    async def generate_post_ideas(self, topic="crypto trends"):
        """
        Generate one tweet idea with a cool, humble influencer vibe.
        Focus on trends in Solana, Ethereum, Bitcoin, XRP, and Solana memecoins/trading.
        Cached for 1 hour.
        """
        key = f"idea:{topic}"
        def generate():
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system", 
                            "content": (
                                "You are a cool, humble crypto influencer known for your authentic and engaging style. "
                                "You cover trends in the Solana, Ethereum, Bitcoin, and XRP ecosystems, as well as the buzz around Solana memecoins and trading. "
                                "Your tweets are natural, conversational, and resonate with the crypto community."
                            )
                        },
                        {
                            "role": "user", 
                            "content": f"Generate one tweet idea about {topic} that sounds genuine and could catch the attention of key influencers. Avoid overly technical or generic language."
                        }
                    ],
                    max_tokens=80
                )
                idea = response["choices"][0]["message"]["content"].strip()
                return idea
            except Exception as e:
                return f"⚠️ Error generating idea: {str(e)}"
        return await self.cached_call(key, generate, ttl=3600)

    async def generate_variants(self, n=3, topic="crypto trends"):
        """
        Generate multiple tweet variants with an influencer vibe.
        Cached for 1 hour.
        """
        key = f"variants:{n}:{topic}"
        def generate():
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system", 
                            "content": (
                                "You are a cool, humble crypto influencer with a knack for crafting tweets that feel personal and engaging. "
                                "Focus on trends in the Solana, Ethereum, Bitcoin, and XRP ecosystems, as well as the latest in Solana memecoins and trading buzz. "
                                "Keep the tone natural and relatable."
                            )
                        },
                        {
                            "role": "user", 
                            "content": f"Generate {n} tweet variants about {topic} that would resonate with crypto enthusiasts and influencers. Each variant should sound authentic and avoid typical bot language."
                        }
                    ],
                    max_tokens=120
                )
                text = response["choices"][0]["message"]["content"].strip()
                variants = [variant.strip() for variant in text.split("\n") if variant.strip()]
                return variants
            except Exception as e:
                return [f"⚠️ Error generating variants: {str(e)}"]
        return await self.cached_call(key, generate, ttl=3600)

    async def ask_question(self, question: str):
        """
        Answer a crypto-related question using OpenAI.
        Cached for 1 hour.
        """
        key = f"ask:{question}"
        def generate():
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a knowledgeable crypto expert with real-world insights."},
                        {"role": "user", "content": question}
                    ],
                    max_tokens=150
                )
                answer = response["choices"][0]["message"]["content"].strip()
                return answer
            except Exception as e:
                return f"⚠️ Error answering question: {str(e)}"
        return await self.cached_call(key, generate, ttl=3600)

    async def generate_crypto_news(self):
        """
        Generate a concise summary of the current state of the cryptocurrency market.
        Cached for 30 minutes.
        """
        key = "news"
        def generate():
            try:
                prompt = (
                    "Summarize the latest trends and events in the cryptocurrency market. Focus on major ecosystems like Solana, Ethereum, Bitcoin, XRP, "
                    "and include commentary on memecoin trading trends. Keep it brief, impactful, and influencer-friendly."
                )
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a savvy crypto market analyst with a finger on the pulse of trends."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150
                )
                news_summary = response["choices"][0]["message"]["content"].strip()
                return news_summary
            except Exception as e:
                return f"⚠️ Error generating crypto news: {str(e)}"
        return await self.cached_call(key, generate, ttl=1800)

    async def generate_crypto_quote(self):
        """
        Generate an inspirational crypto-related quote.
        Cached for 30 minutes.
        """
        key = "quote"
        def generate():
            try:
                prompt = (
                    "Provide an inspirational crypto-related quote that is cool and humble, "
                    "and that would resonate with influencers and the broader crypto community."
                )
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a creative and motivational crypto influencer."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=60
                )
                quote = response["choices"][0]["message"]["content"].strip()
                return quote
            except Exception as e:
                return f"⚠️ Error generating quote: {str(e)}"
        return await self.cached_call(key, generate, ttl=1800)

    async def summarize_url(self, url: str):
        """
        Fetch and summarize the content of a given URL.
        Cached for 24 hours.
        """
        key = f"summarize:{url}"
        def generate():
            try:
                response = requests.get(url, timeout=10)
                if response.status_code != 200:
                    return f"⚠️ Failed to fetch URL. Status code: {response.status_code}"
                soup = BeautifulSoup(response.text, 'html.parser')
                paragraphs = soup.find_all('p')
                text = "\n".join([p.get_text() for p in paragraphs])
                if len(text) > 2000:
                    text = text[:2000]
                prompt = f"Summarize the following text in a concise and engaging manner:\n\n{text}"
                summary_response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are an expert summarizer who captures the essence of content."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=100
                )
                summary = summary_response["choices"][0]["message"]["content"].strip()
                return summary
            except Exception as e:
                return f"⚠️ Error summarizing URL: {str(e)}"
        return await self.cached_call(key, generate, ttl=86400)

    async def analyze_transaction(self, chain: str, tx_hash: str):
        """
        Analyze a blockchain transaction (Solana or Ethereum) with a basic risk assessment.
        (This function does not use OpenAI and is low cost.)
        """
        try:
            if chain.lower() == "solana":
                tx = await self.solana_client.get_transaction(tx_hash)
                analysis = f"The Solana transaction {tx_hash} has been analyzed. Risk score: 0.5 (simplified analysis)."
                return {"chain": chain, "analysis": analysis}
            elif chain.lower() == "eth":
                tx = self.web3_eth.eth.get_transaction(tx_hash)
                analysis = f"The Ethereum transaction {tx_hash} has been analyzed. Risk score: 0.5 (simplified analysis)."
                return {"chain": chain, "analysis": analysis}
            return {"error": "Unsupported chain"}
        except Exception as e:
            logger.error(f"Error analyzing transaction: {e}")
            return {"error": str(e)}

# Instantiate our main class
solshieldx = SolShieldX()

@bot.event
async def on_ready():
    ready_message = "Are You Ready?: To Make It Rain Impressions."
    ascii_art = r"""

   ▄████████  ▄██████▄   ▄█          ▄████████    ▄█    █▄     ▄█     ▄████████  ▄█       ████████▄  ▀████    ▐████▀ 
  ███    ███ ███    ███ ███         ███    ███   ███    ███   ███    ███    ███ ███       ███   ▀███   ███▌   ████▀  
  ███    █▀  ███    ███ ███         ███    █▀    ███    ███   ███▌   ███    █▀  ███       ███    ███    ███  ▐███    
  ███        ███    ███ ███         ███         ▄███▄▄▄▄███▄▄ ███▌  ▄███▄▄▄     ███       ███    ███    ▀███▄███▀    
▀███████████ ███    ███ ███       ▀███████████ ▀▀███▀▀▀▀███▀  ███▌ ▀▀███▀▀▀     ███       ███    ███    ████▀██▄     
         ███ ███    ███ ███                ███   ███    ███   ███    ███    █▄  ███       ███    ███   ▐███  ▀███    
   ▄█    ███ ███    ███ ███▌    ▄    ▄█    ███   ███    ███   ███    ███    ███ ███▌    ▄ ███   ▄███  ▄███     ███▄  
 ▄████████▀   ▀██████▀  █████▄▄██  ▄████████▀    ███    █▀    █▀     ██████████ █████▄▄██ ████████▀  ████       ███▄ 
                                                                                                                   
 
    """
    logger.info(ready_message)
    print(ready_message)
    print(ascii_art)

# ----------------- Discord Commands -----------------

@bot.command(name="idea")
@commands.cooldown(1, 60, commands.BucketType.user)
async def post_idea(ctx, *, topic="crypto trends"):
    """Generate and send a single tweet idea on a given topic."""
    idea = await solshieldx.generate_post_ideas(topic)
    await ctx.send(f"📝 **Post Idea:**\n{idea}")

@bot.command(name="variants")
@commands.cooldown(1, 60, commands.BucketType.user)
async def tweet_variants(ctx, count: int = 3, *, topic="crypto trends"):
    """
    Generate and send multiple tweet variants.
    Usage: !variants [count] [topic]
    """
    variants = await solshieldx.generate_variants(n=count, topic=topic)
    response_text = "📝 **Tweet Variants:**\n" + "\n".join(f"- {v}" for v in variants)
    await ctx.send(response_text)

@bot.command(name="ask")
@commands.cooldown(1, 30, commands.BucketType.user)
async def ask(ctx, *, question: str):
    """Ask a crypto-related question and get an answer."""
    answer = await solshieldx.ask_question(question)
    await ctx.send(f"❓ **Question:** {question}\n💡 **Answer:** {answer}")

@bot.command(name="news")
@commands.cooldown(1, 60, commands.BucketType.user)
async def crypto_news(ctx):
    """Generate a summary of the current state of the crypto market."""
    news = await solshieldx.generate_crypto_news()
    await ctx.send(f"📰 **Crypto News Summary:**\n{news}")

@bot.command(name="quote")
@commands.cooldown(1, 60, commands.BucketType.user)
async def crypto_quote(ctx):
    """Generate an inspirational crypto-related quote."""
    quote = await solshieldx.generate_crypto_quote()
    await ctx.send(f"💬 **Crypto Quote:**\n{quote}")

@bot.command(name="summarize")
@commands.cooldown(1, 60, commands.BucketType.user)
async def summarize(ctx, url: str):
    """Fetch and summarize the content of a given URL."""
    summary = await solshieldx.summarize_url(url)
    await ctx.send(f"📄 **Summary of {url}:**\n{summary}")

@bot.command(name="analyze")
@commands.cooldown(1, 30, commands.BucketType.user)
async def analyze_tx(ctx, chain: str, tx_hash: str):
    """Analyze a blockchain transaction (use 'solana' or 'eth')."""
    result = await solshieldx.analyze_transaction(chain, tx_hash)
    await ctx.send(f"🔍 **Analysis Result:**\n```{json.dumps(result, indent=2)}```")

@bot.command(name="ping")
async def ping(ctx):
    """Simple test command."""
    await ctx.send("Pong!")

if __name__ == "__main__":
    bot.run(TOKEN)
