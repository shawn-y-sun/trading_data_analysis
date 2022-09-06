import requests # loads the REQUESTS package, allows us to use the get, post, and Session functions
import time
import threading
import numpy as np

########## CHANGE THIS API KEY ##########
API_KEY = 'GWMV82CC'
#########################################

s = requests.Session() # assigns the SESSION() function from REQUESTS to the variable "s"
s.headers.update({'X-API-key': API_KEY}) # assigns the API key "V4PYCGCW" to the header of "s", so every message we send to RIT contains the API key ; you will use the API key for your RIT

ORDER_ENDPOINT = 'http://localhost:9999/v1/orders'
CASE_ENDPOINT = 'http://localhost:9999/v1/case'
ORDER_BOOK_ENDPOINT = 'http://localhost:9999/v1/securities/book'
POSITIONS_ENDPOINT = 'http://localhost:9999/v1/securities'
TAS_ENDPOINT = 'http://localhost:9999/v1/securities/tas'
ORDER_DELETE_ENDPOINT = 'http://localhost:9999/v1/orders/{}'

MAX_LONG_EXPOSURE = 5000 # assign the variable MAX_LONG_EXPOSURE a value of 25,000 - the maximum number of shares I want to be long at any point in time
MAX_SHORT_EXPOSURE = -5000 # assign the variable MAX_SHORT_EXPOSURE a value of -25,000 - the maximum number of shares I want to be short at any point in time
ORDER_LIMIT = {'AC': 1000}
SPREAD_MAX = 0.50
ORDER_COUNT = 5
SPEED_BUMP = 0.25
TRADER_DIFF = 0.05
TILT_THRESHOLD = 9
TILT_SPREAD = 0.00
AGGRESSIVE_SPREAD = 0.01
TRADE_SPREAD = AGGRESSIVE_SPREAD*2+0.00
MAX_THREADS = 20
STASIS_MAX = 1

last_traded = 0
current_position = {}
last_prices = {}

def get_tick_status(): # defines a function called "get_tick_status" when defining a function the brackets () and colon : must be included. Any values you send to the function "get_tick_status" would be stored in the variable names in the brackets, which we will not use in this function. The colon tells Python that the definition statement is done and the function's code is next
    resp = s.get(CASE_ENDPOINT) # uses the "get" function from REQUESTS, in combination with the variable "s" - hence the "s.get" - to send a request (i.e. get information from) to http://localhost:9999/v1/case and store the information that comes back in the variable "resp"
    if resp.ok: # uses the IF statement and the "ok" function from REQUESTS to check IF the status code of the variable "resp" is ok (meaning the status code is 200); if the status code is 200, go to the next line, otherwise skip 
        case = resp.json() # uses the "json" function from REQUESTS to parse or reformat the data in "resp" using the JSON format, then storing the parsed/reformatted data in the variable "case"
        return case['tick'], case['status'] # return two separate pieces of information, separated by commas, to the variables that called "get_tick_status" - see line 47 - the variable "case" contains a "dictionary" of variables, each of which has a "key" (or name) and a value; this line is returning the value of the variable called "tick" and the value of the variable called "status" from the dictionary called "case"; the value of case['tick'] will be assigned to the variable "tick" on line 47, the value of case['status'] will be assigned to the variable "status" on line 47
    else:
        print('Connection Error')
        return resp.ok, resp.json()

def get_bid_ask(ticker):
    payload = {'ticker': ticker} # assigns the value of "ticker" to the key (or name) "ticker" in the dictionary "payload" - note the curly brackets surrounding the dictionary
    resp = s.get(ORDER_BOOK_ENDPOINT, params = payload) # attaches the dictionary "payload" to the parameters ("params") that are included in the "get" request sent to RIT; in this case "params" includes the ticker symbol that tells RIT which order book to retrieve
    if resp.ok:
        book = resp.json() # stores the parsed data from "resp" in a variable named "book"; "book" is a list that contains two lists (one called "bids" and one called "asks") - similar to a folder called "book" that has two sub-folders, one called "bids" and the other called "asks" - and each of the "bids" and "asks" lists are made up of a list of items, with each item in the list being a dictionary that contains the information for each order in the order book
        bid_side_book = book['bids'] # creates a new list called "bid_side_book" composed of all the items/dictionaries from the "bids" list in "book"
        ask_side_book = book['asks'] # creates a new list called "ask_side_book" composed of all the items/dictionaries from the "asks" list in "book"
        
        bid_prices_book = [item["price"] for item in bid_side_book] # assigns the list "bid_prices_book" the "price" values for all bids in bid_side_book
        ask_prices_book = [item['price'] for item in ask_side_book] # assigns the list "ask_prices_book" the "price" values for all asks in ask_side_book
        
        best_bid_price_fn = bid_prices_book[0] # assigns the variable "best_bid_price_fn" the value of the first item in the "bid_prices_book" list (this is the highest bid price, or the "top of the book"; note that counting in Python starts at 0, so the first item in a list is item 0, the second item in a list is item 1, the third item in a list is item 2, etc. 
        best_ask_price_fn = ask_prices_book[0] # assigns the variable "best_ask_price_fn" the value of the first item in the "ask_prices_book" list (this is the lowest ask price, or the "top of the book")
  
        return best_bid_price_fn, best_ask_price_fn, bid_side_book, ask_side_book # returns the values from the function to the variables on line 94: the value of "best_bid_price_fn" will be assigned to variable "best_bid_price" on line 94, the value of "best_ask_price_fn" will be assigned to variable "best_ask_price" on line 94

