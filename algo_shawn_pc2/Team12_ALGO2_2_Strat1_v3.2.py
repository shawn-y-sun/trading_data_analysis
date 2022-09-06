import requests
from time import sleep
import threading

s = requests.Session()
s.headers.update({'X-API-key': '0BCIUU0S'})

MAX_LONG_EXPOSURE = 25000
MAX_SHORT_EXPOSURE = -25000
ORDER_LIMIT = 5000

ticker_list = ['RY']
spread_gap = 0.02
speed_bump = 0.3
trader_num = 10
price_incr = [0.01, 0.01, 0.01, 0, 0, 0, -0.01, -0.01, -0.01]

## Endpoint
ORDER_ENDPOINT = 'http://localhost:9999/v1/orders'

def get_tick():
    resp = s.get('http://localhost:9999/v1/case')
    if resp.ok:
        case = resp.json()
        return case['tick'], case['status']


def get_bid_ask(ticker):
    payload = {'ticker': ticker}
    resp = s.get ('http://localhost:9999/v1/securities/book', params = payload)
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
        if position < MAX_LONG_EXPOSURE:
            resp = submit_limit_order(tk, quant, best_bid + incr, 'BUY')
            
            if resp.ok:
                order_id = resp.json()['order_id']
                order_list.append(str(order_id))
        
        if position > MAX_SHORT_EXPOSURE:
            resp = submit_limit_order(tk, quant, best_ask - incr, 'SELL')
            
            if resp.ok:
                order_id = resp.json()['order_id']
                order_list.append(str(order_id))
        
    return order_list



def strat(tk):
    tick, status = get_tick()
    
    while status == 'ACTIVE':
        
        book = get_ticker_book_info(tk)
        position = book['position']
        
        
        try:
            best_bid_price, best_ask_price = get_bid_ask(tk)
            best_spread = best_ask_price - best_bid_price
        except:
            break
        
        
        if best_spread > spread_gap:
            order_list = []
        
            order_list = submit_sequence_orders(tk, best_bid_price, best_ask_price, 
                                                ORDER_LIMIT, position, order_list)
        

            sleep(speed_bump)
            ids_to_cancel = ','.join(order_list)
            s.post('http://localhost:9999/v1/commands/cancel', params = {'ids': ids_to_cancel})
            
        tick, status = get_tick()

def multi_trader(tk):
    threads = []
    for _ in range(trader_num):
        thread = threading.Thread(target=strat, args=[tk])
        thread.start()
        threads.append(thread)
        sleep(speed_bump / trader_num)
    
    for thread in threads:
        thread.join()


def main():
    
    for tk in ticker_list:
        multi_trader(tk)
    
    
if __name__ == '__main__':
    while True:
        tick, status = get_tick()
        if status == 'ACTIVE':
            main()