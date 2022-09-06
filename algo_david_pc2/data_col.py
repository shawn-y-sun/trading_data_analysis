# -*- coding: utf-8 -*-
"""
Created on Fri Apr  1 11:28:09 2022

@author: shawn
"""
import requests
from collections import Counter
import os
import datetime
from openpyxl import load_workbook
from time import sleep
import threading
import ast

# CHANGE before run
algo_file = r'Team4_ALGO2_2_Strat1_v5'
trader = 'David-PC1'
file_path = "algo2_data_david_pc1.xlsx"
s = requests.Session()
s.headers.update({'X-API-key': 'TA0ZGM64'})

ticker_lst = ['CNR', 'RY', 'AC']


def get_file_name():
    return os.path.basename(__file__)[:-3]	


def get_timestamp():
    time = datetime.datetime.now()
    return f'{time}'[:16]


def get_tick():
    resp = s.get('http://localhost:9999/v1/case')
    if resp.ok:
        case = resp.json()
        return case['tick'], case['status']


def get_pl():
    resp = s.get ('http://localhost:9999/v1/securities')
    if resp.ok:
        book = resp.json()
        pl_lst = [sec['realized'] for sec in book]
    
    return pl_lst


def get_vol(read_tick=299):
    tick, status = get_tick()
    while tick < read_tick:
        tick, status = get_tick()
        continue
    
    transac_lst = s.get ('http://localhost:9999/v1/orders?status=TRANSACTED').json()
    
    vol_lst = []
    
    for tk in ticker_lst:
        tk_vol_lst = [order['quantity_filled'] for order in transac_lst if order['ticker'] == tk]
        vol_lst.append(sum(tk_vol_lst))
    
    return vol_lst


def get_ticker_traders_info(ticker, count_dict):
    payload = {'ticker': ticker}
    resp = s.get ('http://localhost:9999/v1/securities/book', params = payload)
    if resp.ok:
        book = resp.json()
        bid_side_book = book['bids']
        ask_side_book = book['asks']
        
        bid_traders = [order['trader_id'] for order in bid_side_book if order['trader_id'] != 'ANON']
        ask_traders = [order['trader_id'] for order in ask_side_book if order['trader_id'] != 'ANON']
        
        all_traders = bid_traders + ask_traders
        count_results = dict(Counter(all_traders))
        
        if len(count_dict[ticker]) == 0:
            count_dict[ticker] = count_results
        
        else:
            for key, val in count_results.items():
                if key in list(count_dict[ticker].keys()):
                    count_dict[ticker][key] += val
                else:
                    count_dict[ticker][key] = val
     


def get_traders_info(traders_info_dict, wait=0.5):
    
    tick, status = get_tick()
    while status == 'ACTIVE':
    
        for ticker in ticker_lst:
            get_ticker_traders_info(ticker, traders_info_dict)
            tick, status = get_tick()
            
            if status == 'ACTIVE':
                continue
            else:
                break
        
        sleep(wait)
        tick, status = get_tick()
    
    return None


def parse_traders_info(traders_info_dict):
    traders_input = []
    
    trader_ids = []
    active_traders = []
    orders_per_trader = []
    for tk in ticker_lst:
        ## Get active traders
        trader_ids += list(traders_info_dict[tk].keys())
        active_traders.append(len(traders_info_dict[tk]))
        
        ## Get orders per trader per ticker
        x= traders_info_dict[tk]
        orders_num = {k: v for k, v in sorted(x.items(), key=lambda item: item[1], reverse=True)}
        orders_per_trader.append(str(orders_num))
        
    
    traders_input.append(len(set(trader_ids)))
    traders_input += active_traders
    
    # Get total order num per trader
    total_orders_per_trader = {}
    for trader in list(set(trader_ids)):
        count = 0
        for i in range(3):
            orders_num_dict = ast.literal_eval(orders_per_trader[i])
            try:
                count += orders_num_dict[trader]
            except KeyError:
                continue
        total_orders_per_trader[trader] = count
    
    
    x = total_orders_per_trader
    total_orders_per_trader_sorted = {k: v for k, v in sorted(x.items(), key=lambda item: item[1], reverse=True)}
    traders_input.append(str(total_orders_per_trader_sorted))
    traders_input += orders_per_trader
        
    return traders_input
        
    
        
def collect_input():
    traders_info_dict = {ticker: {} for ticker in ticker_lst}
    thread = threading.Thread(target=get_traders_info, args=[traders_info_dict])
    thread.start()
    
    vol_lst = get_vol()
    
    tick, status = get_tick()
    while status == 'ACTIVE':
        tick, status = get_tick()
        continue
    
    input_lst = []
    input_lst.append(get_timestamp())
    if algo_file is None:
        input_lst.append(get_file_name())
    else:
        input_lst.append(algo_file)
    input_lst.append(trader)
    
    pl_lst = get_pl()
    input_lst.append(sum(pl_lst))
    input_lst += pl_lst
    
    input_lst.append(sum(vol_lst))
    input_lst += vol_lst
    
    thread.join()
    
    traders_input = parse_traders_info(traders_info_dict)
    input_lst += traders_input
    
    return input_lst


def write_data():
    input_lst = collect_input()
    #Load
    wb = load_workbook(file_path)
    ws = wb.active

    # Write
    ws.append(input_lst)

    # Close and Save
    wb.save(file_path)
    print(f'Data collected at {get_timestamp()} for {algo_file} by {trader}')


if __name__ == '__main__':
    while True:
        tick, status = get_tick()
        if status == 'ACTIVE':
            write_data()
            sleep(2)
            tick, status = get_tick()
                
    
    