import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from collections import defaultdict
import json
import tweepy
import openai
import asyncio
import logging

# (Optional) For future scheduling features:
# from apscheduler.schedulers.asyncio import AsyncIOScheduler

from solana.rpc.async_api import AsyncClient
from web3 import Web3
from web3.middleware import geth_poa_middleware

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Retrieve API keys and tokens from environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWITTER_CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
TWITTER_CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
INFURA_API_KEY = os.getenv("INFURA_API_KEY")

# Configure OpenAI with the API key
openai.api_key = OPENAI_API_KEY

# Set up Discord bot intents and command prefix
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Required to read message content
bot = commands.Bot(command_prefix="!", intents=intents)

# (Optional) Set up an AsyncIO scheduler if you later wish to schedule posts
# scheduler = AsyncIOScheduler()
# scheduler.start()

class SolShieldX:
    def __init__(self):
        # Initialize blockchain and social media clients

        # Solana client
        self.solana_client = AsyncClient("https://api.mainnet-beta.solana.com")

        # Ethereum client via Infura
        self.web3_eth = Web3(Web3.HTTPProvider(f"https://mainnet.infura.io/v3/{INFURA_API_KEY}"))
        self.web3_eth.middleware_onion.inject(geth_poa_middleware, layer=0)

        # Twitter v2 client using the Bearer Token (for trend analysis and influencer monitoring)
        self.twitter_client_v2 = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
        
        # (Optional) Twitter v1.1 client if needed for other features
        self.twitter_auth = tweepy.OAuth1UserHandler(
            TWITTER_CONSUMER_KEY,
            TWITTER_CONSUMER_SECRET,
            TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_TOKEN_SECRET
        )
        self.twitter_client_v1 = tweepy.API(self.twitter_auth)

        # Hard-coded list of influencer usernames to monitor (replace with real Twitter handles)
        self.influencers = ["influencer1", "influencer2", "influencer3"]

        # Threat detection data (using a default dictionary)
        self.threat_db = defaultdict(set)
        self.load_threat_data()

    def load_threat_data(self):
        """Load threat data from a JSON file."""
        try:
            with open("threat_feeds.json") as f:
                data = json.load(f)
                self.threat_db.update(data.get("addresses", {}))
        except Exception as e:
            logger.warning(f"Error loading threat data: {e}")

    async def generate_post_ideas(self):
        """
        Generate a single high-quality social media post idea using GPT-3.5-turbo.
        Offloads the synchronous OpenAI call to a separate thread.
        Uses dictionary indexing to access the response.
        """
        def sync_generate():
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a creative social media strategist. "
                                "Generate an engaging tweet idea about blockchain security trends that is concise and optimized for high impressions."
                            )
                        },
                        {
                            "role": "user",
                            "content": "Generate one tweet idea about blockchain security trends."
                        }
                    ],
                    max_tokens=100
                )
                # Use dictionary indexing to extract the generated idea
                idea = response["choices"][0]["message"]["content"].strip()
                return idea
            except Exception as e:
                return f"⚠️ Error generating ideas: {str(e)}"
        idea = await asyncio.to_thread(sync_generate)
        logger.info("Generated post idea successfully.")
        return idea

    async def generate_variants(self, n=3):
        """
        Generate multiple tweet variants to allow A/B testing.
        Offloads the synchronous OpenAI call to a separate thread.
        Returns a list of variant strings.
        """
        def sync_generate_variants():
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a creative social media strategist. "
                                "Generate multiple concise and engaging tweet variants about blockchain security trends optimized for high engagement and impressions."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"Generate {n} tweet variants about blockchain security trends. Separate each variant with a newline."
                        }
                    ],
                    max_tokens=150
                )
                text = response["choices"][0]["message"]["content"].strip()
                variants = [variant.strip() for variant in text.split("\n") if variant.strip()]
                return variants
            except Exception as e:
                return [f"⚠️ Error generating variants: {str(e)}"]
        variants = await asyncio.to_thread(sync_generate_variants)
        logger.info("Generated tweet variants successfully.")
        return variants

    async def find_crypto_trends(self):
        """Fetch trending crypto topics from Twitter using v2 endpoints."""
        try:
            response = self.twitter_client_v2.search_recent_tweets(
                query="blockchain OR crypto OR web3 -is:retweet",
                max_results=10
            )
            if response.data:
                tweets = [tweet.text for tweet in response.data]
            else:
                tweets = ["No trends found"]
            logger.info("Fetched trending topics successfully.")
            return tweets
        except Exception as e:
            logger.error(f"Twitter API error: {e}")
            return [f"⚠️ Twitter error: {str(e)}"]

    async def get_influencer_activity(self):
        """
        Retrieve the latest tweet from each influencer in the hard-coded list.
        Uses Twitter API v2 to get user tweets.
        """
        influencer_tweets = {}
        for username in self.influencers:
            try:
                user_response = self.twitter_client_v2.get_user(username=username)
                if user_response.data is None:
                    influencer_tweets[username] = "User not found or inaccessible."
                    continue
                user_id = user_response.data.id
                tweets_response = self.twitter_client_v2.get_users_tweets(user_id, max_results=1)
                if tweets_response.data:
                    influencer_tweets[username] = tweets_response.data[0].text
                else:
                    influencer_tweets[username] = "No recent tweets."
            except Exception as e:
                influencer_tweets[username] = f"Error: {e}"
        logger.info("Fetched influencer activity successfully.")
        return influencer_tweets

    async def analyze_transaction(self, chain: str, tx_hash: str):
        """Analyze a blockchain transaction (Solana or Ethereum)."""
        try:
            if chain.lower() == "solana":
                tx = await self.solana_client.get_transaction(tx_hash)
                return {"chain": chain, "risk_score": 0.5}  # Simplified analysis
            elif chain.lower() == "eth":
                tx = self.web3_eth.eth.get_transaction(tx_hash)
                return {"chain": chain, "risk_score": 0.5}  # Simplified analysis
            return {"error": "Unsupported chain"}
        except Exception as e:
            logger.error(f"Error analyzing transaction: {e}")
            return {"error": str(e)}

