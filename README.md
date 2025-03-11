# Market Maker Bot

## Overview
The **Market Maker Bot** is a Python script designed to automate trading operations on the Gate.io cryptocurrency exchange. It implements a market-making strategy, using the [CCXT](https://github.com/ccxt/ccxt) library for interacting with the Gate.io exchange API.

## Features
- Fetches OHLCV (Open, High, Low, Close, Volume) data for a specified trading pair.
- Calculates technical indicators such as RSI (Relative Strength Index) and NATR (Normalized Average True Range) using the Pandas TA library.
- Determines reference price, buy price, and sell price based on calculated indicators and configured spread.
- Places buy and sell orders on the exchange when spread conditions are met.
- Logs trade information and errors to a CSV file for analysis and debugging.

## Prerequisites
1. Python 3.x installed on your system.
2. CCXT library installed (`pip install ccxt`).
3. Pandas and Pandas TA libraries installed (`pip install pandas pandas-ta`).

## Configuration
Before running the script, make sure to:
1. Replace `config.API_KEY` and `config.API_SECRET` with your Gate.io API key and secret.
2. Adjust strategy parameters such as `spread`, `order_refresh_time`, and `order_amount` according to your trading preferences.

## Usage
1. Clone or download the repository to your local machine.
2. Navigate to the directory containing the script.
3. Install dependencies using `pip install -r requirements.txt`.
4. Modify the configuration parameters in the script according to your preferences.
5. Run the script using `python market_maker.py`.

## Logging
The bot logs trade information and errors to a CSV file named `market_maker.csv`. Each log entry includes a timestamp, log level, and the corresponding message.

## Disclaimer
This bot is provided for educational purposes only and should not be considered financial advice. Cryptocurrency trading involves risk, and users should exercise caution and perform their own research before engaging in any trading activities.

