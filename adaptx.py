#!/usr/bin/env python
"""
AdaptX: A Solana influencer Discord bot with real prediction markets.

Key Features:
- Core Commands: /idea, /ask, /analyze, /walletanalysis, /price, /networkstats, /scheduleama, /governance, /usecases
- Enhanced Commands: /tokeninfo, /validator, /events, /trackwallet, /stoptracking, /nftportfolio, /stakinganalysis, /recentactivity, /ecosystem
- Experimental Features (Set 1): /soundboard, /setalert, /nftgallery, /stakingcalc, /decode
- New Experimental Features (Set 2): /solpoll, /tokenlottery, /validatorrank, /nftdrop, /solchat
- New Features (Set 3): /tokenmetadata, /programaccounts, /blockinfo, /accountinfo, /leaderboard, /solanagames, /memegenerator, /snsresolve, /swapestimate, /solpay
- Prediction Markets: /linkwallet, /createprediction, /placewager, /viewpredictions, /settleprediction
- Enhanced Integration: Better utilization of Helius, Quicknode, and Mistral.
- New Features (Enhanced): /networkanalytics, /walletrealtime, /marketupdate, /solanainsights, /userfeedback
- Additional New Features: /cryptohistory, /nftdetails, /validatorsearch, /solanadashboard, /airdrop
- Voice Support: Enabled with PyNaCl
- Dependencies: discord.py==2.2.2, python-dotenv, aiohttp, cachetools, solana>=0.35.0, solders, pyfiglet, base58, PyNaCl, Pillow, requests
"""

import os
import asyncio
import logging
import sqlite3
import random
from typing import Any, Dict, List, Union
from datetime import datetime, timedelta
import json

import discord
from discord.ext import commands, tasks
from discord import app_commands, Embed, File
from discord import FFmpegPCMAudio
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solders.transaction import Transaction
from solders.system_program import TransferParams, transfer
from solana.rpc.commitment import Confirmed
from solders.signature import Signature
import base58

from dotenv import load_dotenv
import aiohttp
from cachetools import TTLCache
import pyfiglet
import requests
from PIL import Image, ImageDraw, ImageFont
import io

# Configuration & Logging
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
QUICKNODE_SOLANA_HTTP_URL = os.getenv("QUICKNODE_SOLANA_HTTP_URL")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
SOLANA_RPC_URL = QUICKNODE_SOLANA_HTTP_URL or "https://api.mainnet-beta.solana.com"
BOT_WALLET_SECRET = os.getenv("BOT_WALLET_SECRET")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("AdaptX")

# ASCII Art with Gradient
ascii_art = pyfiglet.figlet_format("ADAPTX", font="elite")
def apply_gradient(ascii_art, gradient_stops):
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
            r = pos / (L - 1) if L > 1 else 0
            segment = min(int(r * num_segments), num_segments - 1)
            local_ratio = (r * num_segments) - segment
            start_color = gradient_stops[segment]
            end_color = gradient_stops[segment + 1]
            color = tuple(int(start_color[i] + (end_color[i] - start_color[i]) * local_ratio) for i in range(3))
            colored_line += f"\033[38;2;{color[0]};{color[1]};{color[2]}m" + line[pos]
        colored_line += "\033[0m"
        gradient_lines.append(colored_line)
    return '\n'.join(gradient_lines)

gradient_stops = [(0, 255, 163), (3, 225, 255), (220, 31, 255), (220, 31, 255)]
ascii_art_gradient = apply_gradient(ascii_art, gradient_stops)
print(ascii_art_gradient)
print("Version 1.20 - Prediction Markets Edition\n")

# Bot Setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global Variables
network_stats_history: List[Dict[str, Union[float, int]]] = []  # For network TPS history
realtime_wallet_subscriptions: Dict[int, List[str]] = {}  # user_id -> list of wallet addresses

# Validation Functions
def is_valid_solana_address(address: str) -> bool:
    try:
        decoded = base58.b58decode(address)
        return 32 <= len(decoded) <= 44
    except Exception:
        return False

def is_valid_transaction_hash(tx_hash: str) -> bool:
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
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=data, timeout=10) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result['choices'][0]['message']['content'].strip()
            except Exception as e:
                logger.error(f"Mistral API error: {e}")
                return f"⚠️ Error: {str(e)}"

mistral_client = MistralAIClient(MISTRAL_API_KEY)

