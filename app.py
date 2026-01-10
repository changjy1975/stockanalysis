import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 網頁設定 ---
st.set_page_config(page_title="專業級多時框股票看板", layout="wide")

# --- 側邊欄設定 ---
st.sidebar.header("查詢參數")
ticker = st.sidebar.text_input("輸入股票代碼", "2330.TW")

# --- 新增：時框選擇器 ---
interval_label = st.sidebar.selectbox(
    "選擇時框 (Interval)", 
    ["5分鐘", "15分鐘", "1小時", "日線", "周線"], 
    index=3 # 預設選「日線」
)

# 時框對應的 yfinance 參數與預設回推天數
interval_map = {
    "5分鐘": {"value": "5m", "days": 5},
    "15分鐘": {"value": "15m", "days": 10},
    "1小時": {"value": "1h", "days": 30},
    "日線": {"value": "1d", "days": 365},
    "周線": {"value": "1wk", "days": 1095} # 3年
}

selected_interval = interval_map[interval_label]["value"]
default_days = interval_map[interval_label]["days"]

# 自動調整開始日期，避免分鐘級數據抓取失敗
st.sidebar.write(f"提示：{interval_label}數據通常僅限近期")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=default_days))
end_date = st.sidebar.date_input("結束日期", datetime.now())

# --- 數據抓取 ---
@st.cache_data
def load_data(symbol, start, end, interval):
    # 下載數據，加入 interval 參數
    data = yf.download(symbol, start=start, end=end, interval=interval, auto_adjust=True)
    if data.empty: return data
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

try:
    df = load_data(ticker, start_date, end_date, selected_interval)

    if df.empty or len(df) < 10:
        st.error(f"無法取得數據。注意：{interval_label} 數據若超過 60 天前可能無法查詢，請嘗試縮短時間範圍。")
    else:
        # --- 1. 計算所有技術指標 ---
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA60'] = ta.sma(df['Close'], length=60)
        df['EMA10'] = ta.ema(df['Close'], length=10)
        df['EMA20'] = ta.ema(df['Close'], length=20)
        
        macd = ta.macd(df['Close'])
        df['MACD'] = macd.iloc[:, 0]
        df['MACD_H'] = macd.iloc[:, 1]
        df['MACD_S'] = macd.iloc[:, 2]
        
        kd = ta.stoch(df['High'], df['Low'], df['Close'])
        df['K'] = kd.iloc[:, 0]
        df['D'] = kd.iloc[:, 1]
        
        df['RSI'] = ta.rsi(df['Close'], length=14)

        # --- 2. 顯示標題與最新摘要 ---
        st.title(f"📈 {ticker} ({interval_label}) 技術分析")
        
        curr_p = float(df['Close'].iloc[-1])
        prev_p = float(df['Close'].iloc[-2])
        price_diff = curr_p - prev_p
        price_perc = (price_diff / prev_p) * 100
        
        with st.container():
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("當前價格", f"{curr_p:.2f}", f"{price_diff:+.2f} ({price_perc:+.2f}%)")
            c2.metric("RSI(14)", f"{df['RSI'].iloc[-1]:.1f}")
            c3.metric("K / D 值", f"{df['K'].iloc[-1]:.1f} / {df['D'].iloc[-1]:.1f}")
            c4.metric("EMA10", f"{df['EMA10'].iloc[-1]:.2f}")

        # --- 3. 繪製整合圖表 ---
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, 
            row_heights=[0.5, 0.2, 0.15, 0.15]
        )

        # K線 + 均線
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name="K線"
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='SMA20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='lightgreen', width=1, dash='dot'), name='EMA10'), row=1, col=1)

        # MACD
        colors = ['#26A69A' if x > 0 else '#EF5350' for x in df['MACD_H']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD柱狀', marker_color=colors), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='white', width=1), name='MACD線'), row=2, col=1)

        # KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1), name='K值'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1), name='D值'), row=3, col=1)

        # RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1), name='RSI'), row=4, col=1)

        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10))
        fig.update_xaxes(showticklabels=False, row=1, col=1)
        fig.update_xaxes(showticklabels=False, row=2, col=1)
        fig.update_xaxes(showticklabels=False, row=3, col=1)

        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"分析失敗: {e}")
