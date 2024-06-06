import ccxt, os, time, csv, config
from datetime import datetime
import pandas as pd
import pandas_ta as ta

# Gate
exchange = ccxt.gate({
    'apiKey': config.GAPI_KEY,
    'secret': config.GAPI_SECRET,
})

# Define strategy parameters
symbol = 'XCAD_USDT'
spread = 0.015  # 1.5%
order_refresh_time = 65  # seconds
order_amount = 10  # XCAD
max_open_orders = 2
max_retries = 5
retry_delay = 5  # Seconds
min_usdt_balance = 10  # Minimum balance in USDT to continue placing buy orders

# Log file configuration
log_file_path = 'market_maker.csv'
max_log_file_size = 5 * 1024 * 1024  # 5 MB

# Configure CSV logging
csv_file = open(log_file_path, 'a', newline='')
csv_writer = csv.writer(csv_file)

def log_to_csv(level, message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    csv_writer.writerow([timestamp, level, message])
    csv_file.flush()  # Flush the buffer to ensure data is written to the file
    check_log_file_size()  # Check and truncate log file if needed

def check_log_file_size():
    if os.path.getsize(log_file_path) > max_log_file_size:
        truncate_log_file()

def truncate_log_file():
    global csv_file, csv_writer
    csv_file.close()
    with open(log_file_path, 'r+') as file:
        lines = file.readlines()
        file.seek(0)
        file.writelines(lines[-100:])  # Keep only the last 100 lines
        file.truncate()
    csv_file = open(log_file_path, 'a', newline='')
    csv_writer = csv.writer(csv_file)

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
    
    # Adjust spread based on NATR (volatility)
    dynamic_spread = spread * (1 + natr / 100)  # Example: increase spread by a factor of NATR
    
    # Calculate buy and sell prices with dynamic spread
    buy_price = ref_price * (1 - dynamic_spread)
    sell_price = ref_price * (1 + dynamic_spread)
    
    return ref_price, buy_price, sell_price

def place_order(side, price, amount):
    min_order_value_usdt = 3  # Minimum order value in USDT for XCAD_USDT pair
    if price * amount < min_order_value_usdt:
        log_to_csv('ERROR', f"Attempted to place {side} order below minimum order size: Price={price}, Amount={amount}. Minimum order value is {min_order_value_usdt} USDT.")
        return None

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

rebalance_orders = {}  # Dictionary to track rebalance orders

def cancel_all_orders(exclude_ids=[]):
    all_orders = exchange.fetch_open_orders(symbol)
    for order in all_orders:
        if order['id'] not in exclude_ids:
            try:
                exchange.cancel_order(order['id'], symbol)  # Include the symbol here
                log_to_csv('INFO', f"Canceled order: ID={order['id']}, Price={order['price']}, Amount={order['amount']}")
            except Exception as e:
                log_to_csv('ERROR', f"Failed to cancel order: ID={order['id']}. Error: {e}")

def place_rebalance_order(side, amount):
    try:
        if side == 'buy':
            # Fetch the latest market price
            current_price = exchange.fetch_ticker(symbol)['last']
            # Calculate the total cost in USDT for the buy amount
            total_cost = current_price * amount
            # Place a market buy order by specifying the total cost directly
            order = exchange.create_order(symbol, 'market', 'buy', None, total_cost, {'cost': total_cost})
        else:
            # Place a market sell order by specifying the amount directly
            order = exchange.create_market_sell_order(symbol, amount)
        
        log_to_csv('INFO', f"Rebalance {side.capitalize()} Market Order for XCAD: ID={order['id']}, Amount={order['amount']}")
        rebalance_orders[order['id']] = {'side': side, 'amount': amount}
        return order
    except Exception as e:
        log_to_csv('ERROR', f"Error placing {side} market order: {e}")
        return None

def check_balance():
    balance = exchange.fetch_balance()
    usdt_balance = balance['total']['USDT']
    xcda_balance = balance['total']['XCAD']
    return usdt_balance, xcda_balance

def main():
    try:
        while True:
            ohlcv = get_ohlcv(symbol)
            if ohlcv is None:
                log_to_csv('CRITICAL', "Failed to fetch OHLCV data. Exiting...")
                break
            
            indicators = calculate_indicators(ohlcv)
            ref_price, buy_price, sell_price = get_reference_price(indicators)
            usdt_balance, xcda_balance = check_balance()
            log_to_csv('INFO', f"USDT Balance: {usdt_balance}, XCAD Balance: {xcda_balance}")
            
            cancel_all_orders(exclude_ids=list(rebalance_orders.keys()))

            # Existing rebalance order handling
            for order_id in list(rebalance_orders.keys()):
                try:
                    order_info = exchange.fetch_order(order_id, symbol)  # Include the symbol here
                    if order_info['status'] in ['closed', 'canceled']:
                        del rebalance_orders[order_id]
                except Exception as e:
                    log_to_csv('ERROR', f"Failed to fetch order: ID={order_id}. Error: {e}")

            # Calculate the minimum XCAD amount to meet the 3 USDT order value requirement
            min_xcad_for_usdt = 3 / sell_price
            min_order_amount = max(order_amount, min_xcad_for_usdt)

            # Check if rebalance is needed
            if xcda_balance < min_order_amount and usdt_balance >= buy_price * min_order_amount:
                # Not enough XCAD to sell, but enough USDT to buy XCAD
                place_rebalance_order('buy', min_order_amount)
            elif usdt_balance < buy_price * min_order_amount and xcda_balance >= min_order_amount:
                # Not enough USDT to buy, but enough XCAD to sell
                place_rebalance_order('sell', min_order_amount)

            # Regular buy and sell orders
            if usdt_balance >= buy_price * order_amount:
                buy_order = place_order('buy', buy_price, order_amount)
                if buy_order:
                    log_to_csv('INFO', f"Buy Order: ID={buy_order['id']}, Price={buy_order['price']}, Amount={buy_order['amount']}")
            
            if xcda_balance >= order_amount:
                sell_order = place_order('sell', sell_price, order_amount)
                if sell_order:
                    log_to_csv('INFO', f"Sell Order: ID={sell_order['id']}, Price={sell_order['price']}, Amount={sell_order['amount']}")

            time.sleep(order_refresh_time)
    finally:
        csv_file.close()

if __name__ == "__main__":
    main()
