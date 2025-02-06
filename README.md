# SolShieldX Discord Bot

SolShieldX is a multi-functional Discord bot designed for blockchain security and crypto trend content generation. It leverages OpenAI's GPT-3.5-turbo for generating creative tweet ideas and variants, uses Twitter API v2 to fetch trending topics and influencer activity, and even provides basic blockchain transaction analysis via Solana and Ethereum.

## Features

- **Post Idea Generation:**  
  Uses OpenAI's GPT-3.5-turbo to generate a single tweet idea about blockchain security trends.

- **Tweet Variants:**  
  Generates multiple tweet variants for A/B testing to help refine content strategy.

- **Trending Topics:**  
  Fetches current trending topics from Twitter related to blockchain, crypto, and web3.

- **Influencer Monitoring:**  
  Retrieves the latest tweets from a predefined list of influencers.

- **Blockchain Transaction Analysis:**  
  Provides a simplified risk analysis for Solana and Ethereum transactions.

- **Command Testing:**  
  Includes a simple `!ping` command to test if the bot is running.

## Prerequisites

Before you begin, ensure you have the following:

- Python 3.9 or later installed.
- A virtual environment set up for your project.
- A Discord bot token, obtained from the [Discord Developer Portal](https://discord.com/developers/applications).
- OpenAI API key (with access to GPT-3.5-turbo) from [OpenAI](https://platform.openai.com).
- Twitter API credentials (Consumer Key, Consumer Secret, Access Token, Access Token Secret, and Bearer Token) from [Twitter Developer Portal](https://developer.twitter.com/).
- Infura API key (for Ethereum blockchain access) from [Infura](https://infura.io/).
- A `threat_feeds.json` file in the project root (it can be empty or contain basic data, e.g., `{"addresses": {}}`).

## Installation

1. **Clone the repository (if not already):**

   ```bash
   git clone https://github.com/<your-username>/<your-repo-name>.git
   cd <your-repo-name>