# Instantiate our main class
solshieldx = SolShieldX()

@bot.event
async def on_ready():
    logger.info(f'✅ Bot ready: {bot.user.name}')
    print(f'✅ Bot ready: {bot.user.name}')

@bot.command(name="idea")
async def post_idea(ctx):
    """Generate and send a single tweet idea."""
    idea = await solshieldx.generate_post_ideas()
    await ctx.send(f"📝 **Post Idea:**\n{idea}")

@bot.command(name="variants")
async def tweet_variants(ctx, count: int = 3):
    """
    Generate and send multiple tweet variants.
    Usage: !variants [count]
    """
    variants = await solshieldx.generate_variants(n=count)
    response_text = "📝 **Tweet Variants:**\n" + "\n".join(f"- {v}" for v in variants)
    await ctx.send(response_text)

@bot.command(name="trends")
async def find_trends(ctx):
    """Display trending crypto topics."""
    trends = await solshieldx.find_crypto_trends()
    await ctx.send("📈 **Trending Topics:**\n" + "\n\n".join(trends))

@bot.command(name="influencers")
async def influencer_activity(ctx):
    """Display the latest tweet from each influencer."""
    activity = await solshieldx.get_influencer_activity()
    response_lines = ["👥 **Influencer Activity:**"]
    for username, tweet in activity.items():
        response_lines.append(f"**{username}**: {tweet}")
    await ctx.send("\n".join(response_lines))

@bot.command(name="analyze")
async def analyze_tx(ctx, chain: str, tx_hash: str):
    """Analyze a blockchain transaction (use 'solana' or 'eth')."""
    result = await solshieldx.analyze_transaction(chain, tx_hash)
    await ctx.send(f"🔍 **Analysis Result:**\n```{json.dumps(result, indent=2)}```")

@bot.command(name="ping")
async def ping(ctx):
    """Simple test command."""
    await ctx.send("Pong!")

# (Optional) Example of scheduling a tweet generation every hour:
# async def scheduled_tweet():
#     idea = await solshieldx.generate_post_ideas()
#     logger.info(f"Scheduled Tweet Idea: {idea}")
# scheduler.add_job(scheduled_tweet, 'interval', hours=1)

if __name__ == "__main__":
    bot.run(TOKEN)
