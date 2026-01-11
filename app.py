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
    .price-box { border: 1px solid #4B5563; padding: 15px; border-radius: 10px; background-color: #111827; height: 180px; }
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
- 上櫃股票：代碼 + .TWO (如 6147.TWO)
""")

# --- 3. 數據抓取與計算 ---
@st.cache_data
def load_and_process_data(symbol, start, end):
    try:
        data = yf.download(symbol, start=start, end=end, auto_adjust=True)
        if data.empty or len(data) < 40: return None
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        
        df = data.copy()
        # 布林通道 (使用 iloc 確保獲取)
        bbands = ta.bbands(df['Close'], length=20, std=2)
        df['BBL'], df['BBM'], df['BBU'] = bbands.iloc[:, 0], bbands.iloc[:, 1], bbands.iloc[:, 2]
        
        # 均線
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['EMA10'] = ta.ema(df['Close'], length=10)
        df['EMA20'] = ta.ema(df['Close'], length=20)
        
        # 指標
        macd = ta.macd(df['Close'])
        df['MACD'], df['MACD_H'] = macd.iloc[:, 0], macd.iloc[:, 1]
        kd = ta.stoch(df['High'], df['Low'], df['Close'])
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        return df.dropna()
    except: return None

# --- 4. 主程式流程 ---
df = load_and_process_data(ticker_input, start_date, end_date)

if df is None:
    st.error("查無數據或代碼格式錯誤。請確認：上市加 .TW，上櫃加 .TWO")
else:
    curr = df.iloc[-1]
    curr_p = float(curr['Close'])
    
    # 評分系統
    score = 0
    if curr['Close'] > curr['EMA20']: score += 4
    if curr['K'] > curr['D']: score += 3
    if curr['MACD_H'] > 0: score += 3

    st.title(f"📈 {ticker_input} 技術分析與進出建議")

    # 頂部指標摘要
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("目前股價", f"{curr_p:.2f}")
    c2.metric("多空評分", f"{score} 分", "偏多" if score >= 5 else "偏空")
    c3.metric("EMA20 (趨勢)", f"{curr['EMA20']:.2f}")
    c4.metric("RSI (14)", f"{curr['RSI']:.1f}")

    # 圖表
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBU'], line=dict(color='rgba(255,255,255,0.2)'), name="布林上軌"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBL'], line=dict(color='rgba(255,255,255,0.2)'), name="布林下軌", fill='tonexty'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='orange', width=2), name="EMA20"), row=1, col=1)
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # --- 🎯 進出價位建議 ---
    st.markdown("### 🎯 實戰進出價位建議")
    
    # 計算邏輯
    entry_target = curr['EMA20']  # 進場基準位
    take_profit = curr['BBU']     # 止盈參考位
    stop_loss = min(curr['BBL'], curr['EMA20'] * 0.97) # 止損位
    
    # 計算距離進場位的百分比 (修正後的格式)
    dist_to_entry = (curr_p / entry_target) - 1

    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown(f'<div class="price-box">🟢 <b>建議進場點 (支撐)</b><br><h2>{entry_target:.2f}</h2><p>參考 EMA20 均線，目前偏離 {dist_to_entry:+.2%}</p></div>', unsafe_allow_html=True)
    with b2:
        st.markdown(f'<div class="price-box">🔴 <b>止盈參考 (壓力)</b><br><h2>{take_profit:.2f}</h2><p>參考布林上軌位置</p></div>', unsafe_allow_html=True)
    with b3:
        st.markdown(f'<div class="price-box">⚠️ <b>止損參考 (破位)</b><br><h2>{stop_loss:.2f}</h2><p>跌破 EMA20 約 3% 或布林下軌</p></div>', unsafe_allow_html=True)

    # 戰術執行說明
    st.markdown("---")
    st.subheader("📝 戰術執行說明")
    
    # 根據距離給予不同建議
    if abs(dist_to_entry) < 0.015:
        advice = "✅ **股價正處於進場區間附近**，若指標維持多頭，是良好的佈局時機。"
    elif dist_to_entry > 0:
        advice = f"⌛ **股價目前高於進場區間 {dist_to_entry:.2%}**，建議等待回測支撐再行介入，避免追高。"
    else:
        advice = "⚠️ **股價低於趨勢支撐**，需觀察是否能在短時間內站回 EMA20，否則趨勢有轉弱風險。"

    st.info(f"""
    **📣 當前操作建議：**
    1. 目前股價：**{curr_p:.2f}**
    2. {advice}
    3. **多空評分報告：** 目前總分為 **{score} 分**，{ '盤勢強勁，適合偏多操作' if score >= 7 else '盤勢震盪，建議分批佈局' if score >= 4 else '盤勢偏弱，建議持幣觀望' }。
    """)
