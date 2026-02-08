import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="量化交易 Pro - 多因子評分版", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .factor-card { border: 1px solid #4B5563; padding: 15px; border-radius: 10px; background-color: #1a1c24; margin-bottom: 10px; }
    .score-high { color: #00ff88; font-size: 24px; font-weight: bold; }
    .score-low { color: #ff4b4b; font-size: 24px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 數據抓取與處理 ---
@st.cache_data(ttl=3600)
def load_all_data(symbol, start, end):
    try:
        # 抓取技術面數據 (增加到 365 天緩衝以滿足 MA200)
        start_buffer = pd.to_datetime(start) - timedelta(days=365)
        df = yf.download(symbol, start=start_buffer, end=end, auto_adjust=True)
        if df.empty: return None, None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 技術指標計算
        df.ta.ema(length=10, append=True)
        df.ta.ema(length=20, append=True)
        df.ta.sma(length=200, append=True) # 200日均線
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.macd(append=True)
        df.ta.stoch(append=True)
        df.ta.rsi(length=14, append=True)
        
        # 欄位映射
        cols = df.columns
        df.rename(columns={
            [c for c in cols if 'EMA_10' in c][0]: 'EMA10',
            [c for c in cols if 'EMA_20' in c][0]: 'EMA20',
            [c for c in cols if 'SMA_200' in c][0]: 'MA200',
            [c for c in cols if 'BBU' in c][0]: 'BBU',
            [c for c in cols if 'BBL' in c][0]: 'BBL',
            [c for c in cols if 'MACDh' in c][0]: 'MACD_H',
            [c for c in cols if 'STOCHk' in c][0]: 'K',
            [c for c in cols if 'STOCHd' in c][0]: 'D',
            [c for c in cols if 'RSI' in c][0]: 'RSI'
        }, inplace=True)

        # 抓取基本面數據
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        fundamental_data = {
            "pe": info.get("trailingPE"),
            "revenue_growth": info.get("revenueGrowth", 0),
            "sector": info.get("sector", "Other"),
            "industry": info.get("industry", "N/A")
        }
        
        return df[df.index >= pd.to_datetime(start)].dropna(), fundamental_data
    except:
        return None, None

# --- 3. 多因子評分邏輯 ---
def calculate_multi_factor_score(df, fundamentals):
    # 產業平均 PE 映射表 (粗估值，可依需求調整)
    industry_pe_map = {
        "Technology": 35.0, "Financial Services": 15.0, "Healthcare": 25.0,
        "Consumer Cyclical": 25.0, "Energy": 12.0, "Utilities": 18.0, "Real Estate": 30.0
    }
    avg_pe = industry_pe_map.get(fundamentals['sector'], 20.0)
    
    curr = df.iloc[-1]
    results = []
    total_score = 0
    
    # 1. 趨勢因子 (50%)
    trend_pass = curr['Close'] > curr['MA200']
    trend_val = 50 if trend_pass else 0
    total_score += trend_val
    results.append({"factor": "趨勢 (Trend)", "desc": "價格 > 200MA" if trend_pass else "價格 < 200MA", "score": trend_val, "weight": 50})
    
    # 2. 成長因子 (30%)
    growth_pass = fundamentals['revenue_growth'] > 0.15
    growth_val = 30 if growth_pass else 0
    total_score += growth_val
    results.append({"factor": "成長 (Growth)", "desc": f"營收年增 {fundamentals['revenue_growth']:.1%}" + (" (>15%)" if growth_pass else " (<15%)"), "score": growth_val, "weight": 30})
    
    # 3. 價值因子 (20%)
    pe = fundamentals['pe']
    value_pass = pe is not None and pe < avg_pe
    value_val = 20 if value_pass else 0
    total_score += value_val
    pe_str = f"{pe:.1f}" if pe else "N/A"
    results.append({"factor": "價值 (Value)", "desc": f"P/E {pe_str} vs 產業平均 {avg_pe}", "score": value_val, "weight": 20})
    
    return total_score, results

# --- 4. 側邊欄與主頁面 ---
st.sidebar.header("📊 參數設定")
ticker_input = st.sidebar.text_input("股票代碼", "2330.TW").upper()
start_date = st.sidebar.date_input("分析開始", datetime.now() - timedelta(days=365))

df, fundamentals = load_all_data(ticker_input, start_date, datetime.now())

if df is not None:
    score, factor_details = calculate_multi_factor_score(df, fundamentals)
    curr_p = df['Close'].iloc[-1]
    
    st.title(f"📈 {ticker_input} 多因子量化看板")
    
    # 第一層：評分摘要
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.metric("目前股價", f"{curr_p:.2f}")
        st.write(f"**產業:** {fundamentals['sector']}")
    with c2:
        st.markdown(f"### 綜合評分: <span class='{'score-high' if score >= 70 else 'score-low'}'>{score} / 100</span>", unsafe_allow_html=True)
        st.progress(score / 100)
    with c3:
        status = "🟢 強勢優質股" if score >= 80 else "🟡 觀望/中性" if score >= 50 else "🔴 弱勢或高價"
        st.subheader(status)

    st.markdown("---")

    # 第二層：多因子細節
    st.subheader("📊 多因子評分細節")
    f_cols = st.columns(3)
    for i, f in enumerate(factor_details):
        with f_cols[i]:
            st.markdown(f"""
            <div class="factor-card">
                <h4>{f['factor']}</h4>
                <p>{f['desc']}</p>
                <h2 style="color:{'#00ff88' if f['score'] > 0 else '#ff4b4b'}">{f['score']} / {f['weight']}</h2>
            </div>
            """, unsafe_allow_html=True)

    # 第三層：圖表 (含 MA200)
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.4, 0.1, 0.15, 0.15, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='white', width=2, dash='dot'), name="MA200 (生命線)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='#00ff88', width=1.5), name="EMA10"), row=1, col=1)
    
    # 成交量
    vol_colors = ['red' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'green' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name="成交量"), row=2, col=1)
    
    # MACD 紅綠柱
    macd_colors = ['red' if x > 0 else 'green' for x in df['MACD_H']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=macd_colors, name="MACD柱"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan'), name='K'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold'), name='RSI'), row=5, col=1)

    fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.error("數據獲取失敗，請確認代碼（如：TSLA 或 2330.TW）")
