import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 網頁設定 ---
st.set_page_config(page_title="專業股票分析助手", layout="wide")
st.title("📈 股票技術分析 App")

# --- 側邊欄：使用者輸入 ---
st.sidebar.header("查詢設定")
ticker = st.sidebar.text_input("輸入股票代碼 (例如: AAPL, 2330.TW)", "2330.TW")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

# --- 抓取數據與處理 ---
@st.cache_data
def load_data(symbol, start, end):
    # 修正點 1: 使用 auto_adjust=True 讓欄位結構更單純
    data = yf.download(symbol, start=start, end=end, auto_adjust=True)
    
    if data.empty:
        return data
        
    # 修正點 2: 處理 yfinance 新版本的多層索引 (MultiIndex) 問題
    # 這行程式碼會把 ('Close', '2330.TW') 簡化為 'Close'
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
        
    return data

try:
    df = load_data(ticker, start_date, end_date)

    if df.empty or len(df) < 10:
        st.error("數據不足或找不到該股票，請檢查代碼或日期範圍。")
    else:
        # --- 計算技術指標 ---
        # 確保數據是 Series 格式
        close_price = df['Close']
        df['MA20'] = ta.sma(close_price, length=20)
        df['MA60'] = ta.sma(close_price, length=60)
        df['RSI'] = ta.rsi(close_price, length=14)

        # --- 顯示基本資訊 ---
        # 取得最新一筆數據並轉為標量 (float)
        current_price = float(df['Close'].iloc[-1])
        prev_price = float(df['Close'].iloc[-2])
        price_diff = current_price - prev_price
        price_change = (price_diff / prev_price) * 100

        col1, col2, col3 = st.columns(3)
        col1.metric("目前股價", f"{current_price:.2f}", f"{price_diff:.2f} ({price_change:.2f}%)")
        col2.metric("最高價 (區間)", f"{df['High'].max():.2f}")
        col3.metric("最低價 (區間)", f"{df['Low'].min():.2f}")

        # --- 繪製 K 線圖 (Plotly) ---
        st.subheader("技術分析圖表")
        
        fig = go.Figure()

        # 加入 K 線
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name="K線"
        ))

        # 加入均線 (MA)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1.5), name='MA20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='blue', width=1.5), name='MA60'))

        # 圖表佈局設定
        fig.update_layout(
            xaxis_rangeslider_visible=False, # 隱藏下方的滑桿以增加清晰度
            height=600,
            template="plotly_dark",
            margin=dict(l=10, r=10, t=30, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        # 顯示圖表
        st.plotly_chart(fig, use_container_width=True)

        # --- 顯示 RSI ---
        st.subheader("RSI 強弱指標")
        st.line_chart(df['RSI'])

        # --- 顯示數據表格 ---
        with st.expander("查看原始歷史數據"):
            st.dataframe(df.sort_index(ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"發生錯誤: {e}")
    st.info("提示：如果是台股，請記得加上 .TW，例如 2330.TW")