def get_time_sales(ticker):
    payload = {'ticker': ticker}
    resp = s.get(TAS_ENDPOINT, params = payload)
    if resp.ok:
        book = resp.json()
        time_sales_book = [item["quantity"] for item in book]
        return time_sales_book # returns the list "time_sales_book"; the variable that is assigned this value when calling the function must be able to hold a list of values

def get_position():
    global current_position
    resp = s.get(POSITIONS_ENDPOINT)
    if resp.ok:
        book = resp.json()
        
        for i in range(3):
            current_position[book[i]['ticker']] = {'position': book[i]['position'], 'vwap': book[i]['vwap']}
            # print('Current Position in', book[i]['ticker'], 'is', book[i]['position'])
        
        return abs(book[0]['position']) + abs(book[1]['position']) + abs(book[2]['position']) # sum of absolute position values for all three tradeable stocks; alternatively, can include a ticker symbol in the query to return the data for a particular stock

def get_open_orders(ticker):
    payload = {'ticker': ticker}
    resp = s.get(ORDER_ENDPOINT, params = payload)
    if resp.ok:
        orders = resp.json()
        buy_orders = [item for item in orders if item["action"] == "BUY"] # creates a list in "buy_orders" of all buy orders -> for each dictionary in the list that has a value of "BUY" for the "action" key
        sell_orders = [item for item in orders if item["action"] == "SELL"] # creates a list in "buy_orders" of all buy orders -> for each dictionary in the list that has a value of "SELL" for the "action" key
        return buy_orders, sell_orders # returns two lists of dictionaries, the variables being assigned these value must be able to hold lists of dictionaries

def get_order_status(order_id):
    resp = s.get(ORDER_ENDPOINT + '/' + str(order_id)) # requests the order details for a specific order defined by "order_id" - each order entered into the market has a unique ID
    if resp.ok:
        order = resp.json()
        return order['status'] # returns the status of "order_id" - either "OPEN", "CANCELLED", or "TRANSACTED"\\

def get_ticker_position(ticker):
    global current_position
    
    return current_position[ticker]['position']

def get_ticker_vwap(ticker):
    global current_position
    
    return current_position[ticker]['vwap']
    
def create_order(ticker, action, order_type, quantity, price=0):
    
    params = {
            'ticker': ticker,
            'type': order_type,
            'action': action,
            'quantity': quantity,
            }
    
    if order_type == 'LIMIT':
        params['price'] = price
    
    return params

def check_trending(tick):
    global last_prices
    
    if last_prices[tick] > last_prices[tick-1] and last_prices[tick-1] > last_prices[tick-2] and last_prices[tick-2] > last_prices[tick-3] and last_prices[tick-3] > last_prices[tick-4]:
        return True
    elif last_prices[tick] < last_prices[tick-1] and last_prices[tick-1] < last_prices[tick-2] and last_prices[tick-2] < last_prices[tick-3] and last_prices[tick-3] < last_prices[tick-4]:
        return True
    return False

