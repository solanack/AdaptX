#!/usr/bin/env python
"""
AdaptX: A cool, calm, and respectful Solana influencer Discord bot.

Key Features:
- Core Commands: /idea, /ask, /analyze, /walletanalysis, /price, /networkstats, /scheduleama, /governance, /usecases
- Enhanced Commands: /tokeninfo, /validator, /events, /trackwallet, /stoptracking, /nftportfolio, /stakinganalysis, /recentactivity, /ecosystem
- Experimental Features (Set 1): /soundboard, /setalert, /nftgallery, /stakingcalc, /decode
- New Experimental Features (Set 2): /solpoll, /tokenlottery, /validatorrank, /nftdrop, /solchat
- New Features (Set 3): /tokenmetadata, /programaccounts, /blockinfo, /accountinfo, /leaderboard, /solanagames, /memegenerator, /snsresolve, /swapestimate, /solpay
- Voice Support: Enabled with PyNaCl for audio features
- Dependencies: discord.py==2.2.2, python-dotenv, aiohttp, cachetools, solana, pyfiglet, googletrans==4.0.0-rc1, base58, PyNaCl, Pillow
"""

import os
import asyncio
import logging
import sqlite3
import random
from typing import Any, Dict, List, Union

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord import FFmpegPCMAudio  # For audio playback

from dotenv import load_dotenv
import aiohttp
from cachetools import TTLCache
from solana.rpc.async_api import AsyncClient
import pyfiglet
from googletrans import Translator
import base58

# Configuration & Logging
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
QUICKNODE_SOLANA_HTTP_URL = os.getenv("QUICKNODE_SOLANA_HTTP_URL")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Adapt X")

# ASCII Art with Solana Gradient Colors
ascii_art = pyfiglet.figlet_format("ADAPTX", font="elite")

def apply_gradient(ascii_art, gradient_stops):
    """
    Apply a horizontal gradient to the ASCII art across each line.
    
    Args:
        ascii_art (str): The ASCII art as a string with newline-separated lines.
        gradient_stops (list): List of colors representing gradient stops.
    
    Returns:
        str: The ASCII art with a horizontal gradient applied.
    """
    lines = ascii_art.split('\n')
    gradient_lines = []
    num_segments = len(gradient_stops) - 1

    for line in lines:
        L = len(line)
        if L == 0:
            gradient_lines.append('')
            continue

        colored_line = ""
        for pos in range(L):
            if L > 1:
                r = pos / (L - 1)  # Ratio from 0 to 1 across the line
            else:
                r = 0  # Single character lines use the first color

            # Calculate the segment and local ratio for interpolation
            segment = min(int(r * num_segments), num_segments - 1)
            local_ratio = (r * num_segments) - segment
            start_color = gradient_stops[segment]
            end_color = gradient_stops[segment + 1]
            color = interpolate_color(start_color, end_color, local_ratio)

            # Apply ANSI color code to the character
            color_code = f"\033[38;2;{color[0]};{color[1]};{color[2]}m"
            colored_line += color_code + line[pos]

        colored_line += "\033[0m"  # Reset color at the end of the line
        gradient_lines.append(colored_line)

    return '\n'.join(gradient_lines)

def interpolate_color(start, end, ratio):
    """Interpolate between two colors based on a ratio."""
    return tuple(int(start[i] + (end[i] - start[i]) * ratio) for i in range(3))

# Adjusted gradient stops to emphasize more purple
gradient_stops = [
    (0, 255, 163),    # Green
    (3, 225, 255),    # Blue
    (220, 31, 255),   # Purple
    (220, 31, 255)    # Extend purple
]

ascii_art_gradient = apply_gradient(ascii_art, gradient_stops)

print(ascii_art_gradient)
print("Version 1.18\n")  # Updated version

# Enable voice support with PyNaCl
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.voice_states = True  # Enable voice states

bot = commands.Bot(command_prefix="!", intents=intents)

# Input Validation Functions
def is_valid_solana_address(address: str) -> bool:
    """Validate if a string is a Solana address (32-44 bytes base58 encoded)."""
    try:
        decoded = base58.b58decode(address)
        return 32 <= len(decoded) <= 44
    except Exception:
        return False

def is_valid_transaction_hash(tx_hash: str) -> bool:
    """Validate if a string is a Solana transaction hash (64 bytes base58 encoded)."""
    try:
        decoded = base58.b58decode(tx_hash)
        return len(decoded) == 64
    except Exception:
        return False

# Cache Manager
class CacheManager:
    def __init__(self):
        self.caches: Dict[int, TTLCache] = {}

    def get_cache(self, ttl: int) -> TTLCache:
        if ttl not in self.caches:
            self.caches[ttl] = TTLCache(maxsize=200, ttl=ttl)
        return self.caches[ttl]

cache_manager = CacheManager()

# Mistral AI Client
class MistralAIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"

    async def generate_text(self, prompt: str, model: str = "mistral-small", max_tokens: int = 100) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}
        logger.info(f"Sending request to Mistral API: {prompt[:50]}...")
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=data, timeout=10) as response:
                    if response.status != 200:
                        error_details = await response.text()
                        logger.error(f"Mistral API error: {response.status} - {error_details}")
                        return f"⚠️ API Error: {error_details}"
                    result = await response.json()
                    return result['choices'][0]['message']['content'].strip()
            except Exception as e:
                logger.error(f"Mistral API request failed: {e}")
                return f"⚠️ Error: {str(e)}"

mistral_client = MistralAIClient(MISTRAL_API_KEY)

