Market Maker Bot
Overview
The Market Maker Bot is a Python script designed to automate trading operations on the Gate.io cryptocurrency exchange. It implements a market-making strategy, aiming to profit from the spread between buy and sell prices of a specified trading pair. This bot is built using the CCXT library for interacting with the Gate.io exchange API.

Features
Fetches OHLCV (Open, High, Low, Close, Volume) data for a specified trading pair.
Calculates technical indicators such as RSI (Relative Strength Index) and NATR (Normalized Average True Range) using the Pandas TA library.
Determines reference price, buy price, and sell price based on calculated indicators and configured spread.
Places buy and sell orders on the exchange when spread conditions are met.
Logs trade information and errors to a CSV file for analysis and debugging.
Prerequisites
Python 3.x installed on your system.
CCXT library installed (pip install ccxt).
Pandas and Pandas TA libraries installed (pip install pandas pandas-ta).
Configuration
Before running the script, make sure to:

Replace config.GAPI_KEY and config.GAPI_SECRET with your Gate.io API key and secret.
Adjust strategy parameters such as spread, order_refresh_time, and order_amount according to your trading preferences.
Usage
Clone or download the repository to your local machine.
Navigate to the directory containing the script.
Install dependencies using pip install -r requirements.txt.
Modify the configuration parameters in the script according to your preferences.
Run the script using python market_maker.py.
Logging
The bot logs trade information and errors to a CSV file named market_maker.csv. Each log entry includes a timestamp, log level, and corresponding message.

Disclaimer
This bot is provided for educational purposes only and should not be considered financial advice. Cryptocurrency trading involves risk, and users should exercise caution and perform their own research before engaging in any trading activities.
