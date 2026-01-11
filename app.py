import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 (手機 App 模式優化) ---
st.set_page_config(page_title="專業級股市 App", layout="wide")

# 自定義 CSS：強化手機版視覺與圓角區塊
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 10px; border-radius: 8px; }
    .price-card { 
        border: 1px solid #4B5563; 
        padding: 15px; 
        border-radius: 12px; 
        background-color: #1a1c24; 
        margin-bottom: 10px;
        text-align: center;
    }
    .status-text { font-size: 0.9rem; color: #9CA3AF; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄設定 (手機版會隱藏，適合放參數) ---
st.sidebar.header("📊 參數設定")
ticker_input = st.sidebar.text_input("輸入代碼", "2330.TW").upper()
days_back = st.sidebar.slider("查詢天數", 100, 730, 365)
start_date = datetime.now() - timedelta(days=days_back)
end_date = datetime.now()

# --- 3. 數據核心 ---
@st.cache_data
def load_data(symbol, start, end):
    try:
        data = yf.download(symbol, start=start, end=end, auto_adjust=True)
        if data.empty or len(data) < 40: return None
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        df = data.copy()
        # 技術指標計算
        bbands = ta.bbands(df['Close'], length=20, std=2)
        df['BBL'], df['BBM'], df['BBU'] = bbands.iloc[:, 0], bbands.iloc[:, 1], bbands.iloc[:, 2]
        df['EMA10'], df['EMA20'] = ta.ema(df['Close'], length=10), ta.ema(df['Close'], length=20)
        macd = ta.macd(df['Close'])
        df['MACD'], df['MACD_H'] = macd.iloc[:, 0], macd.iloc[:, 1]
        kd = ta.stoch(df['High'], df['Low'], df['Close'])
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        df['RSI'] = ta.rsi(df['Close'], length=14)
        return df.dropna()
    except: return None

# --- 4. 評分邏輯 ---
def get_score(df):
    score = 0
    curr = df.iloc[-1]
    if curr['Close'] > curr['EMA10'] > curr['EMA20']: score += 4
    elif curr['Close'] > curr['EMA20']: score += 2
    else: score -= 3
    if curr['MACD_H'] > 0: score += 2
    else: score -= 2
    if curr['K'] > curr['D']: score += 2
    else: score -= 2
    if curr['RSI'] > 75: score -= 2
    elif curr['RSI'] < 25: score += 2
    return score

# --- 5. 主介面流程 ---
df = load_data(ticker_input, start_date, end_date)

if df is None:
    st.error("查無數據，請確認代碼 (上市.TW/上櫃.TWO)")
else:
    curr = df.iloc[-1]
    curr_p = float(curr['Close'])
    total_score = get_score(df)
    
    # 標題區
    st.title(f"{ticker_input} 分析看板")
    
    # 手機首屏摘要 (2x2 排版)
    m1, m2 = st.columns(2)
    m1.metric("目前股價", f"{curr_p:.2f}", f"{(curr_p - df['Close'].iloc[-2]):+.2f}")
    m2.metric("綜合評分", f"{total_score} 分", "看多" if total_score > 0 else "看空")
    
    st.markdown("---")

    # 手機 App 核心區：進出建議 (直向排版更適合手機)
    st.subheader("🎯 實戰進出建議")
    
    entry_p = curr['EMA10']
    tp_p = curr['BBU']
    sl_p = min(curr['BBL'], curr['EMA20'] * 0.97)
    dist = (curr_p / entry_p) - 1

    # 在手機上，columns 會自動堆疊
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(f'<div class="price-card"><span class="status-text">🟢 進場基準 (EMA10)</span><h2>{entry_p:.2f}</h2><p style="color:{"#10b981" if dist < 0.015 else "#f59e0b"}">乖離率: {dist:+.1%}</p></div>', unsafe_allow_html=True)
    with p2:
        st.markdown(f'<div class="price-card"><span class="status-text">🔴 短線止盈 (布林上)</span><h2>{tp_p:.2f}</h2><p>目標空間: {((tp_p/curr_p)-1):.1%}</p></div>', unsafe_allow_html=True)
    with p3:
        st.markdown(f'<div class="price-card"><span class="status-text">⚠️ 關鍵止損位</span><h2>{sl_p:.2f}</h2><p>防守空間: {((sl_p/curr_p)-1):.1%}</p></div>', unsafe_allow_html=True)

    # 戰術提示小方塊
    if abs(dist) < 0.015:
        st.success(f"✅ **當前時機良好**：股價接近 EMA10 ({entry_p:.2f})，適合佈局。")
    elif dist > 0:
        st.warning(f"⌛ **建議等待**：目前股價較 EMA10 偏高，回測至 {entry_p:.2f} 附近再考慮。")

    st.markdown("---")

    # 專業指標圖表 (保留四層級)
    st.subheader("📊 技術面全圖譜")
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.15, 0.2])
    
    # 1. K線 + 均線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='#10b981', width=1), name="EMA10"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#f59e0b', width=1), name="EMA20"), row=1, col=1)
    
    # 2. MACD
    colors = ['#10b981' if x > 0 else '#ef4444' for x in df['MACD_H']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD', marker_color=colors), row=2, col=1)
    
    # 3. KD
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1), name='K'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1), name='D'), row=3, col=1)
    
    # 4. RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1), name='RSI'), row=4, col=1)

    fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=5, r=5, t=5, b=5), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