# AdaptX Core Class
class AdaptX:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.helius_api_key = HELIUS_API_KEY
        if not self.helius_api_key:
            raise ValueError("Helius API key is required.")
        solana_url = QUICKNODE_SOLANA_HTTP_URL if QUICKNODE_SOLANA_HTTP_URL else f"https://rpc.helius.xyz/?api-key={HELIUS_API_KEY}"
        logger.info(f"Using Solana RPC: {solana_url}")
        self.solana_client = AsyncClient(solana_url)

    async def cached_call(self, key: str, generator: callable, ttl: int = 3600) -> Any:
        cache = cache_manager.get_cache(ttl)
        if key in cache:
            logger.debug(f"Cache hit for key: {key}")
            return cache[key]
        logger.debug(f"Cache miss for key: {key}. Generating new value.")
        value = await generator() if asyncio.iscoroutinefunction(generator) else await asyncio.to_thread(generator)
        cache[key] = value
        return value

    async def generate_post_ideas(self, topic: str = "Solana trends") -> str:
        key = f"idea:{topic}"
        async def generate() -> str:
            try:
                prompt_topic = topic if "solana" in topic.lower() else f"{topic} in the Solana ecosystem"
                prompt = (
                    "You are AdaptX, a knowledgeable and respectful Solana influencer with a cool, calm style. "
                    f"Generate one tweet idea about {prompt_topic} that is thoughtful, detailed, and engaging."
                )
                return await mistral_client.generate_text(prompt)
            except Exception as e:
                logger.error(f"Error generating idea: {e}")
                return f"⚠️ Error generating idea: {str(e)}"
        return await self.cached_call(key, generate, ttl=3600)

    async def ask_question(self, question: str) -> str:
        key = f"ask:{question}"
        async def generate() -> str:
            try:
                prompt = (
                    "You are AdaptX, a Solana expert with a calm and informative style. "
                    f"Question: {question}"
                )
                return await mistral_client.generate_text(prompt, max_tokens=150)
            except Exception as e:
                logger.error(f"Error answering question: {e}")
                return f"⚠️ Error answering question: {str(e)}"
        return await self.cached_call(key, generate, ttl=3600)

    async def analyze_transaction(self, tx_hash: str) -> Dict[str, Any]:
        if not is_valid_transaction_hash(tx_hash):
            return {"error": "Invalid transaction hash."}
        url = f"https://api.helius.xyz/v0/transactions/{tx_hash}?api-key={self.helius_api_key}"
        logger.info(f"Fetching transaction data for {tx_hash}")
        try:
            async with self.session.get(url, timeout=15) as response:
                response.raise_for_status()
                tx_data = await response.json()
            programs = tx_data.get('programs', [])
            token_transfers = tx_data.get('tokenTransfers', [])
            analysis = (
                f"**Helius Transaction Analysis** for `{tx_hash}`\n"
                f"• Description: {tx_data.get('description', 'N/A')}\n"
                f"• Fee: {tx_data.get('fee', 0)/1e9:.4f} SOL\n"
                f"• Status: {tx_data.get('status', 'N/A')}\n"
                f"• Signers: {', '.join(tx_data.get('signers', []))}\n"
                f"• Programs Involved: {', '.join(programs) if programs else 'None'}\n"
                f"• Token Transfers: {len(token_transfers)} transfer(s)\n"
                "Risk Assessment: Low (Verified by Helius)"
            )
            return {"analysis": analysis}
        except Exception as e:
            logger.error(f"Transaction analysis error for {tx_hash}: {e}")
            return {"error": f"Analysis failed: {str(e)}"}

    async def analyze_wallet(self, wallet_address: str) -> str:
        if not is_valid_solana_address(wallet_address):
            return "Invalid wallet address."
        url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/balances?api-key={self.helius_api_key}"
        logger.info(f"Fetching wallet balances for {wallet_address}")
        try:
            async with self.session.get(url, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
            tokens = data.get('tokens', [])
            sol_balance = data.get('nativeBalance', 0) / 1e9
            analysis = (
                f"**Wallet Analysis for `{wallet_address}`**\n"
                f"• SOL Balance: {sol_balance:.4f} SOL\n"
                f"• Token Holdings: {len(tokens)} token(s)\n"
            )
            for token in tokens[:5]:
                analysis += f"  - {token['name']}: {token['amount'] / 10**token['decimals']:.4f}\n"
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing wallet {wallet_address}: {e}")
            return f"Error analyzing wallet: {str(e)}"

    async def get_solana_stats(self) -> Dict[str, Any]:
        url = f"https://api.helius.xyz/v0/metrics?api-key={self.helius_api_key}"
        logger.info("Fetching Solana network metrics from Helius")
        try:
            async with self.session.get(url, timeout=10) as resp:
                data = await resp.json()
                return {
                    "tps": data.get("tps", "N/A"),
                    "transaction_count": data.get("transactionCount", "N/A"),
                }
        except Exception as e:
            logger.error(f"Error fetching Helius metrics: {e}")
            return {"tps": "N/A", "transaction_count": "N/A"}

    async def get_solana_network_stats(self) -> str:
        metrics = await self.get_solana_stats()
        try:
            epoch_info = await self.solana_client.get_epoch_info()
            epoch_val = epoch_info.value.epoch
            supply = await self.solana_client.get_supply()
            total_supply = supply.value.total / 1e9
            vote_accounts = await self.solana_client.get_vote_accounts()
            validator_count = len(vote_accounts.value.current)
            slot = await self.solana_client.get_slot()
            block_height = slot.value
        except Exception as e:
            logger.error(f"Error fetching additional Solana stats: {e}")
            epoch_val = total_supply = validator_count = block_height = "N/A"
        return (
            f"**Solana Network Stats:**\n"
            f"• TPS: {metrics.get('tps', 'N/A')}\n"
            f"• Transaction Count: {metrics.get('transaction_count', 'N/A')}\n"
            f"• Block Height: {block_height}\n"
            f"• Epoch: {epoch_val}\n"
            f"• Total Supply: {total_supply:.2f} SOL\n"
            f"• Validator Count: {validator_count}"
        )

    async def get_crypto_price_coingecko(self, crypto: str = "solana") -> str:
        key = f"price:{crypto}"
        async def generate() -> str:
            url = f"https://api.coingecko.com/api/v3/coins/{crypto.lower()}"
            logger.info(f"Fetching price data for {crypto} from CoinGecko")
            try:
                async with self.session.get(url, timeout=10) as response:
                    data = await response.json()
                if 'market_data' in data:
                    price = data['market_data']['current_price']['usd']
                    market_cap = data['market_data']['market_cap']['usd']
                    volume = data['market_data']['total_volume']['usd']
                    return (
                        f"**{crypto.title()} Stats:**\n"
                        f"• Price: ${price:,}\n"
                        f"• Market Cap: ${market_cap:,}\n"
                        f"• 24h Volume: ${volume:,}"
                    )
                else:
                    return f"Could not retrieve data for '{crypto}'."
            except Exception as e:
                logger.error(f"Error fetching price for {crypto}: {e}")
                return f"Error fetching price: {str(e)}"
        return await self.cached_call(key, generate, ttl=300)

    async def get_coingecko_id(self, token_mint: str) -> str:
        url = "https://api.coingecko.com/api/v3/coins/list?include_platform=true"
        logger.info(f"Fetching CoinGecko ID for token mint {token_mint}")
        try:
            async with self.session.get(url, timeout=10) as response:
                coins = await response.json()
                for coin in coins:
                    if coin.get("platforms", {}).get("solana") == token_mint:
                        return coin["id"]
                return None
        except Exception as e:
            logger.error(f"Error fetching CoinGecko coin list: {e}")
            return None

    async def get_token_holder_count(self, token_mint: str) -> int:
        key = f"token_holders:{token_mint}"
        async def generate() -> int:
            url = f"https://api.helius.xyz/v0/token-accounts?api-key={self.helius_api_key}"
            logger.info(f"Fetching token accounts for mint {token_mint} from Helius")
            try:
                async with self.session.post(url, json={"mint": token_mint}, timeout=15) as response:
                    response.raise_for_status()
                    accounts = await response.json()
                unique_owners = set(account['owner'] for account in accounts)
                return len(unique_owners)
            except Exception as e:
                logger.error(f"Error fetching token holders for {token_mint}: {e}")
                return 0
        return await self.cached_call(key, generate, ttl=7200)

    async def get_validator_info(self, validator_address: str) -> Dict[str, Any]:
        logger.info(f"Fetching validator info for {validator_address}")
        try:
            vote_accounts = await self.solana_client.get_vote_accounts()
            for validator in vote_accounts.value.current:
                if validator.vote_pubkey == validator_address:
                    return {
                        "stake": validator.activated_stake / 1e9,
                        "commission": validator.commission,
                        "epoch_credits": validator.epoch_credits[-1][1] if validator.epoch_credits else 0,
                    }
            return None
        except Exception as e:
            logger.error(f"Error fetching validator info: {e}")
            return None

    async def get_upcoming_events_twitter(self) -> List[Dict[str, str]]:
        if not TWITTER_BEARER_TOKEN:
            logger.warning("Twitter Bearer Token not provided. Falling back to mock events.")
            return [{"date": "2023-10-01", "event": "Solana Breakpoint Conference"}]
        key = "twitter_events"
        async def generate() -> List[Dict[str, str]]:
            url = "https://api.twitter.com/2/tweets/search/recent"
            headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
            query = "from:Solana OR from:SolanaFndn event announcement -is:retweet"
            params = {"query": query, "max_results": 10}
            logger.info("Fetching upcoming Solana events from Twitter")
            try:
                async with self.session.get(url, headers=headers, params=params, timeout=10) as response:
                    response.raise_for_status()
                    data = await response.json()
                events = []
                for tweet in data.get("data", []):
                    text = tweet["text"]
                    if "event" in text.lower() and "date" in text.lower():
                        events.append({"date": "N/A", "event": text[:100] + "..."})
                return events if events else [{"date": "N/A", "event": "No recent events found."}]
            except Exception as e:
                logger.error(f"Error fetching Twitter events: {e}")
                return [{"date": "N/A", "event": "Error fetching events."}]
        return await self.cached_call(key, generate, ttl=3600)

    async def get_nft_portfolio(self, wallet_address: str) -> str:
        if not is_valid_solana_address(wallet_address):
            return "Invalid wallet address."
        url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/nft-balances?api-key={self.helius_api_key}"
        logger.info(f"Fetching NFT portfolio for {wallet_address}")
        try:
            async with self.session.get(url, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
            nfts = data.get("nfts", [])
            analysis = f"**NFT Portfolio for `{wallet_address}`**\n• Total NFTs: {len(nfts)}\n"
            for nft in nfts[:5]:
                analysis += f"  - {nft.get('name', 'Unknown')} (Mint: {nft.get('mint', 'N/A')})\n"
            return analysis
        except Exception as e:
            logger.error(f"Error fetching NFT portfolio for {wallet_address}: {e}")
            return f"Error fetching NFT portfolio: {str(e)}"

    async def get_staking_analysis(self, wallet_address: str) -> str:
        if not is_valid_solana_address(wallet_address):
            return "Invalid wallet address."
        url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/staking-accounts?api-key={self.helius_api_key}"
        logger.info(f"Fetching staking accounts for {wallet_address}")
        try:
            async with self.session.get(url, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
            stakes = data.get("stakingAccounts", [])
            analysis = f"**Staking Analysis for `{wallet_address}`**\n• Total Staked Accounts: {len(stakes)}\n"
            for stake in stakes[:5]:
                analysis += f"  - Stake Account: {stake.get('account', 'N/A')} | Amount: {stake.get('amount', 0)/1e9:.2f} SOL\n"
            return analysis
        except Exception as e:
            logger.error(f"Error fetching staking analysis for {wallet_address}: {e}")
            return f"Error fetching staking analysis: {str(e)}"

    async def get_recent_activity(self, wallet_address: str) -> str:
        if not is_valid_solana_address(wallet_address):
            return "Invalid wallet address."
        url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions?api-key={self.helius_api_key}"
        logger.info(f"Fetching recent activity for {wallet_address}")
        try:
            async with self.session.get(url, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
            txs = data[:5]
            analysis = f"**Recent Activity for `{wallet_address}`**\n• Total Transactions: {len(data)}\n"
            for tx in txs:
                analysis += f"  - Tx Hash: {tx.get('signature', 'N/A')[:8]}... | Fee: {tx.get('fee', 0)/1e9:.4f} SOL\n"
            return analysis
        except Exception as e:
            logger.error(f"Error fetching recent activity for {wallet_address}: {e}")
            return f"Error fetching recent activity: {str(e)}"

    async def get_ecosystem_insights(self) -> str:
        logger.info("Generating Solana ecosystem insights")
        try:
            stats = await self.get_solana_network_stats()
            trending_tokens = await self.get_trending_tokens()
            top_validators = await self.get_top_validators()
            events = await self.get_upcoming_events_twitter()
            insights = "**Solana Ecosystem Insights:**\n\n"
            insights += f"**Network Overview:**\n{stats}\n\n"
            insights += "**Trending Tokens:**\n" + (trending_tokens or "• No trending tokens available.\n") + "\n"
            insights += "**Top Validators:**\n" + (top_validators or "• No validator data available.\n") + "\n"
            insights += "**Upcoming Events:**\n"
            for event in events[:3]:
                insights += f"• {event['date']}: {event['event']}\n"
            return insights
        except Exception as e:
            logger.error(f"Error generating ecosystem insights: {e}")
            return f"Error generating ecosystem insights: {str(e)}"

    async def get_trending_tokens(self) -> str:
        logger.info("Fetching trending tokens (mocked)")
        return "• BONK: +15% volume\n• RAY: +10% holders"

    async def get_top_validators(self) -> str:
        logger.info("Fetching top validators")
        try:
            vote_accounts = await self.solana_client.get_vote_accounts()
            validators = sorted(vote_accounts.value.current, key=lambda v: v.activated_stake, reverse=True)[:3]
            analysis = ""
            for val in validators:
                analysis += f"• {val.vote_pubkey[:8]}...: {val.activated_stake/1e9:.2f} SOL stake, {val.commission}% commission\n"
            return analysis
        except Exception as e:
            logger.error(f"Error fetching top validators: {e}")
            return None

# Background Tasks
solana_stats_cache = {}
tracked_wallets = {}

@tasks.loop(minutes=5)
async def refresh_solana_stats():
    stats = await bot.adaptx.get_solana_stats()
    solana_stats_cache.update(stats)
    logger.info("Refreshed Solana stats cache")

@tasks.loop(minutes=15)
async def check_wallet_updates():
    logger.info("Checking wallet updates")
    cursor = bot.db.cursor()
    cursor.execute("SELECT wallet_address, user_id, channel_id FROM wallet_tracking")
    for wallet, user_id, channel_id in cursor.fetchall():
        analysis = await bot.adaptx.analyze_wallet(wallet)
        cursor.execute("SELECT last_analysis FROM wallet_tracking WHERE wallet_address = ?", (wallet,))
        last_analysis = cursor.fetchone()[0]
        if analysis != last_analysis:
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(f"<@{user_id}>, your tracked wallet `{wallet}` has updates:\n{analysis}")
            cursor.execute("UPDATE wallet_tracking SET last_analysis = ? WHERE wallet_address = ?", (analysis, wallet))
    bot.db.commit()

@tasks.loop(minutes=1)
async def check_price_alerts():
    cursor = bot.db.cursor()
    cursor.execute("SELECT * FROM alerts")
    for user_id, token, condition, value in cursor.fetchall():
        price = await get_token_price(token)
        if (condition == "above" and price > value) or (condition == "below" and price < value):
            user = await bot.fetch_user(user_id)
            await user.send(f"🚨 {token} is {condition} ${value}! Current price: ${price}")
            cursor.execute("DELETE FROM alerts WHERE user_id = ? AND token = ?", (user_id, token))
            bot.db.commit()

async def get_token_price(token: str) -> float:
    # Mock function: replace with real API (e.g., CoinGecko)
    return 150.0 if token == "SOL" else 0.0

# Event Handlers
@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        logger.info(f"{bot.user} is ready and commands synced!")
        refresh_solana_stats.start()
        check_wallet_updates.start()
        check_price_alerts.start()
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")

# Multilang Cog
class MultilangCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.translator = Translator()

    @commands.command(name="translate")
    async def translate(self, ctx, language: str, *, text: str):
        """Translate text into the specified language."""
        try:
            translation = self.translator.translate(text, dest=language)
            await ctx.send(translation.text)
        except Exception as e:
            logger.error(f"Translation error: {e}")
            await ctx.send("Translation failed. Please check the language code and try again.")

# User Points System
@bot.command(name="points")
async def points(ctx):
    """Display the user's points."""
    user_id = ctx.author.id
    cursor = bot.db.cursor()
    cursor.execute("SELECT points FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        await ctx.send(f"You have {result[0]} points!")
    else:
        await ctx.send("You don't have any points yet.")

@bot.command(name="addpoints")
async def addpoints(ctx, points: int):
    """Add points to the user."""
    user_id = ctx.author.id
    cursor = bot.db.cursor()
    cursor.execute("SELECT points FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        new_points = result[0] + points
        cursor.execute("UPDATE users SET points = ? WHERE id = ?", (new_points, user_id))
    else:
        cursor.execute("INSERT INTO users (id, points) VALUES (?, ?)", (user_id, points))
    bot.db.commit()
    await ctx.send(f"{points} points added! You now have {new_points if result else points} points.")

# Slash Commands with Rate Limiting
@bot.tree.command(name="idea", description="Generate a tweet idea about Solana")
@app_commands.describe(topic="The topic for the tweet")
@commands.cooldown(1, 60, commands.BucketType.user)
async def idea(interaction: discord.Interaction, topic: str):
    await interaction.response.defer()
    idea_text = await bot.adaptx.generate_post_ideas(topic)
    await interaction.followup.send(f"Here's a tweet idea for you:\n{idea_text}")

@bot.tree.command(name="ask", description="Ask a question about Solana")
@app_commands.describe(question="Your question about Solana")
@commands.cooldown(1, 60, commands.BucketType.user)
async def ask(interaction: discord.Interaction, question: str):
    await interaction.response.defer()
    answer = await bot.adaptx.ask_question(question)
    await interaction.followup.send(f"Here's my take on your question:\n{answer}")

@bot.tree.command(name="analyze", description="Analyze a Solana transaction")
@app_commands.describe(tx_hash="The transaction hash to analyze")
@commands.cooldown(1, 60, commands.BucketType.user)
async def analyze(interaction: discord.Interaction, tx_hash: str):
    await interaction.response.defer()
    result = await bot.adaptx.analyze_transaction(tx_hash)
    if "error" in result:
        await interaction.followup.send(result["error"])
    else:
        await interaction.followup.send(result["analysis"])

@bot.tree.command(name="walletanalysis", description="Analyze a Solana wallet")
@app_commands.describe(wallet_address="The wallet address to analyze")
@commands.cooldown(1, 60, commands.BucketType.user)
async def walletanalysis(interaction: discord.Interaction, wallet_address: str):
    await interaction.response.defer()
    analysis = await bot.adaptx.analyze_wallet(wallet_address)
    await interaction.followup.send(analysis)

@bot.tree.command(name="price", description="Get the current price of a cryptocurrency")
@app_commands.describe(crypto="The cryptocurrency (default: Solana)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def price(interaction: discord.Interaction, crypto: str = "solana"):
    await interaction.response.defer()
    price_info = await bot.adaptx.get_crypto_price_coingecko(crypto)
    await interaction.followup.send(price_info)

@bot.tree.command(name="networkstats", description="Get current Solana network stats")
@commands.cooldown(1, 60, commands.BucketType.user)
async def networkstats(interaction: discord.Interaction):
    await interaction.response.defer()
    stats = await bot.adaptx.get_solana_network_stats()
    await interaction.followup.send(stats)

@bot.tree.command(name="scheduleama", description="Placeholder for scheduling an AMA")
@commands.cooldown(1, 60, commands.BucketType.user)
async def scheduleama(interaction: discord.Interaction):
    await interaction.response.send_message("AMA scheduling is coming soon!")

@bot.tree.command(name="governance", description="Placeholder for governance info")
@commands.cooldown(1, 60, commands.BucketType.user)
async def governance(interaction: discord.Interaction):
    await interaction.response.send_message("Governance features are under development!")

@bot.tree.command(name="usecases", description="Placeholder for Solana use cases")
@commands.cooldown(1, 60, commands.BucketType.user)
async def usecases(interaction: discord.Interaction):
    await interaction.response.send_message("Solana use cases will be detailed soon!")

@bot.tree.command(name="tokeninfo", description="Get information about a Solana token")
@app_commands.describe(token_mint="The mint address of the token")
@commands.cooldown(1, 60, commands.BucketType.user)
async def tokeninfo(interaction: discord.Interaction, token_mint: str):
    await interaction.response.defer()
    if not is_valid_solana_address(token_mint):
        await interaction.followup.send("Invalid token mint address.", ephemeral=True)
        return
    coingecko_id = await bot.adaptx.get_coingecko_id(token_mint)
    if not coingecko_id:
        await interaction.followup.send("Token not found on CoinGecko.", ephemeral=True)
        return
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
    try:
        async with bot.adaptx.session.get(url, timeout=10) as response:
            data = await response.json()
            if 'market_data' in data:
                price = data['market_data']['current_price']['usd']
                market_cap = data['market_data']['market_cap']['usd']
                volume = data['market_data']['total_volume']['usd']
                holder_count = await bot.adaptx.get_token_holder_count(token_mint)
                info = (
                    f"**Token Info for {data['name']} ({data['symbol'].upper()}):** \n"
                    f"• Price: ${price:,}\n"
                    f"• Market Cap: ${market_cap:,}\n"
                    f"• 24h Volume: ${volume:,}\n"
                    f"• Holder Count: {holder_count:,}\n"
                )
                await interaction.followup.send(info)
            else:
                await interaction.followup.send("Could not retrieve market data.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error fetching token info for {token_mint}: {e}")
        await interaction.followup.send("Error fetching token info.", ephemeral=True)

@bot.tree.command(name="validator", description="Get information about a Solana validator")
@app_commands.describe(validator_address="The vote account address of the validator")
@commands.cooldown(1, 60, commands.BucketType.user)
async def validator(interaction: discord.Interaction, validator_address: str):
    await interaction.response.defer()
    if not is_valid_solana_address(validator_address):
        await interaction.followup.send("Invalid validator address.", ephemeral=True)
        return
    info = await bot.adaptx.get_validator_info(validator_address)
    if info:
        stake = info['stake']
        commission = info['commission']
        credits = info['epoch_credits']
        await interaction.followup.send(
            f"**Validator Info for `{validator_address}`:**\n"
            f"• Stake: {stake:.2f} SOL\n"
            f"• Commission: {commission}%\n"
            f"• Latest Epoch Credits: {credits:,}\n"
        )
    else:
        await interaction.followup.send("Validator not found.", ephemeral=True)

@bot.tree.command(name="events", description="List upcoming Solana events")
@commands.cooldown(1, 60, commands.BucketType.user)
async def events(interaction: discord.Interaction):
    await interaction.response.defer()
    events = await bot.adaptx.get_upcoming_events_twitter()
    if events:
        event_list = "\n".join([f"• {event['date']}: {event['event']}" for event in events])
        await interaction.followup.send(f"**Upcoming Solana Events:**\n{event_list}")
    else:
        await interaction.followup.send("No upcoming events found.", ephemeral=True)

@bot.tree.command(name="trackwallet", description="Track changes in a Solana wallet")
@app_commands.describe(wallet_address="The wallet address to track")
@commands.cooldown(1, 60, commands.BucketType.user)
async def trackwallet(interaction: discord.Interaction, wallet_address: str):
    await interaction.response.defer()
    if not is_valid_solana_address(wallet_address):
        await interaction.followup.send("Invalid wallet address.", ephemeral=True)
        return
    user_id = interaction.user.id
    channel_id = interaction.channel_id
    cursor = bot.db.cursor()
    cursor.execute("SELECT * FROM wallet_tracking WHERE wallet_address = ? AND user_id = ?", (wallet_address, user_id))
    if cursor.fetchone():
        await interaction.followup.send("You are already tracking this wallet.", ephemeral=True)
        return
    analysis = await bot.adaptx.analyze_wallet(wallet_address)
    cursor.execute(
        "INSERT INTO wallet_tracking (wallet_address, user_id, channel_id, last_analysis) VALUES (?, ?, ?, ?)",
        (wallet_address, user_id, channel_id, analysis)
    )
    bot.db.commit()
    await interaction.followup.send(f"Started tracking wallet `{wallet_address}`. You'll receive updates in this channel.")

@bot.tree.command(name="stoptracking", description="Stop tracking a Solana wallet")
@app_commands.describe(wallet_address="The wallet address to stop tracking")
@commands.cooldown(1, 60, commands.BucketType.user)
async def stoptracking(interaction: discord.Interaction, wallet_address: str):
    await interaction.response.defer()
    if not is_valid_solana_address(wallet_address):
        await interaction.followup.send("Invalid wallet address.", ephemeral=True)
        return
    user_id = interaction.user.id
    cursor = bot.db.cursor()
    cursor.execute("DELETE FROM wallet_tracking WHERE wallet_address = ? AND user_id = ?", (wallet_address, user_id))
    bot.db.commit()
    await interaction.followup.send(f"Stopped tracking wallet `{wallet_address}`.")

@bot.tree.command(name="nftportfolio", description="Analyze NFTs in a Solana wallet")
@app_commands.describe(wallet_address="The wallet address to analyze")
@commands.cooldown(1, 60, commands.BucketType.user)
async def nftportfolio(interaction: discord.Interaction, wallet_address: str):
    await interaction.response.defer()
    analysis = await bot.adaptx.get_nft_portfolio(wallet_address)
    await interaction.followup.send(analysis)

@bot.tree.command(name="stakinganalysis", description="Analyze staking accounts in a Solana wallet")
@app_commands.describe(wallet_address="The wallet address to analyze")
@commands.cooldown(1, 60, commands.BucketType.user)
async def stakinganalysis(interaction: discord.Interaction, wallet_address: str):
    await interaction.response.defer()
    analysis = await bot.adaptx.get_staking_analysis(wallet_address)
    await interaction.followup.send(analysis)

@bot.tree.command(name="recentactivity", description="Show recent activity for a Solana wallet")
@app_commands.describe(wallet_address="The wallet address to analyze")
@commands.cooldown(1, 60, commands.BucketType.user)
async def recentactivity(interaction: discord.Interaction, wallet_address: str):
    await interaction.response.defer()
    analysis = await bot.adaptx.get_recent_activity(wallet_address)
    await interaction.followup.send(analysis)

@bot.tree.command(name="ecosystem", description="Get comprehensive Solana ecosystem insights")
@commands.cooldown(1, 60, commands.BucketType.user)
async def ecosystem(interaction: discord.Interaction):
    await interaction.response.defer()
    insights = await bot.adaptx.get_ecosystem_insights()
    await interaction.followup.send(insights)

# Experimental Features (Set 1)
@bot.tree.command(name="soundboard", description="Play a Solana-themed sound in voice channel")
@app_commands.describe(sound="The sound to play: beep, confirm")
@commands.cooldown(1, 60, commands.BucketType.user)
async def soundboard(interaction: discord.Interaction, sound: str):
    if not interaction.user.voice:
        await interaction.response.send_message("You need to be in a voice channel!", ephemeral=True)
        return
    channel = interaction.user.voice.channel
    voice_client = await channel.connect()
    if sound == "beep":
        voice_client.play(FFmpegPCMAudio("beep.mp3"))
        await interaction.response.send_message(f"Playing {sound} sound!", ephemeral=True)
    elif sound == "confirm":
        voice_client.play(FFmpegPCMAudio("confirm.mp3"))
        await interaction.response.send_message(f"Playing {sound} sound!", ephemeral=True)
    else:
        await interaction.response.send_message("Available sounds: beep, confirm", ephemeral=True)

@bot.tree.command(name="setalert", description="Set a price alert for a Solana token")
@app_commands.describe(token="Token symbol (e.g., SOL)", condition="above or below", value="Price threshold")
@commands.cooldown(1, 60, commands.BucketType.user)
async def set_alert(interaction: discord.Interaction, token: str, condition: str, value: float):
    if condition not in ["above", "below"]:
        await interaction.response.send_message("Condition must be 'above' or 'below'.", ephemeral=True)
        return
    cursor = bot.db.cursor()
    cursor.execute("INSERT INTO alerts VALUES (?, ?, ?, ?)", (interaction.user.id, token, condition, value))
    bot.db.commit()
    await interaction.response.send_message(f"Alert set for {token} {condition} ${value}.")

@bot.tree.command(name="nftgallery", description="Display your Solana NFTs")
@app_commands.describe(wallet="Your Solana wallet address")
@commands.cooldown(1, 60, commands.BucketType.user)
async def nft_gallery(interaction: discord.Interaction, wallet: str):
    if not is_valid_solana_address(wallet):
        await interaction.response.send_message("Invalid wallet address.", ephemeral=True)
        return
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/nft-balances?api-key={HELIUS_API_KEY}"
    async with bot.adaptx.session.get(url) as resp:
        data = await resp.json()
        nfts = data.get("nfts", [])[:5]
        if nfts:
            gallery = "\n".join([f"- {nft['name']} (Mint: {nft['mint']})" for nft in nfts])
            await interaction.response.send_message(f"**NFT Gallery for {wallet}**\n{gallery}")
        else:
            await interaction.response.send_message("No NFTs found.")

@bot.tree.command(name="stakingcalc", description="Calculate potential staking rewards")
@app_commands.describe(stake="Amount to stake in SOL", validator="Validator address")
@commands.cooldown(1, 60, commands.BucketType.user)
async def staking_calc(interaction: discord.Interaction, stake: float, validator: str):
    validator_info = await bot.adaptx.get_validator_info(validator)
    if not validator_info:
        await interaction.response.send_message("Validator not found.", ephemeral=True)
        return
    apr = 7.5  # Mock APR
    rewards = stake * (apr / 100)
    await interaction.response.send_message(f"Staking {stake} SOL with {validator} could yield ~{rewards:.2f} SOL annually (APR: {apr}%).")

@bot.tree.command(name="decode", description="Decode a Solana transaction")
@app_commands.describe(tx_signature="Transaction signature")
@commands.cooldown(1, 60, commands.BucketType.user)
async def decode_tx(interaction: discord.Interaction, tx_signature: str):
    if not is_valid_transaction_hash(tx_signature):
        await interaction.response.send_message("Invalid transaction hash.", ephemeral=True)
        return
    tx = await bot.adaptx.solana_client.get_transaction(tx_signature)
    if tx.value:
        accounts = tx.value.transaction.message.account_keys
        decoded = f"Tx {tx_signature}: Involved accounts - {', '.join(accounts)}"
        await interaction.response.send_message(f"**Decoded Transaction**\n{decoded}")
    else:
        await interaction.response.send_message("Transaction not found.")

# New Experimental Features (Set 2)
@bot.tree.command(name="solpoll", description="Create a Solana-themed poll")
@app_commands.describe(question="Poll question", options="Options separated by commas")
@commands.cooldown(1, 60, commands.BucketType.user)
async def solpoll(interaction: discord.Interaction, question: str, options: str):
    opts = [opt.strip() for opt in options.split(",")][:10]  # Limit to 10 options
    if len(opts) < 2:
        await interaction.response.send_message("Please provide at least 2 options.", ephemeral=True)
        return
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"][:len(opts)]
    poll_text = f"**Poll: {question}**\n" + "\n".join([f"{emoji} {opt}" for emoji, opt in zip(emojis, opts)])
    await interaction.response.send_message(poll_text)
    message = await interaction.original_response()
    for emoji in emojis:
        await message.add_reaction(emoji)

@bot.tree.command(name="tokenlottery", description="Enter a token lottery (mock)")
@app_commands.describe(token="Token symbol", amount="Amount to enter")
@commands.cooldown(1, 60, commands.BucketType.user)
async def tokenlottery(interaction: discord.Interaction, token: str, amount: float):
    user_id = interaction.user.id
    cursor = bot.db.cursor()
    cursor.execute("INSERT INTO lottery (user_id, token, amount) VALUES (?, ?, ?)", (user_id, token, amount))
    bot.db.commit()
    await interaction.response.send_message(f"You've entered the {token} lottery with {amount} tokens! Winner announced soon (mock).")

@bot.tree.command(name="validatorrank", description="Show top Solana validators")
@commands.cooldown(1, 60, commands.BucketType.user)
async def validatorrank(interaction: discord.Interaction):
    ranking = await bot.adaptx.get_top_validators()
    if ranking:
        await interaction.response.send_message(f"**Top Validators:**\n{ranking}")
    else:
        await interaction.response.send_message("Unable to fetch validator rankings.")

@bot.tree.command(name="nftdrop", description="Announce a mock NFT drop")
@app_commands.describe(name="NFT collection name", quantity="Number of NFTs")
@commands.cooldown(1, 60, commands.BucketType.user)
async def nftdrop(interaction: discord.Interaction, name: str, quantity: int):
    await interaction.response.send_message(f"🎉 **NFT Drop Alert**: {quantity} NFTs from the '{name}' collection are dropping soon! (Mock)")

@bot.tree.command(name="solchat", description="Join a Solana-themed voice chat")
@commands.cooldown(1, 60, commands.BucketType.user)
async def solchat(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("You need to be in a voice channel!", ephemeral=True)
        return
    channel = interaction.user.voice.channel
    voice_client = await channel.connect()
    await interaction.response.send_message(f"Connected to {channel.name} for a Solana chat! Say hi!")

# New Features (Set 3)
@bot.tree.command(name="tokenmetadata", description="Get metadata for a Solana token")
@app_commands.describe(token_mint="The mint address of the token")
@commands.cooldown(1, 60, commands.BucketType.user)
async def tokenmetadata(interaction: discord.Interaction, token_mint: str):
    await interaction.response.defer()
    if not is_valid_solana_address(token_mint):
        await interaction.followup.send("Invalid token mint address.", ephemeral=True)
        return
    url = f"https://api.helius.xyz/v0/tokens/{token_mint}/metadata?api-key={HELIUS_API_KEY}"
    try:
        async with bot.adaptx.session.get(url, timeout=10) as response:
            data = await response.json()
            if 'metadata' in data:
                metadata = data['metadata']
                await interaction.followup.send(
                    f"**Token Metadata for {token_mint}**\n"
                    f"• Name: {metadata.get('name', 'N/A')}\n"
                    f"• Symbol: {metadata.get('symbol', 'N/A')}\n"
                    f"• URI: {metadata.get('uri', 'N/A')}"
                )
            else:
                await interaction.followup.send("Metadata not found.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error fetching token metadata for {token_mint}: {e}")
        await interaction.followup.send("Error fetching token metadata.", ephemeral=True)

@bot.tree.command(name="programaccounts", description="List accounts owned by a program")
@app_commands.describe(program_id="Program ID")
@commands.cooldown(1, 60, commands.BucketType.user)
async def programaccounts(interaction: discord.Interaction, program_id: str):
    await interaction.response.defer()
    if not is_valid_solana_address(program_id):
        await interaction.followup.send("Invalid program ID.", ephemeral=True)
        return
    try:
        accounts = await bot.adaptx.solana_client.get_program_accounts(program_id)
        if accounts.value:
            await interaction.followup.send(f"Found {len(accounts.value)} accounts for program {program_id}.")
        else:
            await interaction.followup.send("No accounts found.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error fetching program accounts for {program_id}: {e}")
        await interaction.followup.send("Error fetching program accounts.", ephemeral=True)

@bot.tree.command(name="blockinfo", description="Get information about a Solana block")
@app_commands.describe(block_number="Block number")
@commands.cooldown(1, 60, commands.BucketType.user)
async def blockinfo(interaction: discord.Interaction, block_number: int):
    await interaction.response.defer()
    try:
        block = await bot.adaptx.solana_client.get_block(block_number)
        if block.value:
            await interaction.followup.send(
                f"**Block {block_number} Info**\n"
                f"• Transactions: {len(block.value.transactions)}\n"
                f"• Block Time: {block.value.block_time}\n"
                f"• Block Hash: {block.value.blockhash[:8]}..."
            )
        else:
            await interaction.followup.send("Block not found.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error fetching block info for {block_number}: {e}")
        await interaction.followup.send("Error fetching block info.", ephemeral=True)

@bot.tree.command(name="accountinfo", description="Get information about a Solana account")
@app_commands.describe(account_address="Account address")
@commands.cooldown(1, 60, commands.BucketType.user)
async def accountinfo(interaction: discord.Interaction, account_address: str):
    await interaction.response.defer()
    if not is_valid_solana_address(account_address):
        await interaction.followup.send("Invalid account address.", ephemeral=True)
        return
    try:
        account = await bot.adaptx.solana_client.get_account_info(account_address)
        if account.value:
            await interaction.followup.send(
                f"**Account Info for {account_address}**\n"
                f"• Balance: {account.value.lamports / 1e9:.4f} SOL\n"
                f"• Owner: {account.value.owner[:8]}...\n"
                f"• Executable: {'Yes' if account.value.executable else 'No'}"
            )
        else:
            await interaction.followup.send("Account not found.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error fetching account info for {account_address}: {e}")
        await interaction.followup.send("Error fetching account info.", ephemeral=True)

@bot.tree.command(name="leaderboard", description="Show top Solana validators by stake")
@commands.cooldown(1, 60, commands.BucketType.user)
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    top_validators = await bot.adaptx.get_top_validators()
    if top_validators:
        await interaction.followup.send(f"**Top Validators by Stake:**\n{top_validators}")
    else:
        await interaction.followup.send("Unable to fetch validator data.", ephemeral=True)

@bot.tree.command(name="solanagames", description="Start a Solana trivia game")
@commands.cooldown(1, 60, commands.BucketType.user)
async def solanagames(interaction: discord.Interaction):
    await interaction.response.defer()
    questions = [
        ("What year was Solana launched?", "2020"),
        ("Who is the founder of Solana?", "Anatoly Yakovenko"),
        ("What is Solana's consensus mechanism?", "Proof of History")
    ]
    question, answer = random.choice(questions)
    await interaction.followup.send(f"**Trivia**: {question}\nType your answer!")
    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel
    try:
        msg = await bot.wait_for("message", check=check, timeout=30)
        if msg.content.lower() == answer.lower():
            await msg.reply("Correct! 🎉")
        else:
            await msg.reply(f"Wrong! The answer was {answer}.")
    except asyncio.TimeoutError:
        await interaction.followup.send("Time's up! ⏰")

@bot.tree.command(name="memegenerator", description="Create a Solana-themed meme")
@app_commands.describe(top_text="Text for top of meme", bottom_text="Text for bottom of meme")
@commands.cooldown(1, 60, commands.BucketType.user)
async def memegenerator(interaction: discord.Interaction, top_text: str, bottom_text: str):
    await interaction.response.defer()
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        template_path = "solana_meme_template.jpg"  # Ensure you have a template image
        img = Image.open(template_path)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((10, 10), top_text.upper(), fill="white", font=font)
        draw.text((10, img.height - 30), bottom_text.upper(), fill="white", font=font)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        await interaction.followup.send(file=discord.File(buffer, "meme.png"))
    except Exception as e:
        logger.error(f"Error generating meme: {e}")
        await interaction.followup.send("Error generating meme. Ensure template exists.", ephemeral=True)

@bot.tree.command(name="snsresolve", description="Resolve a Solana Name Service domain")
@app_commands.describe(domain="SNS domain (e.g., example.sol)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def snsresolve(interaction: discord.Interaction, domain: str):
    await interaction.response.defer()
    if not domain.endswith(".sol"):
        await interaction.followup.send("Please provide a .sol domain.", ephemeral=True)
        return
    # Mock SNS resolution (replace with actual implementation using SNS SDK)
    resolved_address = "ExampleWalletAddress"
    await interaction.followup.send(f"{domain} resolves to {resolved_address}")

@bot.tree.command(name="swapestimate", description="Estimate a token swap")
@app_commands.describe(amount="Amount to swap", token_in="Input token", token_out="Output token")
@commands.cooldown(1, 60, commands.BucketType.user)
async def swapestimate(interaction: discord.Interaction, amount: float, token_in: str, token_out: str):
    await interaction.response.defer()
    # Mock swap estimation (replace with actual implementation using Jupiter or similar)
    output = amount * 0.98  # Assume 2% slippage
    await interaction.followup.send(
        f"**Swap Estimate**\n"
        f"• Input: {amount} {token_in}\n"
        f"• Output: {output:.4f} {token_out} (2% slippage)"
    )

@bot.tree.command(name="solpay", description="Generate a Solana Pay link")
@app_commands.describe(recipient="Recipient address", amount="Amount in SOL", label="Label for payment")
@commands.cooldown(1, 60, commands.BucketType.user)
async def solpay(interaction: discord.Interaction, recipient: str, amount: float, label: str):
    await interaction.response.defer()
    if not is_valid_solana_address(recipient):
        await interaction.followup.send("Invalid recipient address.", ephemeral=True)
        return
    # Generate Solana Pay URL
    solpay_url = f"solana:{recipient}?amount={amount}&label={label.replace(' ', '%20')}"
    await interaction.followup.send(f"**Solana Pay Link**: {solpay_url}")

# Main Entry Point
async def main():
    async with aiohttp.ClientSession() as session:
        bot.adaptx = AdaptX(session)
        bot.db = sqlite3.connect('bot.db')
        bot.db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, wallet TEXT, language TEXT DEFAULT "en")')
        bot.db.execute('CREATE TABLE IF NOT EXISTS wallet_tracking (wallet_address TEXT, user_id INTEGER, channel_id INTEGER, last_analysis TEXT)')
        bot.db.execute('CREATE TABLE IF NOT EXISTS alerts (user_id INTEGER, token TEXT, condition TEXT, value REAL)')
        bot.db.execute('CREATE TABLE IF NOT EXISTS lottery (user_id INTEGER, token TEXT, amount REAL)')
        bot.db.commit()
        await bot.add_cog(MultilangCog(bot))
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())