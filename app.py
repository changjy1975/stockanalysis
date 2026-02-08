import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="量化交易看板 PRO (極端賣出警示版)", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .price-box { border: 1px solid #4B5563; padding: 15px; border-radius: 10px; background-color: #111827; text-align: center; height: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心數據處理與訊號計算 ---
@st.cache_data(ttl=3600)
def load_and_process_data(symbol, start, end):
    try:
        start_buffer = pd.to_datetime(start) - timedelta(days=120)
        df = yf.download(symbol, start=start_buffer, end=end, auto_adjust=True)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        
        # 指標計算
        df.ta.ema(length=10, append=True)
        df.ta.ema(length=20, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.macd(append=True)
        df.ta.stoch(append=True)
        df.ta.rsi(length=14, append=True)
        
        # 動態映射欄位
        cols = df.columns
        mapping = {
            'EMA10': [c for c in cols if 'EMA_10' in c],
            'EMA20': [c for c in cols if 'EMA_20' in c],
            'BBU':   [c for c in cols if 'BBU' in c],
            'BBL':   [c for c in cols if 'BBL' in c],
            'MACD_H':[c for c in cols if 'MACDh' in c],
            'K':     [c for c in cols if 'STOCHk' in c],
            'D':     [c for c in cols if 'STOCHd' in c],
            'RSI':   [c for c in cols if 'RSI' in c]
        }
        df.rename(columns={v[0]: k for k, v in mapping.items() if v}, inplace=True)
        
        # --- 買賣訊號邏輯 (依據最新指示：或 (OR) 邏輯) ---
        # 買進：KD 金叉 + K < 30 + 站在月線 EMA20 之上
        df['Buy_Signal'] = (df['K'] > df['D']) & (df['K'].shift(1) <= df['D'].shift(1)) & \
                           (df['K'] < 30) & (df['Close'] > df['EMA20'])
        
        # 賣出：跌破 EMA10 "或" RSI > 90 (極度超買)
        df['Sell_Signal'] = (df['Close'] < df['EMA10']) | (df['RSI'] > 90)
        
        return df[df.index >= pd.to_datetime(start)].dropna()
    except: return None

# --- 3. 側邊欄與數據載入 ---
st.sidebar.header("📊 投資參數")
ticker_input = st.sidebar.text_input("股票代碼", "2330.TW").upper()
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))

df = load_and_process_data(ticker_input, start_date, datetime.now())

if df is not None:
    curr = df.iloc[-1]
    curr_p = float(curr['Close'])
    
    st.title(f"📈 {ticker_input} 技術指標看板 (EMA10 或 RSI>90)")
    
    # 第一層：指標摘要
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("目前股價", f"{curr_p:.2f}", f"{(curr_p - df['Close'].iloc[-2]):+.2f}")
    m2.metric("RSI(14)", f"{curr['RSI']:.1f}")
    m3.metric("K值 (KD)", f"{curr['K']:.1f}")
    m4.metric("EMA10 門檻", f"{curr['EMA10']:.2f}")

    # --- 4. 繪製圖表 ---
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.4, 0.1, 0.15, 0.15, 0.2])
    
    # K線主圖
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='#00ff88', width=1.5), name="EMA10"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#ffaa00', width=1.5), name="EMA20"), row=1, col=1)

    # 買進標記 (綠色三角形)
    buy_df = df[df['Buy_Signal']]
    fig.add_trace(go.Scatter(x=buy_df.index, y=buy_df['Low'] * 0.97, mode='markers', name='買入',
                             marker=dict(symbol='triangle-up', size=15, color='lime', line=dict(width=1, color='white'))), row=1, col=1)

    # 賣出標記 (紅色三角形) - 使用 Shift 避免連續顯示訊號
    sell_df = df[df['Sell_Signal']]
    sell_df_display = sell_df[~sell_df['Sell_Signal'].shift(1).fillna(False)]
    fig.add_trace(go.Scatter(x=sell_df_display.index, y=sell_df_display['High'] * 1.03, mode='markers', name='賣出',
                             marker=dict(symbol='triangle-down', size=15, color='red', line=dict(width=1, color='white'))), row=1, col=1)

    # 成交量
    vol_colors = ['red' if df['Close'].iloc[i] >= df['Open'].iloc[i] else 'green' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=vol_colors, name="成交量", opacity=0.6), row=2, col=1)

    # MACD
    macd_colors = ['red' if x > 0 else 'green' for x in df['MACD_H']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], marker_color=macd_colors, name="MACD柱"), row=3, col=1)
    
    # KD
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan'), name='K'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta'), name='D'), row=4, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold'), name='RSI'), row=5, col=1)
    fig.add_hline(y=90, line_dash="dash", line_color="red", opacity=0.8, row=5, col=1, annotation_text="超買獲利 (90)")
    fig.add_hline(y=30, line_dash="dot", line_color="green", opacity=0.3, row=5, col=1)

    fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=50, r=50, t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)

    # 策略解釋
    st.subheader("🔍 當前交易策略邏輯")
    c1, c2 = st.columns(2)
    with c1:
        st.success("**🟢 買進：低位階抄底順勢**\n1. KD 金叉\n2. K < 30\n3. 站在月線 EMA20 之上")
    with c2:
        st.error("**🔴 賣出：快速撤退/獲利了結**\n1. 股價跌破 EMA10 (趨勢轉弱)\n2. **或** RSI > 90 (極端超買趕頂)")

else:
    st.error("數據載入失敗，請確認代碼格式與網路連線。")
