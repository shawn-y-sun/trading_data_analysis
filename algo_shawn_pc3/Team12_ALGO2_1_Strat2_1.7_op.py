import requests # we need a package to access RIT via API, there may be other packages that can perform the same role (we are using requests to make an HTTP connection)
from time import sleep # to slow the Python loop we will want to be able to pause the code; the purpose is to correct for different processing speeds in this Python code vs. the RIT server; this is NOT the best way to accomplish this task, ideally the code would have a more exacting way of control the flow of the Python code...
import threading

s = requests.Session() # necessary to keep Python from having socket connection errors; not using Session() means Python would keep opening and closing the socket connection to RIT which causes errors as the connection may not have completed closing when the next opening is attempted
s.headers.update({'X-API-key': '0BCIUU0S'}) # convenience, so we do not need to separately include the API Key in our messages to RIT as it is already included when we use "s"

## Note: from 1.5 to assign different sleep time to different stocks
# variables that are not changing while the case is running, and may appear in multiple spots - one change in the variable here applies to every instance, otherwise I would have to go through the code to change every instance; these are not inside a function which makes them "global" instead of "local" and they can be used by any function
MAX_LONG_EXPOSURE = 25000
MAX_SHORT_EXPOSURE = -25000
IND_MAX_LONG_EXPOSURE = {'CNR': 2500, 'RY': 20000, 'AC': 2500} 
IND_MAX_SHORT_EXPOSURE = {'CNR': -2500, 'RY': -20000, 'AC': -2500} 
WARNING_LONG_LIMIT = {'CNR': 2500, 'RY': 17000, 'AC': 2500} 
WARNING_SHORT_LIMIT = {'CNR': -2500, 'RY': -17000, 'AC': -2500} 
ORDER_LIMIT = {'CNR': 700, 'RY': 5000, 'AC': 700}
SPREAD_LIMIT = {'CNR': 0.06, 'RY': 0, 'AC': 0.1}
SLEEP_TIME = {'CNR': 0.1, 'RY': 0.3, 'AC': 0.1}
price_incr = 0.01
trader_num = {'CNR': 20, 'RY': 50, 'AC': 10}


CASE_PATH = 'http://localhost:9999/v1/case'
BOOK_PATH = 'http://localhost:9999/v1/securities/book'
ORDER_PATH = 'http://localhost:9999/v1/orders'

def get_tick(): # this function queries the status of the case ("ACTIVE", "STOPPED", "PAUSED") which we will use in our "while" loop
    resp = s.get(CASE_PATH)
    if resp.ok:
        case = resp.json()
        return case['tick'], case['status'] # this code does not use the "tick" value, but may be useful if the code is modified

def get_bid_ask(ticker): # this function queries the order book for price data, specifically finds the best bid and offer (BBO) prices; the same get request has additional information, like quantity (see the dictionary output of a query); the decision-making of the code depends on the bid-ask quote
    payload = {'ticker': ticker}
    resp = s.get (BOOK_PATH, params = payload)
    if resp.ok:
        book = resp.json()
        bid_side_book = book['bids']
        ask_side_book = book['asks']
        
        bid_prices_book = [item["price"] for item in bid_side_book]
        ask_prices_book = [item['price'] for item in ask_side_book]
        
        best_bid_price = bid_prices_book[0]
        best_ask_price = ask_prices_book[0]
  
        return best_bid_price, best_ask_price

def get_time_sales(ticker): # not used in the body of the code, but provides a history of the trades for the selected stock, possibly something that could be used in a strategy
    payload = {'ticker': ticker}
    resp = s.get ('http://localhost:9999/v1/securities/tas', params = payload)
    if resp.ok:
        book = resp.json()
        time_sales_book = [item["quantity"] for item in book]
        return time_sales_book

def get_position(): # this function queries my position and calcualtes the gross position across all stocks in the case; the case has 2 limits, net and gross, with separate fines for each - this function is NOT returning the net position, which might be useful in some cases...
    resp = s.get ('http://localhost:9999/v1/securities')
    if resp.ok:
        book = resp.json()
        return abs(book[0]['position']) + abs(book[1]['position']) + abs(book[2]['position']) # summing without the abs() functions would produce the net position

def get_ticker_book_info(ticker):
    resp = s.get ('http://localhost:9999/v1/securities')
    if resp.ok:
        book = resp.json()
        ticker_lst = [i for i in book if i['ticker']==ticker]
        return ticker_lst[0]

def get_open_orders(ticker): # this function gets all open orders for a particular ticker symbol (can be used without the ticker symbol and would return all outstanding orders for all stocks in the case); since the market making strategy in this code uses limit orders, it may be useful to have information about existing orders to control the amount of exposure; not used in this code, but could provide more granular control of the strategy...
    payload = {'ticker': ticker}
    resp = s.get (ORDER_PATH, params = payload)
    if resp.ok:
        orders = resp.json()
        buy_orders = [item for item in orders if item["action"] == "BUY"]
        sell_orders = [item for item in orders if item["action"] == "SELL"]
        return buy_orders, sell_orders