# AdaptX Core Class with Solana Integration
class AdaptX:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.helius_api_key = HELIUS_API_KEY
        self.solana_client = AsyncClient(SOLANA_RPC_URL)
        decoded_secret = base58.b58decode(BOT_WALLET_SECRET)
        self.bot_keypair = Keypair.from_bytes(decoded_secret)
        self.bot_pubkey = self.bot_keypair.pubkey
        self.token_mints = {
            "SOL": None,
            "JUP": Pubkey(base58.b58decode("JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN")),
            "BONK": Pubkey(base58.b58decode("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"))
        }
    async def cached_call(self, key: str, generator: callable, ttl: int = 3600) -> Any:
        cache = cache_manager.get_cache(ttl)
        if key in cache:
            return cache[key]
        value = await generator() if asyncio.iscoroutinefunction(generator) else await asyncio.to_thread(generator)
        cache[key] = value
        return value
    async def generate_post_ideas(self, topic: str = "Solana trends") -> str:
        key = f"idea:{topic}"
        async def generate() -> str:
            prompt = f"You are AdaptX, a Solana influencer. Generate a tweet idea about {topic}."
            return await mistral_client.generate_text(prompt)
        return await self.cached_call(key, generate, ttl=3600)
    async def ask_question(self, question: str) -> str:
        key = f"ask:{question}"
        async def generate() -> str:
            prompt = f"You are AdaptX, a Solana expert. Answer: {question}"
            return await mistral_client.generate_text(prompt, max_tokens=150)
        return await self.cached_call(key, generate, ttl=3600)
    async def analyze_transaction(self, tx_hash: str) -> Dict[str, Any]:
        if not is_valid_transaction_hash(tx_hash):
            return {"error": "Invalid transaction hash."}
        url = f"https://api.helius.xyz/v0/transactions/{tx_hash}?api-key={self.helius_api_key}"
        async with self.session.get(url, timeout=15) as response:
            data = await response.json()
            return {"analysis": f"Tx `{tx_hash}`\n• Fee: {data.get('fee', 0)/1e9:.4f} SOL"}
    async def analyze_wallet(self, wallet_address: str) -> str:
        if not is_valid_solana_address(wallet_address):
            return "Invalid wallet address."
        try:
            url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/balances?api-key={self.helius_api_key}"
            async with self.session.get(url, timeout=15) as response:
                data = await response.json()
                sol_balance = data.get('nativeBalance', 0) / 1e9
                return f"**Wallet `{wallet_address}`**\n• SOL: {sol_balance:.4f}"
        except Exception as e:
            logger.error(f"Helius analyze_wallet error: {e}")
            try:
                balance_resp = await self.solana_client.get_balance(Pubkey(wallet_address))
                sol_balance = balance_resp.value / 1e9
                return f"**Wallet `{wallet_address}`**\n• SOL: {sol_balance:.4f} (fallback)"
            except Exception as e2:
                logger.error(f"Fallback get_balance error: {e2}")
                return "Error analyzing wallet balance."
    async def get_solana_network_stats(self) -> str:
        url = f"https://api.helius.xyz/v0/metrics?api-key={self.helius_api_key}"
        try:
            async with self.session.get(url, timeout=10) as resp:
                data = await resp.json()
                return f"**Solana Stats**\n• TPS: {data.get('tps', 'N/A')}"
        except Exception as e:
            logger.error(f"Helius network stats error: {e}")
            return "**Solana Stats**\n• TPS: N/A (error)"
    async def get_crypto_price_coingecko(self, crypto: str) -> str:
        key = f"price:{crypto}"
        async def generate() -> str:
            url = f"https://api.coingecko.com/api/v3/coins/{crypto.lower()}"
            async with self.session.get(url, timeout=10) as response:
                data = await response.json()
                if 'market_data' in data:
                    price = data['market_data']['current_price']['usd']
                    return f"**{crypto.title()}**\n• Price: ${price:,}"
                return f"No data for '{crypto}'."
        return await self.cached_call(key, generate, ttl=300)
    async def get_coingecko_id(self, token_mint: str) -> str:
        url = "https://api.coingecko.com/api/v3/coins/list?include_platform=true"
        async with self.session.get(url, timeout=10) as response:
            coins = await response.json()
            for coin in coins:
                if coin.get("platforms", {}).get("solana") == token_mint:
                    return coin["id"]
            return None
    async def get_token_holder_count(self, token_mint: str) -> int:
        key = f"token_holders:{token_mint}"
        async def generate() -> int:
            url = f"https://api.helius.xyz/v0/token-accounts?api-key={self.helius_api_key}"
            async with self.session.post(url, json={"mint": token_mint}, timeout=15) as response:
                response.raise_for_status()
                accounts = await response.json()
            unique_owners = set(account['owner'] for account in accounts)
            return len(unique_owners)
        return await self.cached_call(key, generate, ttl=7200)
    async def get_validator_info(self, validator_address: str) -> Dict[str, Any]:
        try:
            vote_accounts = await self.solana_client.get_vote_accounts()
            for validator in vote_accounts.value.current:
                if str(validator.vote_pubkey) == validator_address:
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
            return [{"date": "2023-10-01", "event": "Solana Breakpoint Conference"}]
        key = "twitter_events"
        async def generate() -> List[Dict[str, str]]:
            url = "https://api.twitter.com/2/tweets/search/recent"
            headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
            params = {"query": "from:Solana OR from:SolanaFndn event announcement -is:retweet", "max_results": 10}
            async with self.session.get(url, headers=headers, params=params, timeout=10) as response:
                data = await response.json()
                events = []
                for tweet in data.get("data", []):
                    text = tweet["text"]
                    if "event" in text.lower() and "date" in text.lower():
                        events.append({"date": "N/A", "event": text[:100] + "..."})
                return events if events else [{"date": "N/A", "event": "No recent events found."}]
        return await self.cached_call(key, generate, ttl=3600)
    async def get_nft_portfolio(self, wallet_address: str) -> str:
        if not is_valid_solana_address(wallet_address):
            return "Invalid wallet address."
        url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/nft-balances?api-key={self.helius_api_key}"
        async with self.session.get(url, timeout=15) as response:
            data = await response.json()
            nfts = data.get("nfts", [])
            return f"**NFTs for `{wallet_address}`**\n• Total: {len(nfts)}"
    async def get_staking_analysis(self, wallet_address: str) -> str:
        if not is_valid_solana_address(wallet_address):
            return "Invalid wallet address."
        url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/staking-accounts?api-key={self.helius_api_key}"
        async with self.session.get(url, timeout=15) as response:
            data = await response.json()
            stakes = data.get("stakingAccounts", [])
            return f"**Staking for `{wallet_address}`**\n• Total: {len(stakes)}"
    async def get_recent_activity(self, wallet_address: str) -> str:
        if not is_valid_solana_address(wallet_address):
            return "Invalid wallet address."
        url = f"https://api.helius.xyz/v0/addresses/{wallet_address}/transactions?api-key={self.helius_api_key}"
        async with self.session.get(url, timeout=15) as response:
            data = await response.json()
            txs = data[:5]
            return f"**Activity for `{wallet_address}`**\n• Recent Txs: {len(txs)}"
    async def get_ecosystem_insights(self) -> str:
        stats = await self.get_solana_network_stats()
        return f"**Ecosystem Insights**\n{stats}"
    async def get_trending_tokens(self) -> str:
        return "• BONK: +15% volume\n• RAY: +10% holders"
    async def get_top_validators(self) -> str:
        try:
            vote_accounts = await self.solana_client.get_vote_accounts()
            validators = sorted(vote_accounts.value.current, key=lambda v: v.activated_stake, reverse=True)[:3]
            return "\n".join([f"• {str(v.vote_pubkey)[:8]}...: {v.activated_stake/1e9:.2f} SOL" for v in validators])
        except Exception:
            return "N/A"
    async def prepare_transaction(self, sender_wallet: str, amount: float, token: str, destination: str) -> Dict[str, Any]:
        sender = Pubkey(sender_wallet)
        dest = Pubkey(destination)
        if token == "SOL":
            lamports = int(amount * 1_000_000_000)
            tx = Transaction()
            tx.add(
                transfer(TransferParams(
                    from_pubkey=sender,
                    to_pubkey=dest,
                    lamports=lamports
                ))
            )
            recent_blockhash_resp = await self.solana_client.get_latest_blockhash()
            recent_blockhash = recent_blockhash_resp.value.blockhash
            tx.recent_blockhash = recent_blockhash
            serialized_tx = base58.b58encode(bytes(tx)).decode('utf-8')
            return {"serialized_tx": serialized_tx, "amount": lamports, "token": "SOL"}
        else:
            raise NotImplementedError("SPL token transfers require token account setup.")
    async def verify_and_execute_transaction(self, signed_tx: str, expected_amount: float, token: str) -> str:
        try:
            tx_bytes = base58.b58decode(signed_tx)
            tx = Transaction.deserialize(tx_bytes)
            result = await self.solana_client.send_transaction(tx, opts=Confirmed)
            tx_sig = str(result.value)
            tx_info = await self.solana_client.get_transaction(tx_sig)
            if token == "SOL":
                transfer_instruction = tx_info.value.transaction.transaction.message.instructions[0]
                if str(transfer_instruction.accounts[1]) == str(self.bot_pubkey) and transfer_instruction.data.amount == int(expected_amount * 1_000_000_000):
                    return tx_sig
            raise ValueError("Transaction verification failed.")
        except Exception as e:
            logger.error(f"Transaction execution error: {e}")
            return None

