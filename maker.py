import ccxt
import time
import logging
from datetime import datetime
from decimal import Decimal
import config
import pandas as pd
import pandas_ta as ta
import csv

# Gate
exchange = ccxt.gate({
    'apiKey': config.API_KEY,
    'secret': config.API_SECRET,
})

# Define strategy parameters
symbol = 'XCAD_USDT'
spread = 0.013  # 1.3%
order_refresh_time = 75  # seconds
order_amount = 100  # XCAD
max_open_orders = 2
max_retries = 5
retry_delay = 5  # Seconds

# Configure CSV logging
csv_file = open('market_maker.csv', 'a', newline='')
csv_writer = csv.writer(csv_file)

def log_to_csv(level, message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    csv_writer.writerow([timestamp, level, message])
    csv_file.flush()  # Flush the buffer to ensure data is written to the file

def get_ohlcv(symbol, timeframe='1m', limit=100):
    for attempt in range(max_retries):
        try:
            return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception as e:
            log_to_csv('ERROR', f"Error fetching OHLCV data: {e}. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    log_to_csv('CRITICAL', "Max retries reached. Failed to fetch OHLCV data.")
    return None

def calculate_indicators(ohlcv):
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['natr'] = ta.natr(df['high'], df['low'], df['close'], length=14)
    return df

def get_reference_price(indicators):
    last_close = indicators['close'].iloc[-1]
    rsi = indicators['rsi'].iloc[-1]
    natr = indicators['natr'].iloc[-1]
    
    # Adjust mid price based on RSI
    mid_price_shift = (rsi - 50) / 1000
    ref_price = last_close * (1 + mid_price_shift)
    
    # Adjust spreads based on NATR
    spread_factor = 1 + natr / 100
    buy_price = ref_price * (1 - spread)
    sell_price = ref_price * (1 + spread)
    
    return ref_price, buy_price, sell_price

def place_order(side, price, amount):
    for attempt in range(max_retries):
        try:
            order = exchange.create_limit_order(symbol, side, amount, price)
            log_to_csv('INFO', f"Placed {side} order: ID={order['id']}, Price={order['price']}, Amount={order['amount']}")
            return order
        except Exception as e:
            log_to_csv('ERROR', f"Error placing {side} order: {e}. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    log_to_csv('CRITICAL', f"Max retries reached. Failed to place {side} order.")
    return None

def cancel_all_orders():
    for attempt in range(max_retries):
        try:
            open_orders = exchange.fetch_open_orders(symbol)
            for order in open_orders:
                exchange.cancel_order(order['id'], symbol)
                log_to_csv('INFO', f"Canceled order: ID={order['id']}, Price={order['price']}, Amount={order['amount']}")
            return
        except Exception as e:
            log_to_csv('ERROR', f"Error cancelling orders: {e}. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    log_to_csv('CRITICAL', "Max retries reached. Failed to cancel all orders.")

def check_and_replenish_funds(last_order, last_order_price):
    try:
        balance = exchange.fetch_balance()
        asset_balance = balance['total']['XCAD']
        usdt_balance = balance['total']['USDT']
        
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        replenishment_threshold = 0.01  # 1% above or below the last order price
        
        if last_order == 'buy' and usdt_balance < order_amount * current_price:
            replenishment_sell_price = last_order_price * (1 + replenishment_threshold)
            if current_price > replenishment_sell_price:
                place_order('sell', replenishment_sell_price, order_amount)
                log_to_csv('INFO', f"Placed replenishment sell order at {replenishment_sell_price} due to low USDT balance.")
        elif last_order == 'sell' and asset_balance < order_amount:
            replenishment_buy_price = last_order_price * (1 - replenishment_threshold)
            if current_price < replenishment_buy_price:
                place_order('buy', replenishment_buy_price, order_amount)
                log_to_csv('INFO', f"Placed replenishment buy order at {replenishment_buy_price} due to low XCAD balance.")
    except Exception as e:
        log_to_csv('ERROR', f"Error checking/replenishing funds: {e}")

def check_funds_and_place_orders(buy_price, sell_price):
    balance = exchange.fetch_balance()
    asset_balance = balance['total']['XCAD']
    usdt_balance = balance['total']['USDT']
    
    # Calculate required USDT for buy order
    required_usdt = order_amount * buy_price
    # Check if there's enough USDT to place buy order
    if usdt_balance >= required_usdt:
        buy_order = place_order('buy', buy_price, order_amount)
    else:
        log_to_csv('WARNING', "Not enough USDT balance to place buy order.")
        buy_order = None
    
    # Check if there's enough XCAD to place sell order
    if asset_balance >= order_amount:
        # Increase the sell price slightly to avoid immediate fulfillment
        sell_price = sell_price * 1.005
        sell_order = place_order('sell', sell_price, order_amount)
    else:
        log_to_csv('WARNING', "Not enough XCAD balance to place sell order.")
        sell_order = None

    return buy_order, sell_order

def main():
    last_order = None
    last_order_price = None

    try:
        while True:
            ohlcv = get_ohlcv(symbol)
            if ohlcv is None:
                log_to_csv('CRITICAL', "Failed to fetch OHLCV data. Exiting...")
                break
            
            indicators = calculate_indicators(ohlcv)
            
            ref_price, buy_price, sell_price = get_reference_price(indicators)
            
            # Calculate spread percentage
            spread_percentage = ((sell_price - buy_price) / ref_price) * 100
            
            # Check if spread exceeds 1.3%
            if spread_percentage >= 1.3:
                cancel_all_orders()
                
                buy_order, sell_order = check_funds_and_place_orders(buy_price, sell_price)
                
                if buy_order:
                    log_to_csv('INFO', f"Buy Order: ID={buy_order['id']}, Price={buy_order['price']}, Amount={buy_order['amount']}")
                    last_order = 'buy'
                    last_order_price = buy_order['price']
                if sell_order:
                    log_to_csv('INFO', f"Sell Order: ID={sell_order['id']}, Price={sell_order['price']}, Amount={sell_order['amount']}")
                    last_order = 'sell'
                    last_order_price = sell_order['price']
            else:
                log_to_csv('INFO', f"Spread ({spread_percentage:.2f}%) is less than 1.3%. Not placing orders.")
            
            check_and_replenish_funds(last_order, last_order_price)
            
            time.sleep(order_refresh_time)
    finally:
        csv_file.close()

if __name__ == "__main__":
    main()
