import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="全方位股票分析系統", layout="wide")
st.title("📊 專業級全指標技術看板")

# --- 2. 側邊欄設定 ---
st.sidebar.header("查詢參數")
ticker = st.sidebar.text_input("輸入股票代碼", "2330.TW")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

# --- 3. 數據抓取函數 ---
@st.cache_data
def load_data(symbol, start, end):
    data = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if data.empty: return data
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

# --- 4. 主要執行邏輯 ---
try:
    df = load_data(ticker, start_date, end_date)

    if df.empty or len(df) < 40:
        st.error("數據不足，請增加日期範圍或檢查代碼是否正確。")
    else:
        # --- 計算技術指標 ---
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

        # --- 繪製多層子圖 ---
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, 
            row_heights=[0.5, 0.2, 0.2, 0.1]
        )

        # K線與均線
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='deepskyblue', width=1), name='MA60'), row=1, col=1)

        # MACD
        colors = ['red' if x < 0 else 'green' for x in df['MACD_H']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD柱狀', marker_color=colors), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='white', width=1), name='MACD線'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_S'], line=dict(color='yellow', width=1), name='訊號線'), row=2, col=1)

        # KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1.2), name='K值'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1.2), name='D值'), row=3, col=1)

        # RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1), name='RSI'), row=4, col=1)

        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=50, r=50, t=50, b=50))
        st.plotly_chart(fig, use_container_width=True)

        # --- 5. 策略建議引擎 ---
        st.divider()
        st.header("🤖 技術面操作建議 (未來三個月展望)")

        last_close = float(df['Close'].iloc[-1])
        ma20_now = float(df['MA20'].iloc[-1])
        ma60_now = float(df['MA60'].iloc[-1])
        k_now = float(df['K'].iloc[-1])
        d_now = float(df['D'].iloc[-1])
        rsi_now = float(df['RSI'].iloc[-1])

        # 簡單趨勢判斷邏輯
        if last_close > ma20_now > ma60_now:
            trend = "強勢多頭"
            trend_color = "green"
            action = "持股續抱 / 逢回佈局"
            detail = "股價位於均線之上且均線多頭排列。建議以 MA20 為守停損，未跌破前不輕易離場。"
        elif last_close < ma20_now < ma60_now:
            trend = "弱勢空頭"
            trend_color = "red"
            action = "觀望 / 減碼"
            detail = "目前處於下降通道。建議靜待股價站回 MA60 且均線走平後再進場。"
        else:
            trend = "震盪整理"
            trend_color = "orange"
            action = "區間操作"
            detail = "方向不明確，建議在 RSI < 30 時少量試單，RSI > 70 時減碼。"

        col_s1, col_s2 = st.columns([1, 3])
        with col_s1:
            st.markdown(f"### 建議行動：\n## :{trend_color}[{action}]")
        with col_s2:
            st.write(f"**當前趨勢評估：** {trend}")
            st.write(f"**分析細節：** {detail}")

        with st.expander("📌 未來三個月風險提示"):
            st.write(f"- **壓力區**：約在 {df['High'].tail(60).max():.2f}")
            st.write(f"- **支撐區**：約在 {df['Low'].tail(60).min():.2f}")
            st.write("- **提示**：技術指標具滯後性，請結合基本面與大盤走勢綜合判斷。")

        st.caption("⚠️ 免責聲明：本建議僅基於技術指標之邏輯運算，不代表未來必然走勢。投資有風險，操作前請謹慎評估。")

except Exception as e:
    st.error(f"發生錯誤: {e}")
    st.info("請檢查股票代碼是否正確（例如台股 2330.TW）。")
