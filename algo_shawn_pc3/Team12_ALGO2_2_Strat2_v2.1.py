import requests
from time import sleep 
import threading

s = requests.Session()
s.headers.update({'X-API-key': 'YI1W7QRM'}) # convenience, so we do not need to separately include the API Key in our messages to RIT as it is already included when we use "s"

## Note: from 1.5 to assign different sleep time to different stocks
# variables that are not changing while the case is running, and may appear in multiple spots - one change in the variable here applies to every instance, otherwise I would have to go through the code to change every instance; these are not inside a function which makes them "global" instead of "local" and they can be used by any function
MAX_LONG_EXPOSURE = 25000
MAX_SHORT_EXPOSURE = -25000
IND_MAX_LONG_EXPOSURE = {'CNR': 4000, 'RY': 15000, 'AC': 4000} 
IND_MAX_SHORT_EXPOSURE = {'CNR': -4000, 'RY': -15000, 'AC': -4000} 
WARNING_LONG_LIMIT = {'CNR': 3000, 'RY': 15000, 'AC': 2000} 
WARNING_SHORT_LIMIT = {'CNR': -3000, 'RY': -15000, 'AC': -2000} 
ORDER_LIMIT = {'CNR': 1000, 'RY': 5000, 'AC': 1000}
SPREAD_LIMIT = {'CNR': 0.03, 'RY': 0.02, 'AC': 0.03}
SLEEP_TIME = {'CNR': 0.1, 'RY': 0.2, 'AC': 0.1}
price_incr = 0.01
trader_num = {'CNR': 10, 'RY': 5, 'AC': 10}

price_incr = [0.01, 0]


CASE_PATH = 'http://localhost:9999/v1/case'
BOOK_PATH = 'http://localhost:9999/v1/securities/book'
ORDER_PATH = 'http://localhost:9999/v1/orders'
ORDER_ENDPOINT = 'http://localhost:9999/v1/orders'

def get_tick(): # this function queries the status of the case ("ACTIVE", "STOPPED", "PAUSED") which we will use in our "while" loop
    resp = s.get(CASE_PATH)
    if resp.ok:
        case = resp.json()
        return case['tick'], case['status'] # this code does not use the "tick" value, but may be useful if the code is modified

def get_bid_ask(ticker): 
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


def get_ticker_book_info(ticker):
    resp = s.get ('http://localhost:9999/v1/securities')
    if resp.ok:
        book = resp.json()
        ticker_lst = [i for i in book if i['ticker']==ticker]
        return ticker_lst[0]



def create_limit_order(tk, quant, price, action):
    return {'ticker': tk, 
            'type': 'LIMIT', 
            'quantity': quant, 
            'price': price, 
            'action': action}


def submit_limit_order(tk, quant, price, action):
    params =  {'ticker': tk, 'type': 'LIMIT', 'quantity': quant, 
               'price': price, 'action': action}
    
    resp = s.post(ORDER_ENDPOINT, params = params)
    return resp



def submit_sequence_orders(tk, best_bid, best_ask, quant, position, order_list, price_incr=price_incr):
    for incr in price_incr:
        if position < IND_MAX_LONG_EXPOSURE[tk]:
            resp = submit_limit_order(tk, quant, best_bid + incr, 'BUY')
            
            if resp.ok:
                order_id = resp.json()['order_id']
                order_list.append(str(order_id))
        
        if position > IND_MAX_SHORT_EXPOSURE[tk]:
            resp = submit_limit_order(tk, quant, best_ask - incr, 'SELL')
            
            if resp.ok:
                order_id = resp.json()['order_id']
                order_list.append(str(order_id))
        
    return order_list


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

            order_lst = submit_sequence_orders(ticker_symbol, best_bid_price, best_ask_price, 
                                                ORDER_LIMIT[ticker_symbol], ind_pos, order_lst)
            
                    
            sleep(SLEEP_TIME[ticker_symbol])
            
            ids_to_cancel = ','.join(order_lst)
            cancel = s.post('http://localhost:9999/v1/commands/cancel', params = {'ids': ids_to_cancel}) 


def multi_trader(threads, strat_func, tk, trader_num=trader_num):
    for i in range(trader_num[tk]):
        thread = threading.Thread(target=strat_func, args=[tk])
        thread.start()
        threads.append(thread)
        sleep(SLEEP_TIME[tk]/trader_num[tk])


def main(): 
    tick, status = get_tick()
    ticker_list = ['CNR', 'AC']
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


if __name__ == '__main__':
    while True:
        tick, status = get_tick()
        if status == 'ACTIVE':
            main()

