import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="量化交易 Pro - 完整指標版", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .advice-box { padding: 20px; border-radius: 10px; border-left: 5px solid #00ff88; background-color: #1a1c24; margin-top: 20px; }
    .advice-title { font-size: 20px; font-weight: bold; margin-bottom: 10px; }
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
        df.ta.macd(append=True)
        df.ta.stoch(append=True)
        df.ta.rsi(length=14, append=True)
        
        # 動態映射 (確保欄位正確)
        cols = df.columns
        mapping = {
            'EMA10': [c for c in cols if 'EMA_10' in c],
            'EMA20': [c for c in cols if 'EMA_20' in c],
            'MACD_H':[c for c in cols if 'MACDh' in c],
            'K':     [c for c in cols if 'STOCHk' in c],
            'D':     [c for c in cols if 'STOCHd' in c],
            'RSI':   [c for c in cols if 'RSI' in c]
        }
        df.rename(columns={v[0]: k for k, v in mapping.items() if v}, inplace=True)
        
        # --- 買賣訊號邏輯 ---
        # 買進：KD金叉(且K<30) 且 站在月線上
        df['Buy_Signal'] = (df['K'] > df['D']) & (df['K'].shift(1) <= df['D'].shift(1)) & \
                           (df['K'] < 30) & (df['Close'] > df['EMA20'])
        
        # 賣出：EMA10 跌破 EMA20 (瞬間) 或 RSI 衝破 90 (瞬間)
        death_cross = (df['EMA10'] < df['EMA20']) & (df['EMA10'].shift(1) >= df['EMA20'].shift(1))
        rsi_overheat = (df['RSI'] > 90) & (df['RSI'].shift(1) <= 90)
        df['Sell_Signal'] = death_cross | rsi_overheat
        
        return df[df.index >= pd.to_datetime(start)].dropna()
    except: return None

# --- 3. 投資建議生成 ---
def generate_advice(df):
    curr = df.iloc[-1]
    summary = "🟡 **【持股續抱 / 觀察期】**"
    advice_items = []
    
    if curr['Buy_Signal']:
        summary = "🌟 **【強烈買進訊號】**：低位階 KD 金叉且站穩月線，是理想布局點。"
    elif curr['Sell_Signal']:
        summary = "🛑 **【趨勢撤退訊號】**：趨勢已轉弱或極度過熱，建議優先落袋為安。"
    
    advice_items.append(f"📌 **KD 分析**：目前 K 值 {curr['K']:.1f}，{'處於多方交叉' if curr['K']>curr['D'] else '處於空方交叉'}。")
    advice_items.append(f"📌 **RSI 分析**：目前位階 {curr['RSI']:.1f}，{'過熱需謹慎' if curr['RSI']>75 else '處於安全區間'}。")
    advice_items.append(f"📌 **趨勢分析**：股價{'在月線之上' if curr['Close']>curr['EMA20'] else '跌破月線'}，中期多頭{'仍健在' if curr['Close']>curr['EMA20'] else '受阻'}。")
    
    return summary, advice_items

# --- 4. 主介面顯示 ---
st.sidebar.header("📊 投資參數")
ticker_input = st.sidebar.text_input("股票代碼", "2330.TW").upper()
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))

df = load_and_process_data(ticker_input, start_date, datetime.now())

if df is not None:
    curr = df.iloc[-1]
    st.title(f"📈 {ticker_input} 全指標技術看板")
    
    # AI 投資建議
    summary, advice_items = generate_advice(df)
    st.markdown(f"""
    <div class="advice-box">
        <div class="advice-title">🤖 實戰建議診斷</div>
        <p style='font-size:18px;'>{summary}</p>
        <hr style='margin:10px 0;'>
        <ul>{"".join([f"<li>{item}</li>" for item in advice_items])}</ul>
    </div>
    """, unsafe_allow_html=True)

    # 圖表繪製
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.15, 0.2])
    
    # 1. K線主圖 (含均線與買賣訊號)
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='#00ff88', width=2), name="EMA10"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#ffaa00', width=2), name="EMA20"), row=1, col=1)
    
    buy_pts = df[df['Buy_Signal']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.97, mode='markers', marker=dict(symbol='triangle-up', size=15, color='lime'), name='買入'), row=1, col=1)
    sell_pts = df[df['Sell_Signal']]
    fig.add_trace(go.Scatter(x=sell_pts.index, y=sell_pts['High']*1.03, mode='markers', marker=dict(symbol='triangle-down', size=15, color='red'), name='賣出'), row=1, col=1)

    # 2. MACD (紅漲綠跌)
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=['red' if x > 0 else 'green' for x in df['MACD_H']], name="MACD柱"), row=2, col=1)

    # 3. 完整 KD 線圖 (K線 + D線)
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1.5), name='K值'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1.5), name='D值'), row=3, col=1)
    fig.add_hline(y=80, line_dash="dot", line_color="red", opacity=0.3, row=3, col=1)
    fig.add_hline(y=20, line_dash="dot", line_color="green", opacity=0.3, row=3, col=1)

    # 4. RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1.5), name='RSI'), row=4, col=1)
    fig.add_hline(y=90, line_dash="dash", line_color="red", row=4, col=1)

    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=50, r=50, t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("數據獲取失敗，請確認代碼。")
