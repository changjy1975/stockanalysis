import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="量化交易看板 PRO (精確訊號修正版)", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .price-box { border: 1px solid #4B5563; padding: 15px; border-radius: 10px; background-color: #111827; text-align: center; height: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心數據處理 ---
@st.cache_data(ttl=3600)
def load_and_process_data(symbol, start, end):
    try:
        start_buffer = pd.to_datetime(start) - timedelta(days=150)
        df = yf.download(symbol, start=start_buffer, end=end, auto_adjust=True)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # 指標計算
        df.ta.ema(length=10, append=True)
        df.ta.ema(length=20, append=True)
        df.ta.stoch(append=True)
        df.ta.rsi(length=14, append=True)
        
        # 動態映射 (確保欄位正確)
        cols = df.columns
        mapping = {
            'EMA10': [c for c in cols if 'EMA_10' in c],
            'EMA20': [c for c in cols if 'EMA_20' in c],
            'K':     [c for c in cols if 'STOCHk' in c],
            'D':     [c for c in cols if 'STOCHd' in c],
            'RSI':   [c for c in cols if 'RSI' in c]
        }
        df.rename(columns={v[0]: k for k, v in mapping.items() if v}, inplace=True)
        
        # --- 修正後的買賣訊號邏輯 (事件觸發型) ---
        
        # 買進：KD 金叉(且K<30) 且 站在月線上
        df['Buy_Signal'] = (df['K'] > df['D']) & (df['K'].shift(1) <= df['D'].shift(1)) & \
                           (df['K'] < 30) & (df['Close'] > df['EMA20'])
        
        # 賣出：EMA10 跌破 EMA20 (瞬間) 或 RSI 衝破 90 (瞬間)
        death_cross = (df['EMA10'] < df['EMA20']) & (df['EMA10'].shift(1) >= df['EMA20'].shift(1))
        rsi_overheat = (df['RSI'] > 90) & (df['RSI'].shift(1) <= 90)
        
        df['Sell_Signal'] = death_cross | rsi_overheat
        
        return df[df.index >= pd.to_datetime(start)].dropna()
    except Exception as e:
        return None

# --- 3. 介面設定 ---
st.sidebar.header("📊 投資參數")
ticker_input = st.sidebar.text_input("股票代碼", "2330.TW").upper()
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))

df = load_and_process_data(ticker_input, start_date, datetime.now())

if df is not None:
    curr = df.iloc[-1]
    st.title(f"📈 {ticker_input} 技術指標看板 (訊號修正版)")
    
    # 摘要卡片
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("目前股價", f"{curr['Close']:.2f}")
    m2.metric("RSI(14)", f"{curr['RSI']:.1f}")
    m3.metric("EMA10", f"{curr['EMA10']:.2f}")
    m4.metric("EMA20 (月線)", f"{curr['EMA20']:.2f}")

    # --- 4. 繪製圖表 ---
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.15, 0.2])
    
    # K線與均線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='#00ff88', width=2), name="EMA10"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#ffaa00', width=2), name="EMA20"), row=1, col=1)

    # 標註買進訊號 (綠色向上三角形)
    buy_pts = df[df['Buy_Signal']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low'] * 0.97, mode='markers', name='買入訊號',
                             marker=dict(symbol='triangle-up', size=15, color='lime', line=dict(width=1, color='white'))), row=1, col=1)

    # 標註賣出訊號 (紅色向下三角形)
    sell_pts = df[df['Sell_Signal']]
    fig.add_trace(go.Scatter(x=sell_pts.index, y=sell_pts['High'] * 1.03, mode='markers', name='賣出訊號',
                             marker=dict(symbol='triangle-down', size=15, color='red', line=dict(width=1, color='white'))), row=1, col=1)

    # 成交量
    vol_colors = ['red' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'green' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name="成交量", opacity=0.5), row=2, col=1)

    # KD
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan'), name='K'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta'), name='D'), row=3, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold'), name='RSI'), row=4, col=1)
    fig.add_hline(y=90, line_dash="dash", line_color="red", row=4, col=1, annotation_text="90 (獲利了結)")
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=4, col=1)

    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=50, r=50, t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)

    # 底部說明
    st.info("💡 **賣出訊號顯示逻辑已優化**：現在僅在 **EMA10 跌破 EMA20 的當下** 或 **RSI 首次衝破 90** 時標註紅色三角形。")

else:
    st.error("無法取得數據，請檢查代碼或日期範圍。")
