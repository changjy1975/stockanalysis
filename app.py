import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="量化交易看板 PRO (紅綠強化版)", layout="wide")

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
        # 緩衝期確保長線指標計算準確
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
        
        # --- 動態欄位映射 (防錯邏輯) ---
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
        
        final_rename = {}
        for key, found_cols in mapping.items():
            if found_cols:
                final_rename[found_cols[0]] = key
        
        df.rename(columns=final_rename, inplace=True)
        
        # 確保必要欄位完整
        required_cols = ['EMA10', 'EMA20', 'BBU', 'BBL', 'MACD_H', 'K', 'D', 'RSI']
        if not all(col in df.columns for col in required_cols):
            return None
            
        return df[df.index >= pd.to_datetime(start)].dropna()
    except:
        return None

# --- 3. 主介面設計 ---
st.sidebar.header("📊 投資參數")
ticker_input = st.sidebar.text_input("股票代碼", "2330.TW").upper()
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

df = load_and_process_data(ticker_input, start_date, end_date)

if df is not None:
    curr = df.iloc[-1]
    curr_p = float(curr['Close'])
    prev_p = float(df['Close'].iloc[-2])
    
    st.title(f"📈 {ticker_input} 技術指標看板")
    
    # 指標摘要
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("目前股價", f"{curr_p:.2f}", f"{curr_p - prev_p:+.2f}")
    m3.metric("RSI(14)", f"{curr['RSI']:.1f}")
    m4.metric("今日成交量", f"{int(curr['Volume']):,}")

    st.markdown("---")

    # 交易建議位
    entry_p, tp_p, sl_p = curr['EMA10'], curr['BBU'], min(curr['BBL'], curr['EMA20'] * 0.97)
    p1, p2, p3 = st.columns(3)
    p1.markdown(f'<div class="price-box">🟢 <b>建議進場 (EMA10)</b><br><h2>{entry_p:.2f}</h2></div>', unsafe_allow_html=True)
    p2.markdown(f'<div class="price-box">🔴 <b>短線目標 (布林上軌)</b><br><h2>{tp_p:.2f}</h2></div>', unsafe_allow_html=True)
    p3.markdown(f'<div class="price-box">⚠️ <b>關鍵止損 (月線/下軌)</b><br><h2>{sl_p:.2f}</h2></div>', unsafe_allow_html=True)

    # --- 4. 繪製圖表 (包含 MACD 顏色優化) ---
    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=True, 
        vertical_spacing=0.02, 
        row_heights=[0.4, 0.1, 0.15, 0.15, 0.2]
    )

    # 主圖: K線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='#00ff88', width=1.5), name="EMA10"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#ffaa00', width=1.5), name="EMA20"), row=1, col=1)

    # 成交量: 紅漲綠跌 (台灣慣用色)
    vol_colors = ['red' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'green' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量", marker_color=vol_colors, opacity=0.7), row=2, col=1)

    # MACD: 柱狀圖紅綠色 (紅漲綠跌)
    macd_colors = ['red' if x > 0 else 'green' for x in df['MACD_H']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD柱', marker_color=macd_colors), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='white', width=1), name='MACD線'), row=3, col=1)

    # KD
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan'), name='K'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta'), name='D'), row=4, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold'), name='RSI'), row=5, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=5, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=5, col=1)

    fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=50, r=50, t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)

    # 戰術提醒
    st.subheader("💡 實戰提醒")
    dist = (curr_p / entry_p) - 1
    if abs(dist) < 0.02:
        st.success(f"🎯 股價與 EMA10 距離僅 {dist:.1%}，目前處於理想的技術面進場區間。")
    elif dist > 0.05:
        st.warning(f"⚠️ 短線乖離過大 ({dist:.1%})，建議等待回測 EMA10 再行佈局。")
    else:
        st.info("📊 目前股價走勢偏弱或處於整理期，建議觀察是否能守住月線支撐。")

else:
    st.error("數據載入失敗。請確認代碼（如：2330.TW）與網路連線。")
