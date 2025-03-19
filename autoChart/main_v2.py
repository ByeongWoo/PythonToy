import pyupbit
import time
import pandas as pd
import json
from dotenv import load_dotenv  # pip install python-dotenv
import os
import requests
import multiprocessing
import matplotlib.pyplot as plt
from numpy import ta


# 보유 자산 조회
def get_balances():
    balances = upbit.get_balances()
    tickers = []
    for balance in balances:
        coin = balance['currency']
        if coin != 'KRW' and float(balance['balance']) > 0:  # KRW 제외, 보유량이 0 이상인 코인만 필터링
            tickers.append(f"KRW-{coin}")
    return tickers


def clear_console():
    if os.name == 'nt':  # Windows
        os.system('cls')
    else:  # MacOS / Linux
        os.system('clear')


# 일정 라인 수 이상이면 콘솔을 새로 고침
def print_limited_output():
    max_lines = 20  # 출력할 최대 라인 수
    line_count = 0
    while True:
        if line_count >= max_lines:
            clear_console()  # 일정 라인 수 이상이면 콘솔을 지움
            line_count = 0  # 라인 카운트 초기화
        print(f"Output line {line_count + 1}")
        line_count += 1
        time.sleep(0.5)


def buy(ticker, money):
    cur_my_balance = upbit.get_balance("KRW")  # 원화 잔고 조회
    if cur_my_balance < money:  # 매수 금액이 잔고보다 크면 매수 불가
        print(f"잔고 부족: 현재 잔고 {cur_my_balance}원, 매수 시도 금액 {money}원")
        return
    time.sleep(0.1)
    if money < 5000:  # 최소 주문 금액 확인
        print(f"매수 실패: 최소 주문 금액(5000원) 미만 {money}원")
        return
    time.sleep(0.1)
    b = upbit.buy_market_order(ticker, money)
    try:
        if b.get('error'):  # 'error' 키가 있을 경우 예외 처리
            b = upbit.buy_market_order(ticker, 10000)  # 1만 원으로 재시도
            msg = "error " + str(ticker) + " " + str(10000) + "원 매수 시도\n" + json.dumps(b, ensure_ascii=False)
    except:
        msg = str(ticker) + " " + str(money) + "원 매수 완료\n" + json.dumps(b, ensure_ascii=False)
    print(msg)


def sell(ticker):
    time.sleep(0.1)
    balance = upbit.get_balance(ticker)  # 보유 수량 조회
    if balance == 0 or balance is None:  # 보유량이 없으면 매도 불가
        print(f"매도 실패: {ticker} 보유량 없음")
        return

    current_price = pyupbit.get_current_price(ticker)
    sell_volume = round(current_price * balance, 0)
    ror = round((current_price / upbit.get_avg_buy_price(ticker) - 1) * 100, 2)
    s = upbit.sell_market_order(ticker, balance)
    msg = f"{ticker} 매도 완료 {sell_volume}원\n수익률: {ror}%"
    print(msg)
    print(s)


def get_rsi(target_ticker, period=14):
    df = pyupbit.get_ohlcv(target_ticker, 'minute10')
    # 전일 대비 변동 평균
    df['change'] = df['close'].diff()

    # 상승한 가격과 하락한 가격
    df['up'] = df['change'].apply(lambda x: x if x > 0 else 0)
    df['down'] = df['change'].apply(lambda x: -x if x < 0 else 0)

    # 상승 평균과 하락 평균
    df['avg_up'] = df['up'].ewm(alpha=1 / period).mean()
    df['avg_down'] = df['down'].ewm(alpha=1 / period).mean()

    # 상대강도지수(RSI) 계산
    df['rs'] = df['avg_up'] / df['avg_down']
    df['rsi'] = 100 - (100 / (1 + df['rs']))
    rsi = df['rsi']

    return rsi


def get_transaction_amount(date, num):
    tickers = pyupbit.get_tickers("KRW")  # KRW를 통해 거래되는 코인만 불러오기
    dic_ticker = {}
    for ticker in tickers:
        try:
            df = pyupbit.get_ohlcv(ticker, date)  # date 기간의 거래대금을 구해준다
            volume_money = df['close'].iloc[-1] * df['volume'].iloc[-1]
            dic_ticker[ticker] = volume_money
        except Exception as e:
            pass

    # 거래대금 큰 순으로 ticker를 정렬
    sorted_ticker = sorted(dic_ticker.items(), key=lambda x: x[1], reverse=True)
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


def search_rsi(setting_rsi):
    try:
        top10_tickers = get_transaction_amount("day", 10)

        print(f"tickers : {top10_tickers}")
        for symbol in top10_tickers:
            url = "https://api.upbit.com/v1/candles/minutes/10"
            querystring = {"market": symbol, "count": "200"}
            response = requests.request("GET", url, params=querystring)
            data = response.json()

            # 데이터가 없거나 예기치 않은 형태일 경우 예외 처리
            if not data or isinstance(data, dict):
                continue  # 다음 심볼로 넘어가기

            df = pd.DataFrame(data)
            df = df.reindex(index=df.index[::-1]).reset_index()
            df['close'] = df["trade_price"]

            def rsi(ohlc: pd.DataFrame, period: int = 14):
                delta = ohlc["close"].diff()
                up, down = delta.copy(), delta.copy()
                up[up < 0] = 0
                down[down > 0] = 0
                _gain = up.ewm(alpha=1 / period).mean()
                _loss = down.abs().ewm(alpha=1 / period).mean()
                RS = _gain / _loss
                return pd.Series(100 - (100 / (1 + RS)), name="RSI")

            # RSI 값 계산
            rsi_value = rsi(df, 14).iloc[-1]

            # RSI 값이 NaN이면 건너뜁니다.
            if pd.isna(rsi_value):
                print(f"Error: Invalid RSI value for {symbol}")
                continue  # 다음 심볼로 넘어가기

            if rsi_value < setting_rsi:
                os.system('cls')
                print(f"!!과매도 현상 발견!!\n" + symbol)
                print(f"매수 시점 rsi : {rsi_value}")
                return symbol

            time.sleep(1)

    except Exception as e:
        print(f"Error in search_rsi: {e}")
        time.sleep(2)

    return None  # <-- 추가


