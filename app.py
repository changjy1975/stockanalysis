import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 網頁設定 ---
st.set_page_config(page_title="進階股票分析系統", layout="wide")
st.title("📈 股票技術分析專業版 (MA, KD, MACD)")

# --- 側邊欄設定 ---
st.sidebar.header("查詢參數")
ticker = st.sidebar.text_input("輸入股票代碼", "2330.TW")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

# --- 數據抓取函數 ---
@st.cache_data
def load_data(symbol, start, end):
    data = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if data.empty: return data
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

try:
    df = load_data(ticker, start_date, end_date)

    if df.empty or len(df) < 30:
        st.error("數據不足，請嘗試更長的日期範圍或檢查代碼。")
    else:
        # --- 1. 計算技術指標 ---
        # MA 均線
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA60'] = ta.sma(df['Close'], length=60)
        
        # MACD (回傳值包含 MACD線, Signal線, Hist柱狀圖)
        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        df = pd.concat([df, macd], axis=1)
        
        # KD (回傳值包含 STOCHk_14_3_3, STOCHd_14_3_3)
        kd = ta.stoch(df['High'], df['Low'], df['Close'], k=9, d=3)
        df = pd.concat([df, kd], axis=1)
        
        # RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)

        # --- 2. 顯示上方資訊列 ---
        curr_p = float(df['Close'].iloc[-1])
        prev_p = float(df['Close'].iloc[-2])
        diff = curr_p - prev_p
        perc = (diff / prev_p) * 100
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新股價", f"{curr_p:.2f}", f"{diff:.2f} ({perc:.2f}%)")
        c2.metric("MA20", f"{df['MA20'].iloc[-1]:.2f}")
        c3.metric("KD (K值)", f"{df.iloc[-1, df.columns.get_loc('STOCHk_9_3_3')]:.2f}")
        c4.metric("MACD (柱狀)", f"{df.iloc[-1, df.columns.get_loc('MACDH_12_26_9')]:.2f}")

        # --- 3. 使用分頁顯示不同圖表 ---
        tab1, tab2, tab3 = st.tabs(["📊 K線與均線", "指標 1: MACD", "指標 2: KD & RSI"])

        with tab1:
            st.subheader("主圖表 (K-Line & MA)")
            fig_main = go.Figure()
            fig_main.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"))
            fig_main.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1.5), name='MA20'))
            fig_main.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='blue', width=1.5), name='MA60'))
            fig_main.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_dark")
            st.plotly_chart(fig_main, use_container_width=True)

        with tab2:
            st.subheader("MACD 指標")
            # MACD 包含 MACD_12_26_9 (線), MACDs_12_26_9 (信號線), MACDH_12_26_9 (柱狀圖)
            fig_macd = make_subplots(rows=1, cols=1)
            # 柱狀圖 (Histogram)
            colors = ['green' if x > 0 else 'red' for x in df['MACDH_12_26_9']]
            fig_macd.add_trace(go.Bar(x=df.index, y=df['MACDH_12_26_9'], name='Histogram', marker_color=colors))
            # MACD 與 Signal 線
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD_12_26_9'], line=dict(color='cyan', width=1.5), name='MACD線'))
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACDs_12_26_9'], line=dict(color='magenta', width=1.5), name='Signal線'))
            
            fig_macd.update_layout(height=400, template="plotly_dark", margin=dict(t=20, b=20))
            st.plotly_chart(fig_macd, use_container_width=True)
            st.info("💡 MACD 策略：當 MACD 線向上突破 Signal 線（金叉）時，通常視為買點。")

        with tab3:
            st.subheader("KD 指標 (隨機指標)")
            fig_kd = go.Figure()
            fig_kd.add_trace(go.Scatter(x=df.index, y=df['STOCHk_9_3_3'], line=dict(color='white', width=1.5), name='K值'))
            fig_kd.add_trace(go.Scatter(x=df.index, y=df['STOCHd_9_3_3'], line=dict(color='yellow', width=1.5), name='D值'))
            # 增加 20/80 超買超賣線
            fig_kd.add_hline(y=80, line_dash="dash", line_color="red")
            fig_kd.add_hline(y=20, line_dash="dash", line_color="green")
            fig_kd.update_layout(height=350, template="plotly_dark")
            st.plotly_chart(fig_kd, use_container_width=True)

            st.subheader("RSI 強弱指標")
            st.line_chart(df['RSI'])
            st.info("💡 KD 策略：K > D 且 K < 20 時，通常視為超賣區金叉買點；K > 80 為超買區。")

except Exception as e:
    st.error(f"分析失敗: {e}")
