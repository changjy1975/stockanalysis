import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="量化交易看板 PRO (技術回歸版)", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .price-box { border: 1px solid #4B5563; padding: 15px; border-radius: 10px; background-color: #111827; text-align: center; height: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心數據處理與動態映射 ---
@st.cache_data(ttl=3600)
def load_and_process_data(symbol, start, end):
    try:
        # 提供 120 天緩衝以滿足指標計算
        start_buffer = pd.to_datetime(start) - timedelta(days=120)
        df = yf.download(symbol, start=start_buffer, end=end, auto_adjust=True)
        
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 指標計算
        df.ta.ema(length=10, append=True)
        df.ta.ema(length=20, append=True)
        df.ta.sma(length=60, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.macd(append=True)
        df.ta.stoch(append=True)
        df.ta.rsi(length=14, append=True)
        
        # --- 動態映射邏輯：防止 KeyError ---
        cols = df.columns
        mapping = {
            'EMA10': [c for c in cols if 'EMA_10' in c],
            'EMA20': [c for c in cols if 'EMA_20' in c],
            'MA60':  [c for c in cols if 'SMA_60' in c],
            'BBL':   [c for c in cols if 'BBL' in c],
            'BBM':   [c for c in cols if 'BBM' in c],
            'BBU':   [c for c in cols if 'BBU' in c],
            'MACD':  [c for c in cols if 'MACD_' in c and 'h' not in c and 's' not in c],
            'MACD_H':[c for c in cols if 'MACDh' in c],
            'K':     [c for c in cols if 'STOCHk' in c],
            'D':     [c for c in cols if 'STOCHd' in c],
            'RSI':   [c for c in cols if 'RSI' in c]
        }
        
        final_rename = {v[0]: k for k, v in mapping.items() if v}
        df.rename(columns=final_rename, inplace=True)
        
        # 確保必要欄位完整
        if 'EMA10' not in df.columns or 'BBU' not in df.columns:
            return None
            
        return df[df.index >= pd.to_datetime(start)].dropna()
    except:
        return None

# --- 3. 技術面評分系統 ---
def get_technical_score(df):
    score = 0
    details = []
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 趨勢：均線排列
    if curr['Close'] > curr['EMA10'] > curr['EMA20']:
        score += 4; details.append("✅ 均線多頭排列：強勢攻擊波")
    elif curr['Close'] > curr['EMA20']:
        score += 2; details.append("✅ 趨勢偏多：站穩月線支撐")
    else: 
        score -= 3; details.append("❌ 趨勢疲軟：破月線觀望")
    
    # 動能：MACD 柱狀體
    if curr['MACD_H'] > 0: score += 2; details.append("✅ MACD 柱狀體翻紅")
    else: score -= 2; details.append("❌ MACD 柱狀體翻綠")
    
    # 交叉：KD 金叉
    if curr['K'] > curr['D'] and prev['K'] <= prev['D']:
        score += 3; details.append("🔥 KD 出現黃金交叉")
    
    # 位階：RSI
    if curr['RSI'] > 75: score -= 2; details.append("⚠️ RSI 超過 75 (短線過熱)")
    elif curr['RSI'] < 30: score += 2; details.append("💎 RSI 低於 30 (進入超跌)")
    
    return score, details

# --- 4. 主介面顯示 ---
st.sidebar.header("📊 投資參數")
ticker_input = st.sidebar.text_input("股票代碼", "2330.TW").upper()
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))

df = load_and_process_data(ticker_input, start_date, datetime.now())

if df is not None:
    score, details = get_technical_score(df)
    curr = df.iloc[-1]
    curr_p = float(curr['Close'])
    
    st.title(f"📈 {ticker_input} 技術指標看板")
    
    # 第一層：指標摘要
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("目前股價", f"{curr_p:.2f}", f"{(curr_p - df['Close'].iloc[-2]):+.2f}")
    m2.metric("技術評分", f"{score} 分", "看多" if score > 0 else "看空")
    m3.metric("RSI(14)", f"{curr['RSI']:.1f}")
    m4.metric("成交量", f"{int(curr['Volume']):,}")

    st.markdown("---")

    # 第二層：進出策略建議
    entry_p = curr['EMA10']
    tp_p = curr['BBU']
    sl_p = min(curr['BBL'], curr['EMA20'] * 0.97)
    dist = (curr_p / entry_p) - 1

    p1, p2, p3 = st.columns(3)
    p1.markdown(f'<div class="price-box">🟢 <b>建議進場 (EMA10)</b><br><h2>{entry_p:.2f}</h2><p>乖離率: {dist:+.2%}</p></div>', unsafe_allow_html=True)
    p2.markdown(f'<div class="price-box">🔴 <b>短線止盈 (布林上軌)</b><br><h2>{tp_p:.2f}</h2><p>空間: {((tp_p/curr_p)-1):+.2%}</p></div>', unsafe_allow_html=True)
    p3.markdown(f'<div class="price-box">⚠️ <b>關鍵止損 (月線)</b><br><h2>{sl_p:.2f}</h2><p>風險: {((sl_p/curr_p)-1):+.2%}</p></div>', unsafe_allow_html=True)

    # 第三層：視覺化圖表
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.4, 0.1, 0.15, 0.15, 0.2])
    
    # 主圖
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='#00ff88', width=1.5), name="EMA10"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#ffaa00', width=1.5), name="EMA20"), row=1, col=1)

    # 成交量 (紅漲綠跌)
    vol_colors = ['red' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'green' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name="成交量", opacity=0.7), row=2, col=1)

    # MACD (紅漲綠跌)
    macd_colors = ['red' if x > 0 else 'green' for x in df['MACD_H']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=macd_colors, name="MACD柱"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='white', width=1), name='MACD線'), row=3, col=1)

    # KD & RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan'), name='K'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta'), name='D'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold'), name='RSI'), row=5, col=1)

    fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=50, r=50, t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)

    # 診斷報告
    st.subheader("🔍 AI 技術面診斷")
    for d in details:
        st.write(d)
else:
    st.error("無法抓取數據，請確認代碼 (例如: 2330.TW) 或日期區間是否包含足夠數據。")