def search_my_rsi(setting_rsi):
    try:
        top10_tickers = get_balances()

        print(f"tickers : {top10_tickers}")
        for symbol in top10_tickers:
            url = "https://api.upbit.com/v1/candles/minutes/10"
            querystring = {"market": symbol, "count": "200"}
            response = requests.request("GET", url, params=querystring)
            data = response.json()

            # 데이터가 없거나 예기치 않은 형태일 경우 예외 처리
            if not data or isinstance(data, dict):
                continue  # 다음 심볼로 넘어가기

            df = pd.DataFrame(data)
            df = df.reindex(index=df.index[::-1]).reset_index()
            df['close'] = df["trade_price"]

            def rsi(ohlc: pd.DataFrame, period: int = 14):
                delta = ohlc["close"].diff()
                up, down = delta.copy(), delta.copy()
                up[up < 0] = 0
                down[down > 0] = 0
                _gain = up.ewm(alpha=1 / period).mean()
                _loss = down.abs().ewm(alpha=1 / period).mean()
                RS = _gain / _loss
                return pd.Series(100 - (100 / (1 + RS)), name="RSI")

            # RSI 값 계산
            rsi_value = rsi(df, 14).iloc[-1]

            # RSI 값이 NaN이면 건너뜁니다.
            if pd.isna(rsi_value):
                print(f"Error: Invalid RSI value for {symbol}")
                continue  # 다음 심볼로 넘어가기

            if rsi_value < setting_rsi:
                os.system('cls')
                print(f"!!과매도 현상 발견!!\n" + symbol)
                print(f"매수 시점 rsi : {rsi_value}")
                return symbol

            time.sleep(1)

    except Exception as e:
        print(f"Error in search_rsi: {e}")
        time.sleep(2)

    return None  # <-- 추가


# 실제 트레이드 위치
def auto_trade(idx):
    while True:
        try:
            target_rsi = 25
            sell_rsi = 60
            while True:
                if idx < 3:
                    target_ticker = search_rsi(target_rsi)
                else:
                    target_ticker = search_my_rsi(target_rsi)

                time.sleep(1)
                if target_ticker:
                    buy(target_ticker, trade_money)
                    bought_rsi = get_rsi(target_ticker, 14).iloc[-1]
                    tf = True
                    break
                else:
                    print(f"계속 탐색중입니다. Target RSI : {target_rsi}")
                    target_rsi += 1
            first_price = pyupbit.get_current_price(target_ticker)
            print(f"first price : {first_price}")
            cnt = 1
            bp = False
            while tf:
                coin_bought = upbit.get_balance(target_ticker)
                total_balance = coin_bought * pyupbit.get_current_price(target_ticker)
                rsi_value = get_rsi(target_ticker, 14).iloc[-1]
                print(f"타겟 : {target_ticker} 잔고 : {total_balance} 매도 rsi : {rsi_value} ")
                if total_balance > 1000000:
                    print("매도 스킵")
                    break
                if coin_bought < 1:
                    print('already sold')
                    os.system('cls')
                    break
                if total_balance < trade_money * cnt * 0.95:
                    bp = True
                    sell(target_ticker)
                    break
                if rsi_value > 60:
                    time.sleep(10)
                    rsi_value = get_rsi(target_ticker, 14).iloc[-1]
                    if rsi_value < sell_rsi:
                        sell(target_ticker)
                        print(f'sell volume:{total_balance}')
                        os.system('cls')
                        break
                    else:
                        sell_rsi = max(rsi_value, sell_rsi)
                        print(f'current rsi : {rsi_value}, waiting...')
                elif rsi_value < min(30, bought_rsi - 2) and cnt <= 3:
                    bought_rsi -= 2
                    buy(target_ticker, trade_money)
                    print('buy more')
                    cnt += 1
                    time.sleep(10)
                else:
                    print("거래 조건 미충족")
                    os.system('cls')
                    time.sleep(10)
            if bp:
                break
        except:
            time.sleep(1)


load_dotenv()
access = os.environ["access"]  # access 키
secret = os.environ["secret"]  # secret 키
upbit = pyupbit.Upbit(access, secret)

my_balance = upbit.get_balance("KRW")
trade_money = max(5000, my_balance * 0.1)  # 잔고의 10% 또는 최소 5000원

print(f"현재 잔고: {my_balance}원")
print(f"설정된 매수 금액: {trade_money}원")

if __name__ == "__main__":
    print("TRADE START")
    procs = []
    for i in range(4):
        p = multiprocessing.Process(target=auto_trade, args=(i, ))
        print(f'start trading: {i} multiprocess')
        p.start()
        procs.append(p)
        time.sleep(30)

    for p in procs:
        p.join()
    print("TRADE END")