def get_order_status(order_id): # this function finds the order status for a specific order, a complementary function to get_open_orders()
    resp = s.get (ORDER_PATH + '/' + str(order_id))
    if resp.ok:
        order = resp.json()
        return order['status']

def create_limit_order(tk, quant, price, action):
    return {'ticker': tk, 
            'type': 'LIMIT', 
            'quantity': quant, 
            'price': price, 
            'action': action}

def strat(ticker_symbol):
    tick, status = get_tick()
    
    while status == 'ACTIVE':
        try:
            best_bid_price, best_ask_price = get_bid_ask(ticker_symbol)
            best_spread = best_ask_price - best_bid_price
        except:
            break
        book = get_ticker_book_info(ticker_symbol)
        ind_pos = book['position']
        spread_limit = SPREAD_LIMIT[ticker_symbol]
        order_lst = []
        
        if best_spread >= spread_limit:
            if ind_pos < IND_MAX_LONG_EXPOSURE[ticker_symbol]: # "if statements are common triggers for launching orders - the order will be sent if the condition(s) are true; in this case we are identifying that we are entering a buy order ('action' = 'BUY') at the current best bid price (i.e. we are joining the bid) if we have not yet reached our maximum long exposure of 25,000; this condition is flawed/incomplete, and will cause errors... a key skill in coding is figuring out what breaks the strategy/code (i.e. there is no use in figuring out how the code works when everything goes right, the trick is finding the opposite... trial and error will be helpful, but frustrating, to find what can go wrong, which is the algo's risk - one of your jobs is to think of all the things that could go wrong, and prevent them)
                if best_spread <= price_incr:
                    price = best_bid_price
                elif ind_pos < WARNING_SHORT_LIMIT[ticker_symbol]:
                    price = round((best_bid_price + best_ask_price) / 2,2)
                elif ticker_symbol == 'RY' and best_spread < (price_incr*2):
                    price = best_bid_price
                else:
                    price = best_bid_price + price_incr
                resp = s.post(ORDER_PATH, params = create_limit_order(ticker_symbol, ORDER_LIMIT[ticker_symbol], price, 'BUY'))
                if resp.ok:
                    order_id = resp.json()['order_id']
                    order_lst.append(str(order_id))

                
            if ind_pos > IND_MAX_SHORT_EXPOSURE[ticker_symbol]:
                if best_spread <= price_incr:
                    price = best_ask_price
                elif ind_pos > WARNING_LONG_LIMIT[ticker_symbol]:
                    price = round((best_bid_price + best_ask_price) / 2,2)
                elif ticker_symbol == 'RY' and best_spread < (price_incr*3):
                    price = best_ask_price
                else:
                    price = best_ask_price - price_incr
                resp = s.post(ORDER_PATH, params = create_limit_order(ticker_symbol, ORDER_LIMIT[ticker_symbol], price, 'SELL'))
                if resp.ok:
                    order_id = resp.json()['order_id']
                    order_lst.append(str(order_id))

                    
            sleep(SLEEP_TIME[ticker_symbol]) # pauses the code to give the passive orders a chance to trade before being cancelled; this is NOT optimal...
            
            ids_to_cancel = ','.join(order_lst)
            cancel = s.post('http://localhost:9999/v1/commands/cancel', params = {'ids': ids_to_cancel}) # cancels any unfilled orders that were just placed in this for loop - prevents a proliferation of passive orders that can cause the position to exceed the limits; this is NOT optimal...


def multi_trader(threads, strat_func, tk, trader_num=trader_num):
    for i in range(trader_num[tk]):
        thread = threading.Thread(target=strat_func, args=[tk])
        thread.start()
        threads.append(thread)
        sleep(SLEEP_TIME[tk]/trader_num[tk])

def main(): # function that contains the decision-making portion of the algo, can be called by the final if statement (line 88) or invoking main() or hitting the "play" butting (F5)
     # this function call queries the case status and establishes whether the loop will start
    tick, status = get_tick()
    ticker_list = ['CNR','RY','AC']
    if status == 'ACTIVE': # this loop is the algo - the loop contains the set of instructions (including calls to the functions we define above) that execute our trading strategy; we want these instructions to be repeatedly executed over the duration of the case and use the "while" loop to implement this repetition - there are other types of loops that can be used, such as a "for" loop below; the loop is necessary to re-query the market to check on the current quotes which are used in the if conditions (the decision-making part of the algo)       
        biger_threads = []    
        threads = []
        for tk in ticker_list:
            thread = threading.Thread(target=multi_trader, args=[threads, strat, tk])
            thread.start()
            biger_threads.append(thread)

        for thread in threads:
            thread.join()
        
        for thread in biger_threads:
            thread.join()


if __name__ == '__main__': # convenience to make it easier to run the code
    t = 0
    while t == 0:
        tick, status = get_tick()
        if status == 'ACTIVE':
            main()

