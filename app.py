import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 網頁設定 ---
st.set_page_config(page_title="專業級全指標技術看板", layout="wide")

# --- 側邊欄設定 ---
st.sidebar.header("查詢參數")
ticker = st.sidebar.text_input("輸入股票代碼", "2330.TW")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

# --- 數據抓取 ---
@st.cache_data
def load_data(symbol, start, end):
    data = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if data.empty: return data
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

try:
    df = load_data(ticker, start_date, end_date)

    if df.empty or len(df) < 40:
        st.title("📈 股票技術分析看板")
        st.error("數據不足，請在左側增加日期範圍或檢查代碼是否正確。")
    else:
        # --- 1. 計算所有技術指標 (邏輯必須先執行) ---
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA60'] = ta.sma(df['Close'], length=60)
        
        macd = ta.macd(df['Close'])
        df['MACD'] = macd.iloc[:, 0]
        df['MACD_H'] = macd.iloc[:, 1]
        df['MACD_S'] = macd.iloc[:, 2]
        
        kd = ta.stoch(df['High'], df['Low'], df['Close'])
        df['K'] = kd.iloc[:, 0]
        df['D'] = kd.iloc[:, 1]
        
        df['RSI'] = ta.rsi(df['Close'], length=14)

        # --- 2. 顯示標題與最新盤後摘要 (移到上方) ---
        st.title(f"📈 {ticker} 技術分析看板")
        
        # 獲取最新數據與變化
        curr_p = float(df['Close'].iloc[-1])
        prev_p = float(df['Close'].iloc[-2])
        price_diff = curr_p - prev_p
        price_perc = (price_diff / prev_p) * 100
        
        k_val = df['K'].iloc[-1]
        d_val = df['D'].iloc[-1]
        macdh = df['MACD_H'].iloc[-1]
        rsi_val = df['RSI'].iloc[-1]

        # 使用 Container 製作漂亮的摘要列
        with st.container():
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("最新股價", f"{curr_p:.2f}", f"{price_diff:+.2f} ({price_perc:+.2f}%)")
            c2.metric("RSI(
