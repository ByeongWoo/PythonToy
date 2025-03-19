import pyupbit
import time
from datetime import datetime
from pytz import timezone
import pandas as pd
import json
from dotenv import load_dotenv # pip install python-dotenv
import os
import requests

load_dotenv()
access = os.environ["access"]  #access 키
secret = os.environ["secret"]  #secret 키
upbit = pyupbit.Upbit(access, secret)

def buy(ticker, money):
    time.sleep(0.1)
    b = upbit.buy_market_order(ticker, money)
    try:
        if b['error']:
            b = upbit.buy_market_order(ticker, 100000)
            msg = "error " + str(ticker)+" "+str(100000)+"원 매수시도"+"\n"+json.dumps(b, ensure_ascii = False)
    except:
        msg = str(ticker)+" "+str(money)+"원 매수완료"+"\n"+json.dumps(b, ensure_ascii = False)
    print(msg)
    # send_line(msg)

def sell(ticker):
    time.sleep(0.1)
    balance = upbit.get_balance(ticker)
    current_price = pyupbit.get_current_price(ticker)
    sell_volume = round(current_price*balance,0)
    ror = round((current_price/upbit.get_avg_buy_price(ticker)-1)*100,2)
    msg = str(ticker)+"매도 완료"+str(sell_volume) + '\n' + "수익률 :" +str(ror) +"%"
    s = upbit.sell_market_order(ticker, balance)
    print(msg)

def get_rsi(target_ticker, period=14):

    df = pyupbit.get_ohlcv(target_ticker, 'minute10')
    # 전일 대비 변동 평균
    df['change'] = df['close'].diff()

    # 상승한 가격과 하락한 가격
    df['up'] = df['change'].apply(lambda x: x if x > 0 else 0)
    df['down'] = df['change'].apply(lambda x: -x if x < 0 else 0)

    # 상승 평균과 하락 평균
    df['avg_up'] = df['up'].ewm(alpha=1/period).mean()
    df['avg_down'] = df['down'].ewm(alpha=1/period).mean()

    # 상대강도지수(RSI) 계산
    df['rs'] = df['avg_up'] / df['avg_down']
    df['rsi'] = 100 - (100 / (1 + df['rs']))
    rsi = df['rsi']

    return rsi

# def send_line(msg):
#     headers = {'Authorization':'Bearer '+token}
#     message = {
#         "message" : msg
#     }
#     requests.post(api_url, headers= headers , data = message)

def get_transaction_amount(date, num):
    tickers = pyupbit.get_tickers("KRW")	# KRW를 통해 거래되는 코인만 불러오기
    dic_ticker = {}
    for ticker in tickers:
        
        try :
            df = pyupbit.get_ohlcv(ticker, date)	# date 기간의 거래대금을 구해준다
            volume_money = df['close'].iloc[-1] * df['volume'].iloc[-1] 
            dic_ticker[ticker] = volume_money
        except Exception as e:
            pass
     
    # 거래대금 큰 순으로 ticker를 정렬
    sorted_ticker = sorted(dic_ticker.items(), key= lambda x : x[1], reverse= True)
    coin_list = []
    count = 0
    for coin in sorted_ticker:
        count += 1
        # 거래대금이 높은 num 개의 코인만 구한다
        if count <= num:
            coin_list.append(coin[0])
        else:
            break
    return coin_list

def searchRSI(settingRSI):
    try :
        tickers = pyupbit.get_tickers(fiat="KRW")
        for symbol in tickers : 
            url = "https://api.upbit.com/v1/candles/minutes/10" #"https://api.upbit.com/v1/candles/days"
            querystring = {"market":symbol,"count":"200"}
            response = requests.request("GET", url, params=querystring)
            data = response.json()
            df = pd.DataFrame(data)
            df=df.reindex(index=df.index[::-1]).reset_index()
            df['close']=df["trade_price"]
            def rsi(ohlc: pd.DataFrame, period: int = 14):
                delta = ohlc["close"].diff()
                up, down = delta.copy(), delta.copy()
                up[up < 0] = 0
                down[down > 0] = 0

                _gain = up.ewm(alpha=1/period).mean()
                _loss = down.abs().ewm(alpha=1/period).mean()

                RS = _gain / _loss
                return pd.Series(100 - (100 / (1 + RS)), name="RSI")
            rsi = rsi(df, 14).iloc[-1]
            if rsi < settingRSI :
                print(f"!!과매도 현상 발견!!\n"+symbol)
                print(f"매수 시점 rsi : {rsi}")
                return symbol
            time.sleep(1)

    except :
        time.sleep(2)

def auto_trade(money):
    trade_money = money
    print(trade_money)

    try:
        balances = upbit.get_balances()
        print("잔고 조회 성공:", balances)
    except Exception as e:
        print("잔고 조회 실패:", e)
    while True:
        try : 
            target_RSI = 25
            sell_rsi = 60
            while True:
                target_ticker = searchRSI(target_RSI)
                time.sleep(1)
                if target_ticker :
                    buy(target_ticker,trade_money)
                    bought_rsi = get_rsi(target_ticker,14).iloc[-1]
                    TF = True
                    break
                else :
                    print(f"계속 탐색중입니다. Target RSI : {target_RSI}")
                    target_RSI += 1
            firstprice =pyupbit.get_current_price(target_ticker)
            cnt = 1
            bp =False
            while TF == True :
                Coin_bought = upbit.get_balance(target_ticker)
                total_balance = Coin_bought * pyupbit.get_current_price(target_ticker) 
                rsi_value = get_rsi(target_ticker,14).iloc[-1]
                print(f"매도 rsi : {rsi_value} ")
                if total_balance > 100000:
                    print(f"매도 스킵합니다")
                    break
                if Coin_bought<1:
                    print(f'already sold')
                    break
                if total_balance < trade_money*cnt*0.95:
                    bp = True
                    sell(target_ticker)
                    break
                if rsi_value >60 :
                    time.sleep(300)
                    rsi_value = get_rsi(target_ticker,14).iloc[-1]
                    if rsi_value < sell_rsi :
                        sell(target_ticker)
                        print(f'sell volume:{total_balance}')
                        break
                    else:
                        sell_rsi = max(rsi_value,sell_rsi)
                        print(f'current rsi : {rsi_value}, waiting...')
                elif rsi_value < min(30,bought_rsi-2) and cnt <= 3: 
                    bought_rsi -= 2
                    buy(target_ticker,trade_money)
                    print('buy more')
                    cnt += 1
                    time.sleep(300)
                else: 
                    print(f"거래 조건 미충족")
                    time.sleep(100)
            if bp ==True: 
                break
        except :
            time.sleep(1)

if __name__ == '__main__':
    import multiprocessing

    procs = []
    for i in range(4):
        p = multiprocessing.Process(target=auto_trade, args=(5000+i, ))
        print(f'start trading: {i} multiprocess')
        p.start()
        procs.append(p)
        time.sleep(600)

    for p in procs:
        p.join()  # 프로세스가 모두 종료될 때까지 대기