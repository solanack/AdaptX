import os
import discord
from discord.ext import commands
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import tweepy

nltk.download('vader_lexicon', quiet=True)
sia = SentimentIntensityAnalyzer()

class AIToolsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        auth = tweepy.OAuthHandler(os.getenv("TWITTER_API_KEY"), os.getenv("TWITTER_API_SECRET"))
        self.api = tweepy.API(auth)

    @commands.command(name="sentiment")
    async def sentiment(self, ctx, project: str):
        """Analyzes Twitter sentiment for a project."""
        try:
            tweets = self.api.search_tweets(q=project, count=100)
            scores = [sia.polarity_scores(tweet.text)['compound'] for tweet in tweets]
            positive = sum(1 for score in scores if score > 0.05)
            await ctx.send(f"Sentiment for {project}: {positive / len(scores) * 100:.2f}% positive")
        except Exception as e:
            await ctx.send(f"Error analyzing sentiment: {e}")

    @commands.command(name="predict")
    async def predict(self, ctx, token: str):
        """Predicts 24h trend (placeholder)."""
        # Implement with CoinGecko historical data if desired
        await ctx.send(f"Predicted 24h trend for {token}: Up (placeholder)")

async def setup(bot):
    await bot.add_cog(AIToolsCog(bot))