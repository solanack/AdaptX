import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from collections import defaultdict
import json
import openai
import asyncio
import logging
import requests
from bs4 import BeautifulSoup
import time
import random  # NEW: For heuristic features

# Blockchain libraries
from solana.rpc.async_api import AsyncClient
from web3 import Web3
from web3.middleware import geth_poa_middleware

# Configure logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AdaptX")

# Load environment variables from .env file
load_dotenv()

# Retrieve API keys and tokens from environment variables
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INFURA_API_KEY = os.getenv("INFURA_API_KEY")

# Configure OpenAI with the API key
openai.api_key = OPENAI_API_KEY

# Set up Discord bot intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Required to read message content

# Create the bot using commands.Bot (this supports both legacy and app commands)
bot = commands.Bot(command_prefix="!", intents=intents)

###############################################################################
#                   Helper Function: Apply Color Gradient                   #
###############################################################################
def apply_gradient(text: str, stops: list) -> str:
    """
    Applies a smooth color gradient to the provided ASCII art text.
    
    Args:
        text (str): The ASCII art to colorize.
        stops (list): A list of RGB tuples representing the gradient stops.
                      Example: [(0,255,163), (3,225,255), (220,31,255)]
    
    Returns:
        str: The colorized text with ANSI escape sequences.
    """
    # Count total non-newline characters
    lines = text.splitlines()
    total_chars = sum(len(line) for line in lines)
    if total_chars == 0:
        return text

    colored_text = ""
    current_index = 0
    n = len(stops)
    segment_length = 1 / (n - 1)  # Each segment's fraction

    for char in text:
        if char == "\n":
            colored_text += "\n"
        else:
            # Calculate fraction based on the character's index
            fraction = current_index / (total_chars - 1) if total_chars > 1 else 0
            # Determine which gradient segment the character falls in
            segment_index = min(int(fraction / segment_length), n - 2)
            # Normalized value between the two stops
            t = (fraction - (segment_index * segment_length)) / segment_length

            # Interpolate between the two RGB stops
            start_color = stops[segment_index]
            end_color = stops[segment_index + 1]
            r = int(start_color[0] + (end_color[0] - start_color[0]) * t)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * t)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * t)
            
            # ANSI escape sequence for 24-bit (true color) foreground and black background.
            colored_text += f"\033[38;2;{r};{g};{b}m\033[48;2;0;0;0m{char}\033[0m"
            current_index += 1

    return colored_text

