import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="專業級全指標技術看板 (EMA10進場版)", layout="wide")

# 自定義 CSS
st.markdown("""
    <style>
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; }
    .price-box { border: 1px solid #4B5563; padding: 15px; border-radius: 10px; background-color: #111827; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄設定 ---
st.sidebar.header("📊 查詢參數")
ticker_input = st.sidebar.text_input("輸入股票代碼", "2330.TW").upper()
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

st.sidebar.info("💡 **提示**：上市加 `.TW`，上櫃加 `.TWO` (如: 6147.TWO)")

# --- 3. 數據抓取與計算 ---
@st.cache_data
def load_and_process_data(symbol, start, end):
    try:
        data = yf.download(symbol, start=start, end=end, auto_adjust=True)
        if data.empty or len(data) < 40: return None
        if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
        
        df = data.copy()
        # 布林通道 (使用 iloc 避免名稱解析報錯)
        bbands = ta.bbands(df['Close'], length=20, std=2)
        df['BBL'], df['BBM'], df['BBU'] = bbands.iloc[:, 0], bbands.iloc[:, 1], bbands.iloc[:, 2]
        
        # 均線
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA60'] = ta.sma(df['Close'], length=60)
        df['EMA10'] = ta.ema(df['Close'], length=10)
        df['EMA20'] = ta.ema(df['Close'], length=20)
        
        # MACD
        macd = ta.macd(df['Close'])
        df['MACD'], df['MACD_H'], df['MACD_S'] = macd.iloc[:, 0], macd.iloc[:, 1], macd.iloc[:, 2]
        
        # KD
        kd = ta.stoch(df['High'], df['Low'], df['Close'])
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        
        # RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        return df.dropna()
    except: return None

# --- 4. 評分邏輯 (加權演算法) ---
def get_score(df):
    score = 0
    details = []
    curr = df.iloc[-1]
    
    # 趨勢判斷
    if curr['Close'] > curr['EMA10'] > curr['EMA20']:
        score += 4; details.append("均線多頭排列：強勢攻擊 (+4)")
    elif curr['Close'] > curr['EMA20']:
        score += 2; details.append("趨勢偏多：守住月線 (+2)")
    else: 
        score -= 3; details.append("趨勢疲軟：低於月線 (-3)")
    
    # 動能判斷
    if curr['MACD_H'] > 0: score += 2; details.append("MACD 柱狀體翻紅 (+2)")
    else: score -= 2; details.append("MACD 柱狀體翻綠 (-2)")
        
    if curr['K'] > curr['D']: score += 2; details.append("KD 金叉向上 (+2)")
    else: score -= 2; details.append("KD 死叉向下 (-2)")
    
    # 位階判斷
    if curr['RSI'] > 75: score -= 2; details.append("RSI 進入超買區 (-2)")
    elif curr['RSI'] < 25: score += 2; details.append("RSI 進入超跌區 (+2)")
    
    return score, details

# --- 5. 主程式流程 ---
df = load_and_process_data(ticker_input, start_date, end_date)

if df is None:
    st.error("查無數據，請確認代碼格式與日期範圍。")
else:
    total_score, score_details = get_score(df)
    curr = df.iloc[-1]
    curr_p = float(curr['Close'])

    st.title(f"📈 {ticker_input} 專業全指標技術看板")

    # 第一層：即時數據摘要
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("目前股價", f"{curr_p:.2f}", f"{(curr_p - df['Close'].iloc[-2]):+.2f}")
    c2.metric("綜合評分", f"{total_score} 分", "看多" if total_score > 0 else "看空")
    c3.metric("RSI(14)", f"{curr['RSI']:.1f}")
    c4.metric("EMA10 (進場基準)", f"{curr['EMA10']:.2f}")

    st.markdown("---")

    # 第二層：進出價位建議 (動態 EMA10 邏輯)
    st.subheader("🎯 實戰進出建議位 (基於 EMA10 短線趨勢)")
    
    entry_p = curr['EMA10']         # 以 EMA10 為進場基準
    tp_p = curr['BBU']              # 止盈參考布林上軌
    sl_p = min(curr['BBL'], curr['EMA20'] * 0.97) # 止損參考布林下軌或 EMA20 破位
    dist = (curr_p / entry_p) - 1   # 計算與 EMA10 的乖離率

    p1, p2, p3 = st.columns(3)
    p1.markdown(f'<div class="price-box">🟢 <b>建議進場點</b><br><h2>{entry_p:.2f}</h2><p>參考 EMA10 支撐 (偏離 {dist:+.2%})</p></div>', unsafe_allow_html=True)
    p2.markdown(f'<div class="price-box">🔴 <b>短線止盈位</b><br><h2>{tp_p:.2f}</h2><p>參考布林上軌壓力</p></div>', unsafe_allow_html=True)
    p3.markdown(f'<div class="price-box">⚠️ <b>關鍵止損位</b><br><h2>{sl_p:.2f}</h2><p>參考布林下軌或破月線 3%</p></div>', unsafe_allow_html=True)

    st.markdown("---")

    # 第三層：專業技術指標圖表 (四層架構)
    st.subheader("📊 專業技術分析看板")
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, 
        vertical_spacing=0.03, row_heights=[0.5, 0.15, 0.15, 0.2]
    )

    # 1. 主圖：K線 + 布林 + 均線
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBL'], line=dict(color='rgba(255,255,255,0.1)'), name="布林下軌"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['BBU'], line=dict(color='rgba(255,255,255,0.1)'), name="布林上軌", fill='tonexty'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='lightgreen', width=1.5), name="EMA10 (進場線)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color='orange', width=1.5), name="EMA20 (月線)"), row=1, col=1)

    # 2. MACD
    colors = ['#26A69A' if x > 0 else '#EF5350' for x in df['MACD_H']]
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD柱', marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='white', width=1), name='MACD線'), row=2, col=1)

    # 3. KD
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1.2), name='K值'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1.2), name='D值'), row=3, col=1)

    # 4. RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1.2), name='RSI'), row=4, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

    fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # 第四層：AI 解析報告與戰術提示
    st.markdown("---")
    r1, r2 = st.columns([1.5, 1])
    with r1:
        st.subheader("🔍 AI 技術面解析報告")
        report = "\n\n".join([f"• {d}" for d in score_details])
        if total_score >= 5: st.success(report)
        elif total_score <= -5: st.error(report)
        else: st.info(report)
    with r2:
        st.subheader("💡 實戰戰術提醒")
        if abs(dist) < 0.015:
            st.write("✅ **時機成熟**：股價正貼近 EMA10 支撐，若多空評分為正，是強勢股良好的切入點。")
        elif dist > 0:
            st.write(f"⌛ **稍安勿躁**：目前股價高於 EMA10 約 **{dist:.1%}**，短線乖離已現，建議等回測 EMA10 再接。")
        else:
            st.write("⚠️ **注意風險**：股價已跌破 EMA10，請觀察是否能守住月線 (EMA20)，否則短線轉弱。")
