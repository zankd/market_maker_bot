import ccxt
import time
import logging
from datetime import datetime
from decimal import Decimal
import config
import pandas as pd
import pandas_ta as ta 

# Gate io
exchange = ccxt.gate({
    'apiKey': config.API_KEY,
    'secret': config.API_SECRET,
})

# exchange.set_sandbox_mode(True)

# Define strategy parameters
symbol = 'XCAD_USDT'
spread = 0.01  # 1%
order_refresh_time = 75  # seconds
order_amount = 15  # XCAD
max_open_orders = 2
max_retries = 5  
retry_delay = 5 # Seconds

# Configure logging
logging.basicConfig(level=logging.INFO, filename='market_maker.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def get_ohlcv(symbol, timeframe='1m', limit=100):
    for attempt in range(max_retries):
        try:
            return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception as e:
            logger.error(f"Error fetching OHLCV data: {e}. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    logger.critical("Max retries reached. Failed to fetch OHLCV data.")
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
    buy_price = ref_price * (1 - spread * spread_factor)
    sell_price = ref_price * (1 + spread * spread_factor)
    
    return ref_price, buy_price, sell_price

def place_order(side, price, amount):
    for attempt in range(max_retries):
        try:
            order = exchange.create_limit_order(symbol, side, amount, price)
            logger.info(f"Placed {side} order: ID={order['id']}, Price={order['price']}, Amount={order['amount']}")
            return order
        except Exception as e:
            logger.error(f"Error placing {side} order: {e}. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    logger.critical(f"Max retries reached. Failed to place {side} order.")
    return None

def cancel_all_orders():
    for attempt in range(max_retries):
        try:
            open_orders = exchange.fetch_open_orders(symbol)
            for order in open_orders:
                exchange.cancel_order(order['id'], symbol)
                logger.info(f"Canceled order: ID={order['id']}, Price={order['price']}, Amount={order['amount']}")
            return
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}. Attempt {attempt + 1} of {max_retries}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    logger.critical("Max retries reached. Failed to cancel all orders.")

def main():
    while True:
        ohlcv = get_ohlcv(symbol)
        if ohlcv is None:
            logger.critical("Failed to fetch OHLCV data. Exiting...")
            break
        
        indicators = calculate_indicators(ohlcv)
        
        ref_price, buy_price, sell_price = get_reference_price(indicators)
        
        cancel_all_orders()
        
        buy_order = place_order('buy', buy_price, order_amount)
        sell_order = place_order('sell', sell_price, order_amount)
        
        if buy_order:
            logger.info(f"Buy Order: ID={buy_order['id']}, Price={buy_order['price']}, Amount={buy_order['amount']}")
        if sell_order:
            logger.info(f"Sell Order: ID={sell_order['id']}, Price={sell_order['price']}, Amount={sell_order['amount']}")
        
        time.sleep(order_refresh_time)

if __name__ == "__main__":
    main()
