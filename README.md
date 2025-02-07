# AdaptX v2.0 - Crypto Content & Analysis Discord Bot

**AdaptX** is an all-in-one crypto content and analysis Discord bot designed to deliver unapologetic, unfiltered insights into the world of cryptocurrency. Leveraging advanced AI-driven features alongside live blockchain data, AdaptX helps you generate tweet ideas, analyze transactions, fetch crypto prices, and much more—all with a raw, brutally honest style.

---

## Features

- **Unfiltered AI Insights:**  
  Generate brutally honest tweet ideas and crypto analyses with an edgy, no–holds–barred personality.

- **Memecoin Research:**  
  Receive detailed reports on specific Solana memecoins (e.g., `$BONK`, `$SAMO`, etc.) with the `/memereport` command.

- **Crypto News & Quotes:**  
  Stay updated on market trends using `/news` and get inspiring (yet raw) crypto quotes with `/quote`.

- **Blockchain Analysis:**  
  Analyze transactions on Solana or Ethereum using the `/analyze` command for a quick risk assessment.

- **Price Tracking:**  
  Check current prices of various cryptocurrencies in USD via the `/price` command.

- **Viral & Trend Tools:**  
  - Generate viral tweet hooks with `/viralhook`  
  - Craft engaging reply hooks using `/replyhook`  
  - Predict trending crypto topics with `/trendwatch`

- **Wallet Guides:**  
  Step-by-step guides for popular crypto wallets (Phantom, Backpack, Solflare, MetaMask, Xverse, Magic Eden) are available in the `/wallet` group.

- **Heuristic Analysis:**  
  Tools like `/trendpredict`, `/whalewatcher`, `/riskassessment`, `/alphaalerts`, and `/shadowindex` provide local heuristic insights on market sentiment and potential opportunities.

- **Project Roadmap:**  
  Use the `/roadmap` command to view a detailed 1-year roadmap outlining upcoming features and milestones.

- **Extensive Documentation:**  
  Access full documentation of all features using the `/documentation` command (now optimized to handle long responses).

---

## Setup Instructions

### Prerequisites

- **Python 3.8+**  
- Required Python packages (listed in `requirements.txt`):
  - `discord.py`
  - `python-dotenv`
  - `openai`
  - `requests`
  - `beautifulsoup4`
  - `solana`
  - `web3`
- Valid API keys for:
  - [Discord Bot](https://discord.com/developers/applications)
  - [OpenAI](https://openai.com/api/)
  - [Infura](https://infura.io/)

### Environment Variables

Create a `.env` file in the project’s root directory with the following content:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
INFURA_API_KEY=your_infura_api_key

## Roadmap
View our project roadmap [here](ROADMAP.md).