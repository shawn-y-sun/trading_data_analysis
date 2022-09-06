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

algo_file = r'Team12_ALGO2_1_Strat2_1.7_op'
trader = 'Shawn-PC2'
file_path = "algo2_data_shawn_pc2.xlsx"

s = requests.Session()
s.headers.update({'X-API-key': '0BCIUU0S'})

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


def get_ticker_traders_info(ticker, count_dict={}):
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
        
        if len(count_dict) == 0:
            count_dict = count_results
        
        else:
            for key, val in count_results.items():
                if key not in list(count_dict.keys()):
                    count_dict[key] += val
                else:
                    count_dict[key] = val
     


def get_traders_info(wait=2):
    traders_info_dict = {ticker: {} for ticker in ticker_lst}
    
    tick, status = get_tick()
    while status == 'ACTIVE':
    
        for ticker in ticker_lst:
            get_ticker_traders_info(ticker, traders_info_dict[ticker])
            tick, status = get_tick()
            
            if status == 'ACTIVE':
                continue
            else:
                break
        
        sleep(wait)
        tick, status = get_tick()
    print(traders_info_dict)
    return traders_info_dict


def parse_traders_info():
    traders_info = get_traders_info()
    pass
    
    

def collect_input():
    thread = threading.Thread(target=get_traders_info)
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
                
    
    