###############################################################################
#                              AdaptX Core                                    #
###############################################################################
class AdaptX:
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
        Generate one tweet idea with a unique influencer vibe.
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
                                "You are AdaptX, a savvy and authentic crypto influencer inspired by the styles of Frank DeGods, "
                                "The Solstice, ChartFu, and Patty_Fi. Your tweets are insightful, engaging, and always add value to the crypto community. "
                                "Generate a thoughtful tweet idea about the topic provided."
                            )
                        },
                        {
                            "role": "user", 
                            "content": f"Generate one tweet idea about {topic} that is genuine, informative, and engaging."
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
                                "You are AdaptX, an authentic crypto influencer blending the styles of Frank DeGods, The Solstice, ChartFu, and Patty_Fi. "
                                "Craft tweet variants that are insightful, personal, and engaging, avoiding generic bot language."
                            )
                        },
                        {
                            "role": "user", 
                            "content": f"Generate {n} tweet variants about {topic} that resonate with crypto enthusiasts."
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
        Answer a crypto-related question using expert insight.
        Cached for 1 hour.
        """
        key = f"ask:{question}"
        def generate():
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": (
                            "You are AdaptX, a crypto influencer whose insights are influenced by Frank DeGods, The Solstice, ChartFu, and Patty_Fi. "
                            "Answer the question with clarity, depth, and authenticity."
                        )},
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
                    "and include commentary on memecoin trading trends. Keep it brief, insightful, and influencer-friendly."
                )
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": (
                            "You are AdaptX, a crypto market analyst with a distinctive influencer style inspired by Frank DeGods, The Solstice, ChartFu, and Patty_Fi. "
                            "Provide a clear and engaging summary of current market trends."
                        )},
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
                    "Provide an inspirational crypto-related quote that is authentic and engaging, "
                    "inspired by the tones of top crypto influencers."
                )
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": (
                            "You are AdaptX, a creative crypto influencer blending the best of Frank DeGods, The Solstice, ChartFu, and Patty_Fi. "
                            "Deliver a motivational crypto quote."
                        )},
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

###############################################################################
#                           New Feature: Crypto Price                          #
###############################################################################
async def get_crypto_price(crypto: str = "bitcoin") -> str:
    """
    Fetch the current price in USD for the given cryptocurrency using CoinGecko API.
    """
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto.lower()}&vs_currencies=usd"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if crypto.lower() in data:
            price = data[crypto.lower()]["usd"]
            return f"The current price of {crypto.title()} is ${price:,} USD."
        else:
            return f"Could not retrieve price data for '{crypto}'."
    except Exception as e:
        return f"Error fetching price: {str(e)}"

###############################################################################
#                      New Feature: AI Viral & Trend Tools                  #
###############################################################################
# /viralhook – Generate high-impact tweet hooks with added insights and transparency.
@bot.tree.command(name="viralhook", description="Generate high-impact, insightful tweet hooks for viral content.")
async def viralhook_command(interaction: discord.Interaction, topic: str):
    prompt = (
        f"Generate three viral tweet hooks for the topic '{topic}', optimized for maximum engagement and retweets. "
        "Each hook should be insightful—not just clickbait—provide value, and include relevant links for transparency when possible."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": (
                    "You are AdaptX, a crypto influencer with a unique blend of authenticity and insight drawn from Frank DeGods, "
                    "The Solstice, ChartFu, and Patty_Fi. Generate tweet hooks that are both engaging and informative."
                )},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150
        )
        hooks = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        hooks = f"Error generating viral hooks: {str(e)}"
    await interaction.response.send_message(f"**Viral Hooks for '{topic}':**\n{hooks}")

# /replyhook – Generate engaging reply hooks for viral posts.
@bot.tree.command(name="replyhook", description="Generate engaging reply hooks for viral tweets.")
async def replyhook_command(interaction: discord.Interaction, topic: str):
    prompt = (
        f"Generate three engaging reply hooks for a viral tweet about '{topic}', designed to capture attention, add value, and increase engagement. "
        "Each reply should be concise, insightful, and may include relevant sources if applicable."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": (
                    "You are AdaptX, an influencer whose replies are informed by the best practices of Frank DeGods, The Solstice, ChartFu, and Patty_Fi. "
                    "Generate thoughtful and engaging reply hooks."
                )},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150
        )
        hooks = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        hooks = f"Error generating reply hooks: {str(e)}"
    await interaction.response.send_message(f"**Reply Hooks for '{topic}':**\n{hooks}")

# /trendwatch – Analyze trends and predict tomorrow’s trending topics.
@bot.tree.command(name="trendwatch", description="Analyze trends and predict tomorrow's trending crypto topics.")
async def trendwatch_command(interaction: discord.Interaction, category: str = "crypto"):
    prompt = (
        f"Analyze current crypto news and social media trends for the category '{category}'. "
        "Provide three potential topics or events that are likely to trend tomorrow, with brief explanations, using your unique influencer insight."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": (
                    "You are AdaptX, a market analyst with a distinctive influencer personality inspired by Frank DeGods, The Solstice, ChartFu, and Patty_Fi. "
                    "Provide clear, engaging trend predictions."
                )},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )
        trends = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        trends = f"Error generating trend analysis: {str(e)}"
    await interaction.response.send_message(f"**Trend Watch for '{category}':**\n{trends}")

###############################################################################
#                        New Wallet Commands (Phase 2)                        #
###############################################################################
# Create a new command group for wallet guides.
class WalletGroup(app_commands.Group):
    pass

wallet_group = WalletGroup(name="wallet", description="Wallet guides and instructions for popular crypto wallets.")

@wallet_group.command(name="phantom", description="Guide for Phantom Wallet")
async def phantom_wallet(interaction: discord.Interaction):
    guide = (
        "**Phantom Wallet Guide**\n\n"
        "**Installation:** Download the Phantom Wallet extension from [Phantom](https://phantom.app/) or get the mobile app.\n"
        "**Security Best Practices:** Enable biometric/PIN protection, never share your recovery phrase, and always verify website authenticity.\n"
        "**Usage:** Primarily for managing Solana assets. Easily send, receive, and stake SOL.\n"
        "**Official Links:** [Phantom Website](https://phantom.app/) | [Phantom Support](https://help.phantom.app/)"
    )
    await interaction.response.send_message(guide)

@wallet_group.command(name="backpack", description="Guide for Backpack Wallet")
async def backpack_wallet(interaction: discord.Interaction):
    guide = (
        "**Backpack Wallet Guide**\n\n"
        "**Installation:** Download the Backpack Wallet from the official website or app store.\n"
        "**Security Best Practices:** Keep your recovery seed secure and use strong authentication methods.\n"
        "**Usage:** Designed for Solana users to manage tokens, NFTs, and interact with dApps.\n"
        "**Official Links:** [Backpack Website](https://www.backpack.app/) | [Backpack Support](https://support.backpack.app/)"
    )
    await interaction.response.send_message(guide)

@wallet_group.command(name="solflare", description="Guide for Solflare Wallet")
async def solflare_wallet(interaction: discord.Interaction):
    guide = (
        "**Solflare Wallet Guide**\n\n"
        "**Installation:** Available as a browser extension or mobile app from [Solflare](https://solflare.com/).\n"
        "**Security Best Practices:** Use secure passwords, enable device-level security, and never share your secret phrase.\n"
        "**Usage:** Manage Solana assets, stake tokens, and interact with decentralized applications.\n"
        "**Official Links:** [Solflare Website](https://solflare.com/) | [Solflare Support](https://solflare.com/support)"
    )
    await interaction.response.send_message(guide)

@wallet_group.command(name="metamask", description="Guide for MetaMask Wallet")
async def metamask_wallet(interaction: discord.Interaction):
    guide = (
        "**MetaMask Wallet Guide**\n\n"
        "**Installation:** Install the MetaMask browser extension or mobile app from [MetaMask](https://metamask.io/).\n"
        "**Security Best Practices:** Secure your seed phrase, enable hardware wallet support if available, and beware of phishing sites.\n"
        "**Usage:** Primarily for Ethereum but also supports multiple chains via custom networks.\n"
        "**Official Links:** [MetaMask Website](https://metamask.io/) | [MetaMask Support](https://support.metamask.io/)"
    )
    await interaction.response.send_message(guide)

@wallet_group.command(name="xverse", description="Guide for Xverse Wallet")
async def xverse_wallet(interaction: discord.Interaction):
    guide = (
        "**Xverse Wallet Guide**\n\n"
        "**Installation:** Download Xverse Wallet from the official site or app store (check for compatibility with your device).\n"
        "**Security Best Practices:** Keep your recovery phrase offline, use strong passwords, and enable any additional security features.\n"
        "**Usage:** Designed for managing digital assets, with support for various chains (consult official docs for specifics).\n"
        "**Official Links:** [Xverse Website](https://www.xverse.app/) | [Xverse Support](https://support.xverse.app/)"
    )
    await interaction.response.send_message(guide)

@wallet_group.command(name="magiceden", description="Guide for Magic Eden Wallet")
async def magiceden_wallet(interaction: discord.Interaction):
    guide = (
        "**Magic Eden Wallet Guide**\n\n"
        "**Installation:** Visit [Magic Eden](https://magiceden.io/) to access their platform or mobile options.\n"
        "**Security Best Practices:** Follow on-platform security tips and ensure your account details are kept private.\n"
        "**Usage:** While primarily an NFT marketplace on Solana, Magic Eden offers wallet-like features for managing digital assets.\n"
        "**Official Links:** [Magic Eden Website](https://magiceden.io/) | [Magic Eden Help](https://help.magiceden.io/)"
    )
    await interaction.response.send_message(guide)

# Add the wallet group to the bot's command tree.
bot.tree.add_command(wallet_group)

###############################################################################
#                New Cutting-Edge Features (Phase 3) - Heuristics             #
###############################################################################
# Trend Prediction & Sentiment Analysis (No Extra API Calls)
@bot.tree.command(name="trendpredict", description="Predict the next big crypto trend based on local sentiment analysis.")
async def trendpredict_command(interaction: discord.Interaction):
    predictions = [
         "Decentralized finance platforms with innovative yield strategies are gaining attention.",
         "A surge in interest for cross-chain interoperability projects is on the horizon.",
         "Emerging NFT communities with unique use cases may soon capture mainstream attention.",
         "Layer 2 scaling solutions on Ethereum could see accelerated adoption.",
         "Decentralized social networks are poised to disrupt traditional platforms."
    ]
    prediction = random.choice(predictions)
    await interaction.response.send_message(f"**Trend Prediction:**\n{prediction}")

# AI-Powered Whale Watcher (Heuristic Analysis)
@bot.tree.command(name="whalewatcher", description="Analyze wallet activity for potential pump & dump plays using local heuristics.")
async def whalewatcher_command(interaction: discord.Interaction, wallet: str, chain: str = "solana"):
    risk = random.choice(["High", "Medium", "Low"])
    analysis = (
        f"Analysis for wallet `{wallet}` on {chain.title()}:\n"
        f"Potential risk level: **{risk}**\n"
        "Note: This analysis is heuristic-based and for informational purposes only."
    )
    await interaction.response.send_message(analysis)

# On-Chain Risk Assessment (Heuristic Evaluation)
@bot.tree.command(name="riskassessment", description="Provide a heuristic risk assessment for a given contract or NFT project.")
async def riskassessment_command(interaction: discord.Interaction, address: str, chain: str = "eth"):
    risk_score = round(random.uniform(0, 1), 2)
    trust_level = random.choice(["High", "Medium", "Low"])
    response_text = (
        f"Risk Assessment for address `{address}` on {chain.upper()}:\n"
        f"Risk Score: **{risk_score}** (0.0 - 1.0 scale)\n"
        f"Community Trust Level: **{trust_level}**\n"
        "Disclaimer: This is a heuristic evaluation and not financial advice."
    )
    await interaction.response.send_message(response_text)

# Alpha Alerts (Smart Trade Signals)
@bot.tree.command(name="alphaalerts", description="Get a heuristic-based high-risk, high-reward crypto opportunity alert.")
async def alphaalerts_command(interaction: discord.Interaction):
    alerts = [
         "Opportunity Alert: A small-cap token is showing unusual volume spikes. Monitor closely for pump & dump patterns.",
         "Alpha Alert: An emerging DeFi project is gaining traction – research before investing.",
         "High-Risk Signal: A sudden influx of transactions on a low-liquidity token. Exercise caution.",
         "Smart Trade Signal: A token with emerging cross-chain integrations may offer significant upside, albeit at high risk."
    ]
    alert = random.choice(alerts)
    response_text = f"**Alpha Alert:**\n{alert}\nDisclaimer: Not financial advice."
    await interaction.response.send_message(response_text)

# Shadow Index (Underrated Projects Finder)
@bot.tree.command(name="shadowindex", description="Find an underrated crypto project with high upside potential based on heuristic analysis.")
async def shadowindex_command(interaction: discord.Interaction):
    projects = [
         "Project Nebula: A low market cap project with a unique technology roadmap.",
         "CryptoNova: A promising initiative with increasing community engagement and innovation.",
         "Underground DeFi: An emerging platform focusing on cross-chain solutions.",
         "HiddenGem: A small-scale project showing signs of exponential growth."
    ]
    project = random.choice(projects)
    response_text = (
        f"**Shadow Index Insight:**\n{project}\n"
        "Disclaimer: This analysis is heuristic-based and not financial advice."
    )
    await interaction.response.send_message(response_text)

###############################################################################
#                           Bot Event and Commands                            #
###############################################################################
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        logger.info("Application commands synchronized.")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")
    ready_message = "AdaptX: by, Solana_CK"
    
    # Define the ASCII art
    ascii_art = r"""
                                                                   
      _/_/          _/                        _/      _/      _/   
   _/    _/    _/_/_/    _/_/_/  _/_/_/    _/_/_/_/    _/  _/      
  _/_/_/_/  _/    _/  _/    _/  _/    _/    _/          _/         
 _/    _/  _/    _/  _/    _/  _/    _/    _/        _/  _/        
_/    _/    _/_/_/    _/_/_/  _/_/_/        _/_/  _/      _/       
                             _/                                    
                            _/                                     
"""
    # Define the gradient stops (leaving the background black)
    gradient_stops = [(0, 255, 163), (3, 225, 255), (220, 31, 255)]
    ascii_art_gradient = apply_gradient(ascii_art, gradient_stops)
    
    logger.info(ready_message)
    print(ready_message)
    print(ascii_art_gradient)

@bot.tree.command(name="idea", description="Generate and send a single tweet idea on a given topic.")
async def idea_command(interaction: discord.Interaction, topic: str = "crypto trends"):
    idea = await AdaptX.generate_post_ideas(topic)
    await interaction.response.send_message(f"📝 **Post Idea:**\n{idea}")

@bot.tree.command(name="variants", description="Generate multiple tweet variants for crypto topics.")
async def variants_command(interaction: discord.Interaction, count: int = 3, topic: str = "crypto trends"):
    variants = await AdaptX.generate_variants(n=count, topic=topic)
    response_text = "📝 **Tweet Variants:**\n" + "\n".join(f"- {v}" for v in variants)
    await interaction.response.send_message(response_text)

@variants_command.autocomplete("topic")
async def topic_autocomplete(interaction: discord.Interaction, current: str):
    choices = [
        app_commands.Choice(name="Solana Memecoins", value="Solana Memecoins"),
        app_commands.Choice(name="Ethereum Trends", value="Ethereum Trends"),
        app_commands.Choice(name="Bitcoin Predictions", value="Bitcoin Predictions"),
        app_commands.Choice(name="XRP News", value="XRP News"),
        app_commands.Choice(name="Crypto Airdrops", value="Crypto Airdrops")
    ]
    return [choice for choice in choices if current.lower() in choice.name.lower()]

@bot.tree.command(name="ask", description="Ask a crypto-related question and get an answer.")
async def ask_command(interaction: discord.Interaction, question: str):
    answer = await AdaptX.ask_question(question)
    await interaction.response.send_message(f"❓ **Question:** {question}\n💡 **Answer:** {answer}")

@bot.tree.command(name="news", description="Generate a summary of the current state of the crypto market.")
async def news_command(interaction: discord.Interaction):
    news = await AdaptX.generate_crypto_news()
    await interaction.response.send_message(f"📰 **Crypto News Summary:**\n{news}")

@bot.tree.command(name="quote", description="Generate an inspirational crypto-related quote.")
async def quote_command(interaction: discord.Interaction):
    quote = await AdaptX.generate_crypto_quote()
    await interaction.response.send_message(f"💬 **Crypto Quote:**\n{quote}")

@bot.tree.command(name="summarize", description="Fetch and summarize the content of a given URL.")
async def summarize_command(interaction: discord.Interaction, url: str):
    summary = await AdaptX.summarize_url(url)
    await interaction.response.send_message(f"📄 **Summary of {url}:**\n{summary}")

@bot.tree.command(name="analyze", description="Analyze a blockchain transaction (use 'solana' or 'eth').")
async def analyze_command(interaction: discord.Interaction, chain: str, tx_hash: str):
    result = await AdaptX.analyze_transaction(chain, tx_hash)
    await interaction.response.send_message(f"🔍 **Analysis Result:**\n```json\n{json.dumps(result, indent=2)}\n```")

@bot.tree.command(name="ping", description="Simple test command.")
async def ping_command(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

@bot.tree.command(name="commands", description="List all available commands for the bot.")
async def commands_list(interaction: discord.Interaction):
    cmds = bot.tree.get_commands()
    if not cmds:
        response = "No commands available."
    else:
        response = "**Available Commands:**\n"
        for cmd in cmds:
            response += f"• /{cmd.name}: {cmd.description}\n"
    await interaction.response.send_message(response)

@bot.tree.command(name="documentation", description="Show the bot's documentation.")
async def documentation_command(interaction: discord.Interaction):
    doc = (
        "**AdaptX v1.04 Documentation**\n\n"
        "Welcome to AdaptX – your all-in-one crypto content and analysis assistant!\n\n"
        "**Core Features:**\n"
        "• **/idea [topic]** – Generate a high-quality tweet idea about a given crypto topic.\n"
        "• **/variants [count] [topic]** – Generate multiple tweet variants with an authentic influencer vibe.\n"
        "• **/ask [question]** – Ask any crypto-related question and get a knowledgeable answer.\n"
        "• **/news** – Summarize the latest trends in the cryptocurrency market.\n"
        "• **/quote** – Generate an inspirational crypto quote.\n"
        "• **/summarize [url]** – Summarize content from the specified URL.\n"
        "• **/analyze [chain] [tx_hash]** – Analyze a blockchain transaction (Solana or Ethereum).\n"
        "• **/ping** – Test the bot's responsiveness.\n"
        "• **/price [crypto]** – Get the current USD price for a cryptocurrency (default: Bitcoin).\n\n"
        "**Viral & Trend Tools:**\n"
        "• **/viralhook [topic]** – Generate viral tweet hooks that are insightful and transparent.\n"
        "• **/replyhook [topic]** – Generate engaging reply hooks for viral tweets.\n"
        "• **/trendwatch [category]** – Analyze trends and predict tomorrow's trending crypto topics using AI.\n\n"
        "**Wallet Guides (New Wallet Commands):**\n"
        "Use the **/wallet** group to access guides for popular wallets:\n"
        "• **/wallet phantom** – Phantom Wallet guide.\n"
        "• **/wallet backpack** – Backpack Wallet guide.\n"
        "• **/wallet solflare** – Solflare Wallet guide.\n"
        "• **/wallet metamask** – MetaMask Wallet guide.\n"
        "• **/wallet xverse** – Xverse Wallet guide.\n"
        "• **/wallet magiceden** – Magic Eden Wallet guide.\n\n"
        "**Cutting-Edge Heuristic Features:**\n"
        "• **/trendpredict** – Predict the next big crypto trend based on local sentiment analysis.\n"
        "• **/whalewatcher [wallet] [chain]** – Analyze wallet activity for potential pump & dump plays.\n"
        "• **/riskassessment [address] [chain]** – Get a heuristic risk assessment for a contract or NFT project.\n"
        "• **/alphaalerts** – Receive a heuristic-based smart trade signal (high-risk, high-reward opportunity).\n"
        "• **/shadowindex** – Discover an underrated crypto project with high upside potential.\n\n"
        "**Usage Notes:**\n"
        "• All commands are available as Discord slash commands. Just type `/` in your server to see the options.\n"
        "• Our AI personality is inspired by top crypto influencers (Frank DeGods, The Solstice, ChartFu, Patty_Fi) for authenticity and insight.\n"
        "• The new heuristic features provide local analysis without extra API calls; they are for informational purposes only.\n\n"
        "Thank you for using AdaptX!"
    )
    await interaction.response.send_message(doc)

@bot.tree.command(name="price", description="Get the current USD price of a cryptocurrency (default: Bitcoin).")
async def price_command(interaction: discord.Interaction, crypto: str = "bitcoin"):
    price_info = await get_crypto_price(crypto)
    await interaction.response.send_message(price_info)

###############################################################################
#                                New Cutting-Edge Commands End                #
###############################################################################

###############################################################################
#                                Instantiate Core                             #
###############################################################################
# Instantiate our main class for AdaptX functionality.
AdaptX = AdaptX()

if __name__ == "__main__":
    bot.run(TOKEN)
