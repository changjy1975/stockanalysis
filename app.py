import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="量化交易 Pro - 投資建議版", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .advice-box { padding: 20px; border-radius: 10px; border-left: 5px solid #00ff88; background-color: #1a1c24; margin-top: 20px; }
    .advice-title { font-size: 20px; font-weight: bold; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心數據處理與訊號計算 ---
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
        
        # 動態映射
        cols = df.columns
        mapping = {
            'EMA10': [c for c in cols if 'EMA_10' in c],
            'EMA20': [c for c in cols if 'EMA_20' in c],
            'MACD':  [c for c in cols if 'MACD_' in c and 'h' not in c and 's' not in c],
            'MACD_H':[c for c in cols if 'MACDh' in c],
            'K':     [c for c in cols if 'STOCHk' in c],
            'D':     [c for c in cols if 'STOCHd' in c],
            'RSI':   [c for c in cols if 'RSI' in c]
        }
        df.rename(columns={v[0]: k for k, v in mapping.items() if v}, inplace=True)
        
        # 訊號邏輯
        df['Buy_Signal'] = (df['K'] > df['D']) & (df['K'].shift(1) <= df['D'].shift(1)) & (df['K'] < 30) & (df['Close'] > df['EMA20'])
        df['Sell_Signal'] = ((df['EMA10'] < df['EMA20']) & (df['EMA10'].shift(1) >= df['EMA20'].shift(1))) | (df['RSI'] > 90)
        
        return df[df.index >= pd.to_datetime(start)].dropna()
    except: return None

# --- 3. 投資建議生成邏輯 ---
def generate_investment_advice(df):
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    advice_list = []
    
    # 1. MACD 分析 (動能)
    if curr['MACD_H'] > 0:
        if curr['MACD_H'] > prev['MACD_H']:
            advice_list.append("🚀 **MACD 動能強勁**：多方柱狀體持續擴大，顯示多頭攻擊力道轉強。")
        else:
            advice_list.append("⚠️ **MACD 動能減弱**：雖然紅柱仍在，但高度已縮減，需留意短線整理。")
    else:
        advice_list.append("📉 **MACD 趨勢偏空**：目前處於空方控盤區間，不建議在未出現買進訊號前進場。")

    # 2. RSI 分析 (位階)
    if curr['RSI'] > 75:
        advice_list.append("🔥 **RSI 進入超買區**：股價位階偏高，隨時可能回撤，建議停止追價。")
    elif curr['RSI'] < 30:
        advice_list.append("💎 **RSI 進入超跌區**：市場信心極度恐慌，若搭配 KD 金叉是優質抄底點。")
    else:
        advice_list.append("⚖️ **RSI 位階中性**：目前心理面與力道處於平衡狀態。")

    # 3. KD 分析 (轉折)
    if curr['K'] > curr['D']:
        advice_list.append("✅ **KD 處於多方交叉**：K 值大於 D 值，短線具備支撐與上攻機會。")
    else:
        advice_list.append("❌ **KD 處於空方交叉**：目前短線賣壓尚未消化，應耐心等待 K 值跌破 30 後的轉折。")

    # 總結戰術
    if curr['Buy_Signal']:
        summary = "🌟 **【強烈買進訊號】**：目前符合所有嚴謹抄底條件，建議建立部位。"
    elif curr['Sell_Signal']:
        summary = "🛑 **【趨勢撤退訊號】**：EMA10 已跌破月線或 RSI 爆表，請務必執行落袋為安，確保利潤。"
    elif curr['Close'] > curr['EMA20']:
        summary = "🟡 **【強勢區間整理】**：趨勢仍在月線之上，建議持股續抱，但不宜在此位階大幅加碼。"
    else:
        summary = "⚪ **【盤整/偏弱觀察】**：趨勢未明，建議空手等待或減碼觀望。"
        
    return summary, advice_list

# --- 4. 主程式流程 ---
st.sidebar.header("📊 投資參數")
ticker_input = st.sidebar.text_input("股票代碼", "2330.TW").upper()
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))

df = load_and_process_data(ticker_input, start_date, datetime.now())

if df is not None:
    st.title(f"📈 {ticker_input} 全指標智慧看板")
    
    # 指標摘要
    curr = df.iloc[-1]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("目前股價", f"{curr['Close']:.2f}")
    m2.metric("MACD 柱體", f"{curr['MACD_H']:.2f}")
    m3.metric("RSI(14)", f"{curr['RSI']:.1f}")
    m4.metric("K值 (KD)", f"{curr['K']:.1f}")

    # --- 新功能：AI 投資建議區塊 ---
    summary, advice_items = generate_investment_advice(df)
    
    st.markdown(f"""
    <div class="advice-box">
        <div class="advice-title">🤖 實戰技術面診斷報告</div>
        <p style='font-size:18px;'>{summary}</p>
        <hr style='margin:10px 0;'>
        <ul>
            {"".join([f"<li>{item}</li>" for item in advice_items])}
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # 圖表部分 (保持原有精美繪製)
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.15, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='#00ff88', width=2), name="EMA10"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#ffaa00', width=2), name="EMA20"), row=1, col=1)
    
    # 標註買賣點
    buy_pts = df[df['Buy_Signal']]
    fig.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.97, mode='markers', marker=dict(symbol='triangle-up', size=15, color='lime'), name='買入'), row=1, col=1)
    sell_pts = df[df['Sell_Signal']]
    fig.add_trace(go.Scatter(x=sell_pts.index, y=sell_pts['High']*1.03, mode='markers', marker=dict(symbol='triangle-down', size=15, color='red'), name='賣出'), row=1, col=1)

    # MACD / KD / RSI
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=['red' if x > 0 else 'green' for x in df['MACD_H']], name="MACD柱"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan'), name='K'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold'), name='RSI'), row=4, col=1)

    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("數據獲取失敗。")
