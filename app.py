import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="專業股票分析系統", layout="wide")
st.title("📈 股票技術分析專業版")

st.sidebar.header("查詢參數")
ticker = st.sidebar.text_input("輸入股票代碼", "2330.TW")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

@st.cache_data
def load_data(symbol, start, end):
    data = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if data.empty: return data
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

try:
    df = load_data(ticker, start_date, end_date)

    if df.empty or len(df) < 35:
        st.error("數據不足，請嘗試更長的日期範圍（建議至少 3 個月以上）。")
    else:
        # --- 指標計算 (使用 iloc 確保抓取成功) ---
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA60'] = ta.sma(df['Close'], length=60)
        
        macd_df = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        df['MACD_Line'] = macd_df.iloc[:, 0]
        df['MACD_Hist'] = macd_df.iloc[:, 1]
        df['MACD_Signal'] = macd_df.iloc[:, 2]
        
        kd_df = ta.stoch(df['High'], df['Low'], df['Close'], k=9, d=3)
        df['K_Value'] = kd_df.iloc[:, 0]
        df['D_Value'] = kd_df.iloc[:, 1]
        
        df['RSI'] = ta.rsi(df['Close'], length=14)

        # --- 頂部摘要 ---
        curr_p = float(df['Close'].iloc[-1])
        prev_p = float(df['Close'].iloc[-2])
        diff = curr_p - prev_p
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新股價", f"{curr_p:.2f}", f"{diff:.2f}")
        c2.metric("MA20", f"{df['MA20'].iloc[-1]:.2f}")
        c3.metric("K 值", f"{df['K_Value'].iloc[-1]:.2f}")
        c4.metric("MACD 柱狀", f"{df['MACD_Hist'].iloc[-1]:.2f}")

        # --- 分頁圖表 ---
        tab1, tab2, tab3 = st.tabs(["📊 K線與均線", "指標 1: MACD", "指標 2: KD & RSI"])

        with tab1:
            fig_main = go.Figure()
            fig_main.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"))
            fig_main.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1.5), name='MA20'))
            fig_main.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='blue', width=1.5), name='MA60'))
            fig_main.update_layout(xaxis_rangeslider_visible=False, height=550, template="plotly_dark")
            st.plotly_chart(fig_main, use_container_width=True)

        with tab2:
            st.subheader("MACD (12, 26, 9)")
            fig_macd = go.Figure()
            colors = ['#26A69A' if x > 0 else '#EF5350' for x in df['MACD_Hist']]
            fig_macd.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name='柱狀圖', marker_color=colors))
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD_Line'], line=dict(color='white', width=1.5), name='MACD快線'))
            fig_macd.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='yellow', width=1.2), name='Signal慢線'))
            fig_macd.update_layout(height=400, template="plotly_dark")
            st.plotly_chart(fig_macd, use_container_width=True)

        with tab3:
            st.subheader("KD 指標")
            fig_kd = go.Figure()
            fig_kd.add_trace(go.Scatter(x=df.index, y=df['K_Value'], line=dict(color='cyan', width=1.5), name='K值'))
            fig_kd.add_trace(go.Scatter(x=df.index, y=df['D_Value'], line=dict(color='orange', width=1.5), name='D值'))
            fig_kd.add_hline(y=80, line_dash="dash", line_color="red")
            fig_kd.add_hline(y=20, line_dash="dash", line_color="green")
            fig_kd.update_layout(height=300, template="plotly_dark")
            st.plotly_chart(fig_kd, use_container_width=True)

            st.subheader("RSI 強弱指標")
            st.line_chart(df['RSI'])

except Exception as e:
    st.error(f"發生錯誤: {e}")
    st.info("請檢查股票代碼是否正確（如台股 2330.TW）。若剛開盤數據不足也可能出錯。")