# --- Background Tasks ---

@tasks.loop(seconds=30)
async def collect_network_stats():
    stats_str = await bot.adaptx.get_solana_network_stats()
    try:
        tps = float(stats_str.split("TPS:")[1].strip())
    except Exception:
        tps = 0.0
    network_stats_history.append({"timestamp": datetime.utcnow().timestamp(), "tps": tps})
    cutoff = datetime.utcnow().timestamp() - 600
    while network_stats_history and network_stats_history[0]["timestamp"] < cutoff:
        network_stats_history.pop(0)

@tasks.loop(minutes=5)
async def refresh_solana_stats():
    stats = await bot.adaptx.get_solana_network_stats()
    logger.info("Refreshed Solana stats cache")

@tasks.loop(minutes=1)
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
    for user_id, wallets in realtime_wallet_subscriptions.items():
        for wallet in wallets:
            analysis = await bot.adaptx.analyze_wallet(wallet)
            user = await bot.fetch_user(user_id)
            await user.send(f"[Realtime Update] Wallet `{wallet}`: {analysis}")
    bot.db.commit()

@tasks.loop(minutes=1)
async def check_price_alerts():
    cursor = bot.db.cursor()
    cursor.execute("SELECT user_id, token, condition, value FROM alerts")
    for user_id, token, condition, value in cursor.fetchall():
        price_info = await bot.adaptx.get_crypto_price_coingecko(token.lower())
        try:
            price = float(price_info.split("Price: $")[1].replace(",", ""))
            if (condition == "above" and price > value) or (condition == "below" and price < value):
                user = await bot.fetch_user(user_id)
                await user.send(f"🚨 {token} is {condition} ${value}! Current price: ${price}")
                cursor.execute("DELETE FROM alerts WHERE user_id = ? AND token = ?", (user_id, token))
        except Exception as e:
            logger.error(f"Error parsing price for alert: {e}")
    bot.db.commit()

