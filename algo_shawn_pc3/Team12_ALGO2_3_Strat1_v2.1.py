import requests
from time import sleep 
import threading

s = requests.Session()
s.headers.update({'X-API-key': '0BCIUU0S'}) # convenience, so we do not need to separately include the API Key in our messages to RIT as it is already included when we use "s"

MAX_LONG_EXPOSURE = 25000
MAX_SHORT_EXPOSURE = -25000
IND_MAX_LONG_EXPOSURE = {'CNR': 2500, 'RY': 20000, 'AC': 2500} 
IND_MAX_SHORT_EXPOSURE = {'CNR': -2500, 'RY': -20000, 'AC': -2500} 
WARNING_LONG_LIMIT = {'CNR': 1300, 'RY': 10000, 'AC': 1300} 
WARNING_SHORT_LIMIT = {'CNR': -1300, 'RY': -10000, 'AC': -1300} 
ORDER_LIMIT = {'CNR': 200, 'RY': 1500, 'AC': 200}
SPREAD_LIMIT = {'CNR': 0.02, 'RY': 0.02, 'AC': 0.02}
SLEEP_TIME = {'CNR': 0.3, 'RY': 0.3, 'AC': 0.3}
trader_num = {'CNR': 3, 'RY': 3, 'AC': 3}

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



def submit_limit_order(tk, quant, price, action):
    params =  {'ticker': tk, 'type': 'LIMIT', 'quantity': quant, 
               'price': price, 'action': action}
    
    resp = s.post(ORDER_ENDPOINT, params = params)
    return resp



def submit_sequence_orders(tk, best_bid, best_ask, quant, position, order_list, price_incr=price_incr):
    for incr in price_incr:
        if position < WARNING_LONG_LIMIT[tk]:
            resp = submit_limit_order(tk, quant, best_bid + incr, 'BUY')
            
            if resp.ok:
                order_id = resp.json()['order_id']
                order_list.append(str(order_id))
        
        if position > WARNING_SHORT_LIMIT[tk]:
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
    ticker_list = ['CNR', 'RY', 'AC']
    if status == 'ACTIVE': 
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

