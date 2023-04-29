# 3ema + stochastic rsi + atr
###########################################################################################
import MetaTrader5 as mt5
import numpy as np
import pandas as pd


###########################################################################################
# functions
def ema(data, period=20, column="close"):
    return data[column].ewm(span=period, adjust=False).mean()


def StochRSI(data, rsi_period=14, stoch_period=14, smoothk=3, smoothd=3):
    # Calculate RSI
    delta = data.diff().dropna()
    ups = delta * 0
    downs = ups.copy()
    ups[delta > 0] = delta[delta > 0]
    downs[delta < 0] = -delta[delta < 0]
    ups[ups.index[rsi_period - 1]] = np.mean(ups[:rsi_period])  # first value is sum of avg gains
    ups = ups.drop(ups.index[:(rsi_period - 1)])
    downs[downs.index[rsi_period - 1]] = np.mean(downs[:rsi_period])  # first value is sum of avg losses
    downs = downs.drop(downs.index[:(rsi_period - 1)])
    rs = ups.ewm(com=rsi_period - 1, min_periods=0, adjust=False, ignore_na=False).mean() / \
         downs.ewm(com=rsi_period - 1, min_periods=0, adjust=False, ignore_na=False).mean()
    rsi = 100 - 100 / (1 + rs)

    # Calculate StochRSI
    stochrsi = (rsi - rsi.rolling(stoch_period).min()) / (
            rsi.rolling(stoch_period).max() - rsi.rolling(stoch_period).min())
    stochrsi_K = stochrsi.rolling(smoothk).mean()
    stochrsi_D = stochrsi_K.rolling(smoothd).mean()

    return stochrsi, stochrsi_K, stochrsi_D


def trend(ema1, ema2, ema3):
    if ema1 > ema2 > ema3:
        return "bull"
    elif ema1 < ema2 < ema3:
        return "bear"
    else:
        return "none"


def k_d_crossover(k, d, shift_k):
    if k < d < shift_k:
        return 'cross down'
    elif k > d > shift_k:
        return "cross up"
    else:
        return "none"


###########################################################################################
# main body

mt5.initialize()
while True:
    ###########################################################################################
    # settings
    fx_symbol = "XAUUSD"
    timeframe = mt5.TIMEFRAME_M1
    lot = 0.01
    deviation = 20
    start = 1
    end = 150
    risk_reward_value = 2

    # stop loss and tp
    atr_length = 17
    atr_multi = 3.5

    # emas
    ema_length_1 = 3
    ema_length_2 = 8
    ema_length_3 = 14

    # stoch rsi
    rsi = 13
    stoch = 14
    k = 14
    d = 28

    orders = mt5.positions_total()

    ###########################################################################################
    candlestick_data = mt5.copy_rates_from_pos(fx_symbol, timeframe, start, end)  # number of candles
    df = pd.DataFrame(candlestick_data)[["time", "open", "high", "close", "low"]]
    df['time'] = pd.to_datetime(df['time'], unit='s')  # change the format of time
    df.index = pd.DatetimeIndex(df['time'])  # index time

    df['ema1'] = ema(df, ema_length_1, "close")
    df['ema2'] = ema(df, ema_length_2, "close")
    df['ema3'] = ema(df, ema_length_3, "close")

    df["trend"] = np.vectorize(trend)(df['ema1'], df['ema2'], df['ema3'])

    df["stochrsi"], df["stochrsi_K"], df['stochrsi_d'] = StochRSI(df['close'], rsi, stoch, k, d)

    df['shift_k'] = df['stochrsi_K'].shift(1)
    df.dropna(inplace=True)

    df["crossover"] = np.vectorize(k_d_crossover)(df["stochrsi_K"], df["stochrsi_d"], df["shift_k"])
    df.dropna(inplace=True)
    ###########################################################################################
    df['range'] = df['high'] - df['low']
    df['atr_value'] = df['range'].rolling(atr_length).mean()
    df.dropna(inplace=True)

    ###########################################################################################
    df['buystoploss'] = df['close'] - (df['atr_value'] * atr_multi)
    df['buytakeprofit'] = df['close'] + (df['atr_value'] * atr_multi * risk_reward_value)
    df['sellstoploss'] = df['close'] + (df['atr_value'] * atr_multi)
    df['selltakeprofit'] = df['close'] - (df['atr_value'] * atr_multi * risk_reward_value)

    ###########################################################################################

    if df['trend'].iloc[-1] == 'bull' and df['crossover'].iloc[-1] == 'cross up' and not mt5.positions_total():
        print('buy')
        if orders == 0:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": fx_symbol,
                "volume": lot,
                "type": mt5.ORDER_TYPE_BUY,
                "price": mt5.symbol_info_tick(fx_symbol).ask,
                "sl": df['buystoploss'].iloc[-1],
                "tp": df['buytakeprofit'].iloc[-1],
                "deviation": deviation,
                "magic": 234000,
                "comment": "python script open",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)

    if df['trend'].iloc[-1] == 'bear' and df['crossover'].iloc[-1] == 'cross down' and not mt5.positions_total():
        print('sell')
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": fx_symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_SELL,
            "price": mt5.symbol_info_tick(fx_symbol).ask,
            "sl": df['sellstoploss'].iloc[-1],
            "tp": df['selltakeprofit'].iloc[-1],
            "deviation": deviation,
            "magic": 234000,
            "comment": "python script open",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)

    else:
        print(orders)

    print(df.iloc[-1])