# --- Command Definitions ---

# Existing Commands (Points)
@bot.command(name="points")
async def points(ctx):
    user_id = ctx.author.id
    cursor = bot.db.cursor()
    cursor.execute("SELECT points FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    await ctx.send(f"You have {result[0] if result else 0} points!")

@bot.command(name="addpoints")
async def addpoints(ctx, points: int):
    user_id = ctx.author.id
    cursor = bot.db.cursor()
    cursor.execute("SELECT points FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        new_points = result[0] + points
        cursor.execute("UPDATE users SET points = ? WHERE id = ?", (new_points, user_id))
    else:
        new_points = points
        cursor.execute("INSERT INTO users (id, points) VALUES (?, ?)", (user_id, points))
    bot.db.commit()
    await ctx.send(f"{points} points added! You now have {new_points} points.")

# Core Slash Commands
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
    await interaction.followup.send(result.get("analysis", result.get("error", "Error analyzing transaction.")))

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

# Enhanced Commands
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
        await interaction.followup.send(
            f"**Validator Info for `{validator_address}`:**\n"
            f"• Stake: {info['stake']:.2f} SOL\n"
            f"• Commission: {info['commission']}%\n"
            f"• Latest Epoch Credits: {info['epoch_credits']:,}\n"
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

# Experimental Features (Set 1) - Placeholder Implementations
@bot.tree.command(name="soundboard", description="Play a sound in voice channel (placeholder)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def soundboard(interaction: discord.Interaction):
    await interaction.response.send_message("Soundboard feature is under development.")

@bot.tree.command(name="setalert", description="Set a price alert for a token")
@app_commands.describe(token="Token symbol", condition="above/below", value="Price threshold")
@commands.cooldown(1, 60, commands.BucketType.user)
async def setalert(interaction: discord.Interaction, token: str, condition: str, value: float):
    if condition not in ["above", "below"]:
        await interaction.response.send_message("Condition must be 'above' or 'below'.", ephemeral=True)
        return
    cursor = bot.db.cursor()
    cursor.execute("INSERT INTO alerts (user_id, token, condition, value) VALUES (?, ?, ?, ?)",
                   (interaction.user.id, token.upper(), condition, value))
    bot.db.commit()
    await interaction.response.send_message(f"Alert set for {token} {condition} ${value}.")

@bot.tree.command(name="nftgallery", description="Display NFT gallery (placeholder)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def nftgallery(interaction: discord.Interaction):
    await interaction.response.send_message("NFT gallery feature is under development.")

@bot.tree.command(name="stakingcalc", description="Calculate staking rewards (placeholder)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def stakingcalc(interaction: discord.Interaction):
    await interaction.response.send_message("Staking calculator is under development.")

@bot.tree.command(name="decode", description="Decode a Solana transaction (placeholder)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def decode(interaction: discord.Interaction):
    await interaction.response.send_message("Transaction decode feature is under development.")

# New Experimental Features (Set 2) - Placeholder Implementations
@bot.tree.command(name="solpoll", description="Create a Solana-themed poll (placeholder)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def solpoll(interaction: discord.Interaction):
    await interaction.response.send_message("Poll feature is under development.")

@bot.tree.command(name="tokenlottery", description="Enter a token lottery (placeholder)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def tokenlottery(interaction: discord.Interaction):
    await interaction.response.send_message("Token lottery is under development.")

@bot.tree.command(name="validatorrank", description="Rank validators (placeholder)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def validatorrank(interaction: discord.Interaction):
    await interaction.response.send_message("Validator ranking is under development.")

@bot.tree.command(name="nftdrop", description="Announce an NFT drop (placeholder)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def nftdrop(interaction: discord.Interaction):
    await interaction.response.send_message("NFT drop feature is under development.")

@bot.tree.command(name="solchat", description="Initiate a Solana chat (placeholder)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def solchat(interaction: discord.Interaction):
    await interaction.response.send_message("Solana chat is under development.")

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
        logger.error(f"Error fetching token metadata: {e}")
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
        accounts = await bot.adaptx.solana_client.get_program_accounts(Pubkey(program_id))
        await interaction.followup.send(f"Found {len(accounts.value)} accounts for program `{program_id}`.")
    except Exception as e:
        logger.error(f"Error fetching program accounts: {e}")
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
                f"• Block Time: {datetime.fromtimestamp(block.value.block_time).strftime('%Y-%m-%d %H:%M:%S') if block.value.block_time else 'N/A'}\n"
                f"• Block Hash: {str(block.value.blockhash)[:8]}..."
            )
        else:
            await interaction.followup.send("Block not found.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error fetching block info: {e}")
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
        account = await bot.adaptx.solana_client.get_account_info(Pubkey(account_address))
        if account.value:
            await interaction.followup.send(
                f"**Account Info for `{account_address}`**\n"
                f"• Balance: {account.value.lamports / 1e9:.4f} SOL\n"
                f"• Owner: {str(account.value.owner)[:8]}...\n"
                f"• Executable: {'Yes' if account.value.executable else 'No'}"
            )
        else:
            await interaction.followup.send("Account not found.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error fetching account info: {e}")
        await interaction.followup.send("Error fetching account info.", ephemeral=True)

@bot.tree.command(name="leaderboard", description="Show top Solana validators by stake")
@commands.cooldown(1, 60, commands.BucketType.user)
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    top_validators = await bot.adaptx.get_top_validators()
    await interaction.followup.send(f"**Top Validators by Stake:**\n{top_validators}")

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
        img = Image.open(r"C:\Users\ckdsi\Desktop\AdaptX\solana_meme_template.jpg")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((10, 10), top_text.upper(), fill="white", font=font)
        draw.text((10, img.height - 30), bottom_text.upper(), fill="white", font=font)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        await interaction.followup.send(file=discord.File(buffer, "meme.png"))
    except FileNotFoundError:
        await interaction.followup.send("Meme template not found. Please ensure 'solana_meme_template.jpg' exists.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error generating meme: {e}")
        await interaction.followup.send("Error generating meme.", ephemeral=True)

@bot.tree.command(name="snsresolve", description="Resolve a Solana Name Service domain (placeholder)")
@app_commands.describe(domain="SNS domain (e.g., example.sol)")
@commands.cooldown(1, 60, commands.BucketType.user)
async def snsresolve(interaction: discord.Interaction, domain: str):
    await interaction.response.defer()
    if not domain.endswith(".sol"):
        await interaction.followup.send("Please provide a .sol domain.", ephemeral=True)
        return
    await interaction.followup.send(f"{domain} resolves to [Placeholder Address] (SNS resolution not fully implemented).")

@bot.tree.command(name="swapestimate", description="Estimate a token swap")
@app_commands.describe(amount="Amount to swap", token_in="Input token", token_out="Output token")
@commands.cooldown(1, 60, commands.BucketType.user)
async def swapestimate(interaction: discord.Interaction, amount: float, token_in: str, token_out: str):
    await interaction.response.defer()
    output = amount * 0.98  # Simple 2% slippage simulation
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
    solpay_url = f"solana:{recipient}?amount={amount}&label={label.replace(' ', '%20')}"
    await interaction.followup.send(f"**Solana Pay Link**: {solpay_url}")

# Prediction Markets
@bot.tree.command(name="linkwallet", description="Link your Solana wallet to your Discord account")
@app_commands.describe(wallet="Your Solana wallet address")
@commands.cooldown(1, 60, commands.BucketType.user)
async def linkwallet(interaction: discord.Interaction, wallet: str):
    await interaction.response.defer()
    if not is_valid_solana_address(wallet):
        await interaction.followup.send("Invalid wallet address.", ephemeral=True)
        return
    cursor = bot.db.cursor()
    cursor.execute("UPDATE users SET wallet = ? WHERE id = ?", (wallet, interaction.user.id))
    if cursor.rowcount == 0:
        cursor.execute("INSERT INTO users (id, wallet) VALUES (?, ?)", (interaction.user.id, wallet))
    bot.db.commit()
    await interaction.followup.send(f"Wallet `{wallet}` linked to your account.")

@bot.tree.command(name="createprediction", description="Create a prediction market with options")
@app_commands.describe(title="Prediction title", options="Comma-separated options", duration="Duration in hours")
@commands.cooldown(1, 60, commands.BucketType.user)
async def createprediction(interaction: discord.Interaction, title: str, options: str, duration: float):
    await interaction.response.defer()
    options_list = [opt.strip() for opt in options.split(",")]
    if len(options_list) < 2:
        await interaction.followup.send("Provide at least 2 options.", ephemeral=True)
        return
    cursor = bot.db.cursor()
    cursor.execute("SELECT wallet FROM users WHERE id = ?", (interaction.user.id,))
    creator_wallet = cursor.fetchone()
    if not creator_wallet or not creator_wallet[0]:
        await interaction.followup.send("Link your wallet first with /linkwallet.", ephemeral=True)
        return
    end_time = datetime.utcnow() + timedelta(hours=duration)
    image_url = None
    if interaction.data.get('attachments'):
        image_url = interaction.data['attachments'][0]['url']
    cursor.execute(
        "INSERT INTO predictions (title, creator_id, creator_wallet, options, end_time, status, image_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, interaction.user.id, creator_wallet[0], ",".join(options_list), end_time.timestamp(), "open", image_url)
    )
    bot.db.commit()
    prediction_id = cursor.lastrowid
    embed = Embed(title=f"Prediction #{prediction_id}: {title}", description="Options:")
    for i, opt in enumerate(options_list, 1):
        embed.add_field(name=f"{i}. {opt}", value="Wager with /placewager", inline=False)
    if image_url:
        embed.set_image(url=image_url)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="placewager", description="Place a wager on a prediction with SOL, JUP, or BONK")
@app_commands.describe(prediction_id="Prediction ID", token="SOL, JUP, or BONK", amount="Amount to wager", option="Option number")
@commands.cooldown(1, 60, commands.BucketType.user)
async def placewager(interaction: discord.Interaction, prediction_id: int, token: str, amount: float, option: int):
    await interaction.response.defer()
    token = token.upper()
    if token not in ["SOL", "JUP", "BONK"]:
        await interaction.followup.send("Invalid token. Use SOL, JUP, or BONK.", ephemeral=True)
        return
    cursor = bot.db.cursor()
    cursor.execute("SELECT options, status, creator_wallet FROM predictions WHERE id = ?", (prediction_id,))
    pred = cursor.fetchone()
    if not pred or pred[1] != "open":
        await interaction.followup.send("Prediction not found or closed.", ephemeral=True)
        return
    options = pred[0].split(",")
    if not (1 <= option <= len(options)):
        await interaction.followup.send("Invalid option number.", ephemeral=True)
        return
    cursor.execute("SELECT wallet FROM users WHERE id = ?", (interaction.user.id,))
    user_wallet = cursor.fetchone()
    if not user_wallet or not user_wallet[0]:
        await interaction.followup.send("Link your wallet first with /linkwallet.", ephemeral=True)
        return
    tx_data = await bot.adaptx.prepare_transaction(user_wallet[0], amount, token, pred[2])
    await interaction.followup.send(
        f"Please sign this transaction with your wallet (e.g., Phantom):\n"
        f"Serialized Tx: `{tx_data['serialized_tx']}`\n"
        f"Amount: {amount} {token}\n"
        f"Reply with the signed transaction string to confirm."
    )
    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel
    try:
        msg = await bot.wait_for("message", check=check, timeout=300)
        signed_tx = msg.content.strip()
        tx_sig = await bot.adaptx.verify_and_execute_transaction(signed_tx, amount, token)
        if tx_sig:
            cursor.execute(
                "INSERT INTO wagers (user_id, prediction_id, token, amount, option, wallet, tx_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (interaction.user.id, prediction_id, token, amount, option, user_wallet[0], tx_sig)
            )
            bot.db.commit()
            await interaction.followup.send(f"Wager of {amount} {token} placed on option {option}. Tx: `{tx_sig}`")
        else:
            await interaction.followup.send("Transaction verification failed.", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("Wager timed out. Please sign within 5 minutes.", ephemeral=True)

@bot.tree.command(name="viewpredictions", description="View active predictions")
@commands.cooldown(1, 60, commands.BucketType.user)
async def viewpredictions(interaction: discord.Interaction):
    await interaction.response.defer()
    cursor = bot.db.cursor()
    cursor.execute("SELECT id, title, options, end_time, image_url FROM predictions WHERE status = 'open'")
    preds = cursor.fetchall()
    if not preds:
        await interaction.followup.send("No active predictions.")
        return
    embed = Embed(title="Active Predictions", description="Current markets:")
    for pred in preds:
        options = pred[2].split(",")
        embed.add_field(name=f"#{pred[0]}: {pred[1]}", value=f"Options: {', '.join(options)}\nEnds: <t:{int(pred[3])}:R>", inline=False)
        if pred[4]:
            embed.set_image(url=pred[4])
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="settleprediction", description="Settle a prediction and distribute winnings")
@app_commands.describe(prediction_id="Prediction ID", winning_option="Winning option number")
@commands.cooldown(1, 60, commands.BucketType.user)
async def settleprediction(interaction: discord.Interaction, prediction_id: int, winning_option: int):
    await interaction.response.defer()
    cursor = bot.db.cursor()
    cursor.execute("SELECT creator_id, options, status FROM predictions WHERE id = ?", (prediction_id,))
    pred = cursor.fetchone()
    if not pred or pred[2] != "open":
        await interaction.followup.send("Prediction not found or already settled.", ephemeral=True)
        return
    if pred[0] != interaction.user.id:
        await interaction.followup.send("Only the creator can settle this prediction.", ephemeral=True)
        return
    options = pred[1].split(",")
    if not (1 <= winning_option <= len(options)):
        await interaction.followup.send("Invalid winning option.", ephemeral=True)
        return
    cursor.execute("UPDATE predictions SET status = 'closed' WHERE id = ?", (prediction_id,))
    cursor.execute("SELECT user_id, token, amount, wallet FROM wagers WHERE prediction_id = ? AND option = ?", (prediction_id, winning_option))
    winners = cursor.fetchall()
    total_wagered = sum(w[2] for w in winners)
    if total_wagered == 0:
        await interaction.followup.send("No winners to payout.", ephemeral=True)
        return
    for winner in winners:
        payout = winner[2] * 2  # Simple 2x payout example
        tx_data = await bot.adaptx.prepare_transaction(str(bot.adaptx.bot_pubkey), payout, winner[1], winner[3])
        tx = Transaction.deserialize(base58.b58decode(tx_data['serialized_tx']))
        tx.sign(bot.adaptx.bot_keypair)
        tx_sig = await bot.adaptx.solana_client.send_transaction(tx, opts=Confirmed)
        cursor.execute(
            "INSERT INTO payouts (user_id, prediction_id, token, amount, tx_id) VALUES (?, ?, ?, ?, ?)",
            (winner[0], prediction_id, winner[1], payout, str(tx_sig.value))
        )
    bot.db.commit()
    await interaction.followup.send(f"Prediction #{prediction_id} settled. Option {winning_option} wins! Payouts sent.")

# Enhanced New Features
@bot.tree.command(name="networkanalytics", description="Show recent network TPS trends")
@commands.cooldown(1, 60, commands.BucketType.user)
async def networkanalytics(interaction: discord.Interaction):
    await interaction.response.defer()
    if not network_stats_history:
        await interaction.followup.send("No network stats available yet.")
        return
    tps_values = [entry["tps"] for entry in network_stats_history if entry["tps"] > 0]
    if not tps_values:
        await interaction.followup.send("Network stats not available.")
        return
    avg_tps = sum(tps_values) / len(tps_values)
    min_tps = min(tps_values)
    max_tps = max(tps_values)
    await interaction.followup.send(
        f"**Network Analytics (last 10 minutes):**\n"
        f"• Average TPS: {avg_tps:.2f}\n"
        f"• Minimum TPS: {min_tps:.2f}\n"
        f"• Maximum TPS: {max_tps:.2f}"
    )

@bot.tree.command(name="walletrealtime", description="Subscribe to real-time updates for a wallet")
@app_commands.describe(wallet_address="The wallet address to monitor")
@commands.cooldown(1, 60, commands.BucketType.user)
async def walletrealtime(interaction: discord.Interaction, wallet_address: str):
    await interaction.response.defer()
    if not is_valid_solana_address(wallet_address):
        await interaction.followup.send("Invalid wallet address.", ephemeral=True)
        return
    user_id = interaction.user.id
    realtime_wallet_subscriptions.setdefault(user_id, [])
    if wallet_address in realtime_wallet_subscriptions[user_id]:
        await interaction.followup.send("You are already subscribed to this wallet.")
    else:
        realtime_wallet_subscriptions[user_id].append(wallet_address)
        await interaction.followup.send(f"Subscribed to real-time updates for wallet `{wallet_address}`. You will receive DM notifications.")

@bot.tree.command(name="marketupdate", description="Get a narrative market update")
@commands.cooldown(1, 120, commands.BucketType.user)
async def marketupdate(interaction: discord.Interaction):
    await interaction.response.defer()
    price_info = await bot.adaptx.get_crypto_price_coingecko("solana")
    network_stats = await bot.adaptx.get_solana_network_stats()
    trending = await bot.adaptx.get_trending_tokens()
    prompt = (
        f"Using the following data:\n"
        f"{price_info}\n"
        f"{network_stats}\n"
        f"Trending tokens: {trending}\n\n"
        f"Generate an engaging market update summary for Solana."
    )
    update = await mistral_client.generate_text(prompt, max_tokens=200)
    await interaction.followup.send(f"**Market Update:**\n{update}")

@bot.tree.command(name="solanainsights", description="Get insights on staking and validator performance")
@commands.cooldown(1, 120, commands.BucketType.user)
async def solanainsights(interaction: discord.Interaction):
    await interaction.response.defer()
    top_validators = await bot.adaptx.get_top_validators()
    staking_info = "For detailed staking analytics, use /stakinganalysis with your wallet."
    prompt = (
        f"Given the following validator data:\n{top_validators}\n"
        f"And the following staking info:\n{staking_info}\n\n"
        f"Provide a summary of the current state of Solana validators and staking rewards."
    )
    insights = await mistral_client.generate_text(prompt, max_tokens=200)
    await interaction.followup.send(f"**Solana Insights:**\n{insights}")

@bot.tree.command(name="userfeedback", description="Submit feedback for the bot")
@app_commands.describe(feedback="Your feedback message")
@commands.cooldown(1, 60, commands.BucketType.user)
async def userfeedback(interaction: discord.Interaction, feedback: str):
    await interaction.response.defer()
    cursor = bot.db.cursor()
    cursor.execute("INSERT INTO feedback (user_id, feedback, timestamp) VALUES (?, ?, ?)",
                   (interaction.user.id, feedback, datetime.utcnow().timestamp()))
    bot.db.commit()
    prompt = f"User {interaction.user} submitted the following feedback: '{feedback}'. Generate a friendly thank-you note."
    thank_you = await mistral_client.generate_text(prompt, max_tokens=50)
    await interaction.followup.send(f"Feedback received. {thank_you}")

# Additional New Features
@bot.tree.command(name="cryptohistory", description="Get historical price data for a cryptocurrency")
@app_commands.describe(crypto="Cryptocurrency symbol", days="Number of days of history")
@commands.cooldown(1, 60, commands.BucketType.user)
async def cryptohistory(interaction: discord.Interaction, crypto: str, days: int):
    await interaction.response.defer()
    url = f"https://api.coingecko.com/api/v3/coins/{crypto.lower()}/market_chart?vs_currency=usd&days={days}"
    try:
        async with bot.adaptx.session.get(url, timeout=10) as response:
            data = await response.json()
            prices = data.get("prices", [])
            if not prices:
                await interaction.followup.send("No historical data found.")
                return
            first_price = prices[0][1]
            last_price = prices[-1][1]
            await interaction.followup.send(
                f"**Historical Prices for {crypto.upper()}**\n"
                f"Over the last {days} days:\n"
                f"• Start Price: ${first_price:,.2f}\n"
                f"• Latest Price: ${last_price:,.2f}"
            )
    except Exception as e:
        logger.error(f"Error fetching historical prices: {e}")
        await interaction.followup.send("Error fetching historical prices.", ephemeral=True)

@bot.tree.command(name="nftdetails", description="Get detailed metadata for a specific NFT")
@app_commands.describe(nft_mint="The NFT's mint address")
@commands.cooldown(1, 60, commands.BucketType.user)
async def nftdetails(interaction: discord.Interaction, nft_mint: str):
    await interaction.response.defer()
    if not is_valid_solana_address(nft_mint):
        await interaction.followup.send("Invalid NFT mint address.", ephemeral=True)
        return
    url = f"https://api.helius.xyz/v0/tokens/{nft_mint}/metadata?api-key={HELIUS_API_KEY}"
    try:
        async with bot.adaptx.session.get(url, timeout=10) as response:
            data = await response.json()
            if 'metadata' in data:
                metadata = data['metadata']
                await interaction.followup.send(
                    f"**NFT Details for `{nft_mint}`**\n"
                    f"• Name: {metadata.get('name', 'N/A')}\n"
                    f"• Symbol: {metadata.get('symbol', 'N/A')}\n"
                    f"• Description: {metadata.get('description', 'N/A')}\n"
                    f"• URI: {metadata.get('uri', 'N/A')}"
                )
            else:
                await interaction.followup.send("No metadata found for this NFT.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error fetching NFT details: {e}")
        await interaction.followup.send("Error fetching NFT details.", ephemeral=True)

@bot.tree.command(name="validatorsearch", description="Search validators with commission below a threshold")
@app_commands.describe(max_commission="Maximum commission percentage")
@commands.cooldown(1, 60, commands.BucketType.user)
async def validatorsearch(interaction: discord.Interaction, max_commission: int):
    await interaction.response.defer()
    try:
        vote_accounts = await bot.adaptx.solana_client.get_vote_accounts()
        matching = [f"{str(v.vote_pubkey)[:8]}... - Commission: {v.commission}%" for v in vote_accounts.value.current if v.commission <= max_commission]
        if matching:
            await interaction.followup.send("**Validators with commission <= {}%:**\n{}".format(max_commission, "\n".join(matching[:10])))
        else:
            await interaction.followup.send("No validators found.", ephemeral=True)
    except Exception as e:
        logger.error(f"Error in validatorsearch: {e}")
        await interaction.followup.send("Error searching validators.", ephemeral=True)

@bot.tree.command(name="solanadashboard", description="Display a comprehensive Solana dashboard")
@commands.cooldown(1, 120, commands.BucketType.user)
async def solanadashboard(interaction: discord.Interaction):
    await interaction.response.defer()
    price_info = await bot.adaptx.get_crypto_price_coingecko("solana")
    network_stats = await bot.adaptx.get_solana_network_stats()
    trending = await bot.adaptx.get_trending_tokens()
    top_validators = await bot.adaptx.get_top_validators()
    embed = Embed(title="Solana Dashboard", color=0x00FF00)
    embed.add_field(name="Price Info", value=price_info, inline=False)
    embed.add_field(name="Network Stats", value=network_stats, inline=False)
    embed.add_field(name="Trending Tokens", value=trending, inline=False)
    embed.add_field(name="Top Validators", value=top_validators, inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="airdrop", description="Simulate an airdrop awarding points")
@commands.cooldown(1, 120, commands.BucketType.user)
async def airdrop(interaction: discord.Interaction):
    await interaction.response.defer()
    points_awarded = random.randint(10, 100)
    cursor = bot.db.cursor()
    cursor.execute("SELECT points FROM users WHERE id = ?", (interaction.user.id,))
    result = cursor.fetchone()
    if result:
        new_points = result[0] + points_awarded
        cursor.execute("UPDATE users SET points = ? WHERE id = ?", (new_points, interaction.user.id))
    else:
        new_points = points_awarded
        cursor.execute("INSERT INTO users (id, points) VALUES (?, ?)", (interaction.user.id, new_points))
    bot.db.commit()
    await interaction.followup.send(f"Airdrop! You have been awarded {points_awarded} points. Total points: {new_points}.")

# --- Main Entry Point ---

async def main():
    async with aiohttp.ClientSession() as session:
        bot.adaptx = AdaptX(session)
        bot.db = sqlite3.connect('bot.db')
        bot.db.executescript('''
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, wallet TEXT);
            CREATE TABLE IF NOT EXISTS wallet_tracking (wallet_address TEXT, user_id INTEGER, channel_id INTEGER, last_analysis TEXT);
            CREATE TABLE IF NOT EXISTS alerts (user_id INTEGER, token TEXT, condition TEXT, value REAL);
            CREATE TABLE IF NOT EXISTS lottery (user_id INTEGER, token TEXT, amount REAL);
            CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY, title TEXT, creator_id INTEGER, creator_wallet TEXT, options TEXT, end_time REAL, status TEXT, image_url TEXT);
            CREATE TABLE IF NOT EXISTS wagers (user_id INTEGER, prediction_id INTEGER, token TEXT, amount REAL, option INTEGER, wallet TEXT, tx_id TEXT);
            CREATE TABLE IF NOT EXISTS payouts (user_id INTEGER, prediction_id INTEGER, token TEXT, amount REAL, tx_id TEXT);
            CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, feedback TEXT, timestamp REAL);
        ''')
        bot.db.commit()
        collect_network_stats.start()
        refresh_solana_stats.start()
        check_wallet_updates.start()
        check_price_alerts.start()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())