def start_trading(ticker):
    global ORDER_COUNT
    global last_traded
    global TILT_SPREAD

    tick, status = get_tick_status()
    while status == 'ACTIVE':
        
        for stock in ORDER_LIMIT.keys():
            position = get_position()
            buy_orders, sell_orders = get_open_orders(ticker)
            
            stock_position = get_ticker_position(stock)
            best_bid, best_ask, bid_book, ask_book = get_bid_ask(stock)
            
            bid_vol = sum(item['quantity'] if item['trader_id'] == 'ANON' else 0 for item in bid_book)
            ask_vol = sum(item['quantity'] if item['trader_id'] == 'ANON' else 0 for item in ask_book)
            
            sell_tilt = True if bid_vol / ask_vol > TILT_THRESHOLD else False
            buy_tilt = True if ask_vol / bid_vol > TILT_THRESHOLD else False
                        
            if buy_tilt or sell_tilt:
                print("Tick:", tick, "Bid to ask:", bid_vol / ask_vol, flush=True)
                print(stock, "Bid:", bid_vol, "Ask", ask_vol, flush=True)
            
            last_prices[tick] = (best_bid + best_ask)/2
            bid_ask_spread = best_ask - best_bid
            start = time.time()
            order_amount = ORDER_LIMIT[stock]
            
            trending = True if tick > 5 and check_trending(tick) else False
            
            order_list = []
            
            if stock_position < MAX_LONG_EXPOSURE:
                price = best_bid + AGGRESSIVE_SPREAD
                
                if buy_tilt:
                    price += TILT_SPREAD
                
                for i in range(ORDER_COUNT):
                                    
                    if (bid_ask_spread > TRADE_SPREAD) and not sell_tilt:
                        params = create_order(stock, 'BUY', 'LIMIT', order_amount, price)
                        resp = s.post(ORDER_ENDPOINT, params=params)
                        # print("bought",flush=True)
                        
                        if resp.ok:
                            order_id = resp.json()['order_id']
                            last_traded = tick
                            # print(order_id,flush=True)
                            order_list.append(order_id)
                    # print("Sent buy limit order for", order_amount, ticker, "at", price)
                    
            if stock_position >= MAX_SHORT_EXPOSURE:
                price = best_ask - AGGRESSIVE_SPREAD
                
                if (bid_ask_spread > TRADE_SPREAD) and not buy_tilt:
                    
                    if sell_tilt:
                        price -= TILT_SPREAD
                    
                    for i in range(ORDER_COUNT):
    
                        params = create_order(stock, 'SELL', 'LIMIT', order_amount, price)
                        resp = s.post(ORDER_ENDPOINT, params=params)
                        # print("sold",flush=True)
            
                        if resp.ok:
                            order_id = resp.json()['order_id']
                            last_traded = tick
                            # print(order_id,flush=True)
                            order_list.append(order_id)
                    
                # print("Sent sell limit order for", order_amount, ticker, "at", price)
            
            if tick - last_traded > STASIS_MAX and stock_position != 0:
                
                for i in range(int(stock_position//order_amount)+1):
                    action = 'SELL' if stock_position < 0 else 'BUY'
                    params = create_order(stock, action, 'MARKET', min(order_amount, abs(stock_position)))
                    resp = s.post(ORDER_ENDPOINT, params=params)
                    
                    if resp.ok:
                        print(resp.json())
                        print('Unwound stuck at', stock_position,flush=True)
                    last_traded = tick
            
            time.sleep(SPEED_BUMP) 
            
            for order_id in order_list:
                resp = s.delete(ORDER_DELETE_ENDPOINT.format(order_id))

        tick, status = get_tick_status()

def start_trading_wrapper(ticker):

    try:
        start_trading(ticker)
    except:
        return

def main():
    global ORDER_LIMIT
    tick, status = get_tick_status() # calls the function "get_tick_status" - the brackets must be included when calling the function, and the brackets are empty because no information is being sent to "get_tick_status" - and assigns the first piece of information returned by "get_tick_status" to "tick" and the second piece of information returned by "get_tick_status" to "status"
    ticker_list = list(ORDER_LIMIT.keys()) # creates a list of ticker symbols that are traded in the case which will be cycled in the for loop below
    
    while True:
        if status == 'ACTIVE':
            threads = list()
            sema = threading.Semaphore(value = MAX_THREADS)

            for i, ticker in enumerate(ticker_list*int(MAX_THREADS)):
                time.sleep(TRADER_DIFF)
        
                sema.acquire()
                thread = threading.Thread(target = start_trading_wrapper, args=(ticker,))
                threads.append(thread)
                thread.daemon = True
                thread.start()

            for thread in threads:
                thread.join()
        else:
            print("Waiting for server start", flush=True)
            time.sleep(1)
        
        tick, status = get_tick_status()

if __name__ == '__main__': # "if" statement that check if the embedded/reserved variable "__name__" is equal to "__main__", which is always true
    main() # calls the "main" function; since the if statement is always true, this means you can call your "main" function by running all of the code in the window using the Run File command (pressing sideways triange butting or F5); since all lines of the file are read by Python before the "main" function is called, any changes in the code are incorporated



