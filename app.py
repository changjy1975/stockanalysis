import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 網頁設定 ---
st.set_page_config(page_title="簡易股票分析助手", layout="wide")
st.title("📈 股票技術分析 App")

# --- 側邊欄：使用者輸入 ---
st.sidebar.header("查詢設定")
ticker = st.sidebar.text_input("輸入股票代碼 (例如: AAPL, TSLA, 2330.TW)", "2330.TW")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

# --- 抓取數據 ---
@st.cache_data
def load_data(symbol, start, end):
    data = yf.download(symbol, start=start, end=end)
    return data

try:
    df = load_data(ticker, start_date, end_date)

    if df.empty:
        st.error("找不到該股票數據，請檢查代碼是否正確。")
    else:
        # --- 計算技術指標 (使用 pandas_ta) ---
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA60'] = ta.sma(df['Close'], length=60)
        df['RSI'] = ta.rsi(df['Close'], length=14)

       # --- 顯示基本資訊 ---
        stock_info = yf.Ticker(ticker).info
        st.subheader(f"{stock_info.get('longName', ticker)} - 概況")
        
        # 修正點：確保抓到的是數值而不是 Series
        # 使用 .values[-1] 或 float() 來確保取得單一數字
        try:
            current_price = float(df['Close'].iloc[-1])
            prev_price = float(df['Close'].iloc[-2])
            price_change = ((current_price / prev_price) - 1) * 100
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("現價", f"{current_price:.2f}")
            col2.metric("漲跌幅", f"{price_change:.2f}%")
            col3.metric("52週最高", stock_info.get('fiftyTwoWeekHigh', 'N/A'))
            col4.metric("市值 (B)", round(stock_info.get('marketCap', 0) / 1e9, 2))
        except Exception as e:
            st.warning(f"部分數據顯示異常: {e}")

        # --- 繪製 K 線圖 ---
        st.subheader("技術分析圖表")
        fig = go.Figure()

        # K 線圖
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'],
            name="K線"
        ))

        # 均線
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='MA20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='blue', width=1), name='MA60'))

        fig.update_layout(xaxis_rangeslider_visible=False, height=600, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

        # --- 顯示數據表格 ---
        st.subheader("歷史數據 (最近 10 筆)")
        st.dataframe(df.tail(10), use_container_width=True)

        # --- RSI 指標 ---
        st.subheader("RSI 強弱指標")
        st.line_chart(df['RSI'])

except Exception as e:
    st.error(f"發生錯誤: {e}")

st.sidebar.markdown("---")
st.sidebar.write("💡 提示: 台灣股票請加 `.TW` (如 `2330.TW`)")
st.sidebar.write("⚠️ 免責聲明: 本程式僅供參考，不構成投資建議。")
