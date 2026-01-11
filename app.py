import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="專業級技術看板 (含進出建議)", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; }
    .price-box { border: 1px solid #4B5563; padding: 15px; border-radius: 10px; background-color: #111827; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄參數 ---
st.sidebar.header("📊 查詢參數")
ticker_input = st.sidebar.text_input("輸入股票代碼 (例: 2330.TW, 6147.TWO)", "2330.TW").upper()
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

st.sidebar.info("""
**💡 代碼小提醒：**
- 上市股票：代碼 + .TW
- 上櫃股票：代碼 + .TWO
""")

# --- 3. 數據抓取與計算 ---
@st.cache_data
def load_and_process_data(symbol, start, end):
    try:
        data = yf.download(symbol, start=start, end=end, auto_adjust=True)
        if data.empty or len(data) < 40: return None
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        
        df = data.copy()
        # 布林通道
        bbands = ta.bbands(df['Close'], length=20, std=2)
        df['BBL'], df['BBM'], df['BBU'] = bbands.iloc[:, 0], bbands.iloc[:, 1], bbands.iloc[:, 2]
        # 均線
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['EMA10'] = ta.ema(df['Close'], length=10)
        df['EMA20'] = ta.ema(df['Close'], length=20)
        # 動能指標
        macd = ta.macd(df['Close'])
        df['MACD'], df['MACD_H'] = macd.iloc[:, 0], macd.iloc[:, 1]
        kd = ta.stoch(df['High'], df['Low'], df['Close'])
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        return df.dropna()
    except: return None

# --- 4. 主程式 ---
df = load_and_process_data(ticker_input, start_date, end_date)

if df is None:
    st.error("查無數據或代碼格式錯誤，請檢查後再試。")
else:
    curr = df.iloc[-1]
    curr_p = float(curr['Close'])
    
    # 計算分數與評分細節
    score = 0
    if curr['Close'] > curr['EMA20']: score += 4
    if curr['K'] > curr['D']: score += 3
    if curr['MACD_H'] > 0: score += 3

    st.title(f"📈 {ticker_input} 技術分析與進出建議")

    # 頂部指標
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("目前股價", f"{curr_p:.2f}")
    c2.metric("多空評分", f"{score} 分", "看多" if score >= 5 else "看空")
    c3.metric("EMA20 (關鍵支撐)", f"{curr['EMA20']:.2f}")
    c4.metric("布林上軌 (壓力位)", f"{curr['BBU']:.2f}")

    # 圖表區
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBU'], line=dict(color='rgba(255,255,255,0.2)'), name="布林上軌"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBL'], line=dict(color='rgba(255,255,255,0.2)'), name="布林下軌", fill='tonexty'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='orange', width=2), name="EMA20 (趨勢線)"), row=1, col=1)
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # --- 重點：進出價位建議區 ---
    st.markdown("### 🎯 實戰進出價位建議")
    
    # 邏輯計算建議價位
    # 進場區間：EMA20 到 EMA20 * 1.01 (1%誤差)
    entry_low = curr['EMA20'] * 0.995
    entry_high = curr['EMA20'] * 1.01
    # 止盈：布林上軌
    take_profit = curr['BBU']
    # 止損：EMA20 跌破 3% 或 布林下軌
    stop_loss = min(curr['BBL'], curr['EMA20'] * 0.97)

    box1, box2, box3 = st.columns(3)
    
    with box1:
        st.markdown('<div class="price-box">', unsafe_allow_html=True)
        st.write("🟢 **建議進場區間 (支撐)**")
        st.title(f"{entry_low:.2f} ~ {entry_high:.2f}")
        st.caption("說明：參考 EMA20 均線附近支撐進場，相對安全。")
        st.markdown('</div>', unsafe_allow_html=True)

    with box2:
        st.markdown('<div class="price-box">', unsafe_allow_html=True)
        st.write("🔴 **建議止盈目標 (壓力)**")
        st.title(f"{take_profit:.2f}")
        st.caption("說明：參考布林上軌，觸及此處代表短線乖離已大。")
        st.markdown('</div>', unsafe_allow_html=True)

    with box3:
        st.markdown('<div class="price-box">', unsafe_allow_html=True)
        st.write("⚠️ **建議止損價位 (停損)**")
        st.title(f"{stop_loss:.2f}")
        st.caption("說明：若收盤價跌破此價位，代表趨勢轉空，需離場。")
        st.markdown('</div>', unsafe_allow_html=True)

    # 策略小提醒
    st.info(f"""
    **📣 戰術執行：**
    1. 目前股價為 **{curr_p:.2f}**，距離建議進場區間約 **{((curr_p/entry_high)-1)*100:+.2% }**。
    2. 如果總分大於 5 分，且股價回測 EMA20 不破，是勝率較高的買點。
    3. **警語：** 本工具僅供技術分析參考，投資人應獨立判斷風險，盈虧自負。
    """)
