import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="量化交易看板 PRO", layout="wide")

# 自定義 CSS (強化視覺層次)
st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .price-box { border: 1px solid #4B5563; padding: 15px; border-radius: 10px; background-color: #111827; text-align: center; height: 100%; }
    .recommend-green { color: #00ff88; font-weight: bold; }
    .recommend-red { color: #ff4b4b; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心數據處理 ---
@st.cache_data(ttl=3600)
def load_and_process_data(symbol, start, end):
    try:
        # 增加緩衝時間以計算長週期指標 (如 MA60)
        start_buffer = pd.to_datetime(start) - timedelta(days=120)
        df = yf.download(symbol, start=start_buffer, end=end, auto_adjust=True)
        
        if df.empty: return None
        
        # 處理新版 yfinance 可能產生的 MultiIndex 欄位
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 使用 pandas_ta 進行向量化計算
        df.ta.ema(length=10, append=True)
        df.ta.ema(length=20, append=True)
        df.ta.sma(length=60, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.macd(append=True)
        df.ta.stoch(append=True)
        df.ta.rsi(length=14, append=True)
        
        # 統一欄位名稱以方便調用
        df.rename(columns={
            'EMA_10': 'EMA10', 'EMA_20': 'EMA20', 'SMA_60': 'MA60',
            'BBL_20_2.0': 'BBL', 'BBM_20_2.0': 'BBM', 'BBU_20_2.0': 'BBU',
            'MACD_12_26_9': 'MACD', 'MACDh_12_26_9': 'MACD_H', 'MACDs_12_26_9': 'MACD_S',
            'STOCHk_14_3_3': 'K', 'STOCHd_14_3_3': 'D', 'RSI_14': 'RSI'
        }, inplace=True)
        
        # 僅保留使用者選取的區間
        return df[df.index >= pd.to_datetime(start)].dropna()
    except Exception as e:
        st.error(f"數據抓取失敗: {e}")
        return None

# --- 3. 評分邏輯 (加權演算法) ---
def get_score(df):
    score = 0
    details = []
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 趨勢：均線多頭排列
    if curr['Close'] > curr['EMA10'] > curr['EMA20']:
        score += 4; details.append("✅ 均線多頭排列：強勢攻擊波")
    elif curr['Close'] > curr['EMA20']:
        score += 2; details.append("✅ 趨勢偏多：站穩月線支撐")
    else: 
        score -= 3; details.append("❌ 趨勢疲軟：破月線觀望")
    
    # 動能：MACD 與 KD
    if curr['MACD_H'] > 0: score += 2; details.append("✅ MACD 柱狀體翻紅")
    if curr['K'] > curr['D'] and prev['K'] <= prev['D']:
        score += 3; details.append("🔥 KD 出現黃金交叉")
    elif curr['K'] > curr['D']:
        score += 1; details.append("✅ KD 持續向上")
    
    # 位階：RSI
    if curr['RSI'] > 75: score -= 2; details.append("⚠️ RSI 超過 75 (短線過熱)")
    elif curr['RSI'] < 30: score += 2; details.append("💎 RSI 低於 30 (進入超跌)")
    
    return score, details

# --- 4. 側邊欄與介面 ---
st.sidebar.header("📊 投資參數設定")
ticker_input = st.sidebar.text_input("股票代碼", "2330.TW").upper()
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

df = load_and_process_data(ticker_input, start_date, end_date)

if df is not None:
    total_score, score_details = get_score(df)
    curr = df.iloc[-1]
    curr_p = float(curr['Close'])
    
    st.title(f"📈 {ticker_input} 技術指標看板")
    
    # 第一層：即時指標彙整
    m1, m2, m3, m4 = st.columns(4)
    price_change = curr_p - df['Close'].iloc[-2]
    m1.metric("目前股價", f"{curr_p:.2f}", f"{price_change:+.2f}")
    m2.metric("綜合戰鬥力", f"{total_score} 分", "看多" if total_score > 0 else "看空")
    m3.metric("RSI(14)", f"{curr['RSI']:.1f}")
    m4.metric("成交量", f"{int(curr['Volume']):,}")

    st.markdown("---")

    # 第二層：進出建議 (動態計算)
    entry_p = curr['EMA10']
    tp_p = curr['BBU']
    sl_p = min(curr['BBL'], curr['EMA20'] * 0.97)
    dist = (curr_p / entry_p) - 1

    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(f'<div class="price-box">🟢 <b>進場基準 (EMA10)</b><br><h2>{entry_p:.2f}</h2><p>與現價乖離: {dist:+.2%}</p></div>', unsafe_allow_html=True)
    with p2:
        st.markdown(f'<div class="price-box">🔴 <b>目標位 (布林上軌)</b><br><h2>{tp_p:.2f}</h2><p>潛在獲利: {((tp_p/curr_p)-1):+.2%}</p></div>', unsafe_allow_html=True)
    with p3:
        st.markdown(f'<div class="price-box">⚠️ <b>止損位 (月線/下軌)</b><br><h2>{sl_p:.2f}</h2><p>最大風險: {((sl_p/curr_p)-1):+.2%}</p></div>', unsafe_allow_html=True)

    # 第三層：視覺化圖表 (新增成交量層)
    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=True, 
        vertical_spacing=0.02, 
        row_heights=[0.4, 0.1, 0.15, 0.15, 0.2]
    )

    # 主圖：K線 + 均線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='#00ff88', width=1.5), name="EMA10"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='#ffaa00', width=1.5), name="EMA20"), row=1, col=1)
    
    # 成交量
    vol_colors = ['red' if df['Open'].iloc[i] > df['Close'].iloc[i] else 'green' for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="成交量", marker_color=vol_colors, opacity=0.5), row=2, col=1)

    # MACD
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD柱', marker_color=['#26A69A' if x > 0 else '#EF5350' for x in df['MACD_H']]), row=3, col=1)
    
    # KD
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1), name='K'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1), name='D'), row=4, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1.5), name='RSI'), row=5, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=5, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=5, col=1)

    fig.update_layout(height=1000, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=50, r=50, t=30, b=30))
    st.plotly_chart(fig, use_container_width=True)

    # 第四層：戰術分析
    st.markdown("---")
    r1, r2 = st.columns([1, 1])
    with r1:
        st.subheader("🔍 指導診斷")
        for d in score_details:
            st.write(d)
    with r2:
        st.subheader("💡 交易戰術")
        if abs(dist) < 0.02:
            st.success("🎯 **現價接近支撐**：股價正位於 EMA10 附近，若評分為正，進場風險回報比極佳。")
        elif dist > 0.05:
            st.warning("⌛ **過度乖離**：股價遠離 EMA10，短線可能回撤，不建議追高。")
        else:
            st.info("👀 **觀察等待**：目前位置中性，等待股價與 EMA10 重新匯合。")

else:
    st.error("無法讀取數據，請檢查代碼 (例如台股需加 .TW) 或日期範圍是否正確。")
