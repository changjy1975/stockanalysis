import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="專業級全指標技術分析看板", layout="wide")

# 自定義 CSS 讓介面更專業
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄參數 ---
st.sidebar.header("📊 查詢參數")
ticker = st.sidebar.text_input("輸入股票代碼 (台股請加 .TW)", "2330.TW")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

# --- 3. 數據抓取與計算核心 ---
@st.cache_data
def load_and_process_data(symbol, start, end):
    # 下載數據
    data = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if data.empty or len(data) < 40:
        return None
    
    # 處理 MultiIndex 欄位問題
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    df = data.copy()
    
    # 計算技術指標
    # 布林通道 (Bollinger Bands)
    bbands = ta.bbands(df['Close'], length=20, std=2)
    df = pd.concat([df, bbands], axis=1)
    # 欄位統一命名
    df.rename(columns={'BBL_20_2.0': 'BBL', 'BBM_20_2.0': 'BBM', 'BBU_20_2.0': 'BBU'}, inplace=True)

    # 均線 (SMA & EMA)
    df['MA20'] = ta.sma(df['Close'], length=20)
    df['MA60'] = ta.sma(df['Close'], length=60)
    df['EMA10'] = ta.ema(df['Close'], length=10)
    df['EMA20'] = ta.ema(df['Close'], length=20)

    # MACD
    macd = ta.macd(df['Close'])
    df['MACD'] = macd.iloc[:, 0]
    df['MACD_H'] = macd.iloc[:, 1]
    df['MACD_S'] = macd.iloc[:, 2]

    # KD (Stochastic)
    kd = ta.stoch(df['High'], df['Low'], df['Close'])
    df['K'] = kd.iloc[:, 0]
    df['D'] = kd.iloc[:, 1]

    # RSI
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    return df

# --- 4. 精準加權評分系統邏輯 ---
def calculate_advanced_score(df):
    score = 0
    details = []
    curr = df.iloc[-1]
    
    # A. 趨勢類 (權重 40%)
    if curr['Close'] > curr['EMA10'] > curr['EMA20']:
        score += 4
        details.append("均線多頭排列：強勢上升趨勢 (+4)")
    elif curr['Close'] > curr['EMA20']:
        score += 2
        details.append("股價位於 EMA20 支撐上方 (+2)")
    else:
        score -= 3
        details.append("股價跌破關鍵均線：趨勢偏弱 (-3)")

    # B. 動能類 (權重 40%)
    # MACD
    if curr['MACD_H'] > 0:
        score += 2
        details.append("MACD 柱狀體位於零軸上方：動能偏多 (+2)")
    else:
        score -= 2
        details.append("MACD 柱狀體位於零軸下方：動能偏空 (-2)")
    # KD
    if curr['K'] > curr['D']:
        score += 2
        details.append("KD 呈金叉狀態：短線具進攻動能 (+2)")
    else:
        score -= 2
        details.append("KD 呈死叉狀態：短線力道減弱 (-2)")

    # C. 位階/風險類 (權重 20%)
    if curr['Close'] > curr['BBU'] or curr['RSI'] > 75:
        score -= 2
        details.append("股價觸及布林上軌或 RSI 過熱：注意追高風險 (-2)")
    elif curr['Close'] < curr['BBL'] or curr['RSI'] < 25:
        score += 2
        details.append("股價跌破布林下軌或 RSI 超跌：具反彈契機 (+2)")
    
    return score, details

# --- 5. 主程式流程 ---
try:
    df = load_and_process_data(ticker, start_date, end_date)

    if df is None:
        st.title("📈 股票技術分析看板")
        st.error("數據不足或代碼錯誤。請確保日期範圍足夠長 (至少40天)，並檢查代碼是否正確。")
    else:
        # 計算分數
        total_score, score_details = calculate_advanced_score(df)
        
        # 顯示標題
        st.title(f"📈 {ticker} 專業技術看板")

        # --- 第一層：儀表板摘要 ---
        curr_p = df['Close'].iloc[-1]
        prev_p = df['Close'].iloc[-2]
        diff = curr_p - prev_p
        perc = (diff / prev_p) * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新股價", f"{curr_p:.2f}", f"{diff:+.2f} ({perc:+.2f}%)")
        
        # 評分視覺化
        if total_score >= 5: score_label, score_color = "🟢 強力看多", "success"
        elif 0 < total_score < 5: score_label, score_color = "🔵 偏多看待", "info"
        elif -5 < total_score <= 0: score_label, score_color = "🟡 中性偏空", "warning"
        else: score_label, score_color = "🔴 強力看空", "error"
        
        c2.metric("綜合評分", f"{total_score} 分", score_label)
        c3.metric("RSI (14)", f"{df['RSI'].iloc[-1]:.1f}")
        c4.metric("布林位置", "超漲" if curr_p > df['BBU'].iloc[-1] else ("超跌" if curr_p < df['BBL'].iloc[-1] else "常態"))

        st.markdown("---")

        # --- 第二層：多層整合圖表 ---
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, 
            row_heights=[0.5, 0.15, 0.15, 0.2]
        )

        # 1. K線 + 布林 + 均線
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        # 布林通道填充
        fig.add_trace(go.Scatter(x=df.index, y=df['BBL'], line=dict(color='rgba(173, 216, 230, 0.2)', width=1), name='布林下軌'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BBU'], line=dict(color='rgba(173, 216, 230, 0.2)', width=1), name='布林上軌', fill='tonexty', fillcolor='rgba(173, 216, 230, 0.05)'), row=1, col=1)
        # 均線
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1.5), name='SMA20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='lightgreen', width=1, dash='dot'), name='EMA10'), row=1, col=1)

        # 2. MACD
        colors = ['#26A69A' if x > 0 else '#EF5350' for x in df['MACD_H']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD柱狀', marker_color=colors), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='white', width=1), name='MACD線'), row=2, col=1)

        # 3. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1.2), name='K值'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1.2), name='D值'), row=3, col=1)

        # 4. RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1.2), name='RSI'), row=4, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

        fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

        # --- 第三層：AI 分析報告區 ---
        col_info, col_detail = st.columns([1.5, 1])
        
        with col_info:
            st.subheader("🔍 AI 技術面解析報告")
            report_text = "\n\n".join([f"• {d}" for d in score_details])
            if total_score >= 5: st.success(report_text)
            elif 0 < total_score < 5: st.info(report_text)
            elif -5 < total_score <= 0: st.warning(report_text)
            else: st.error(report_text)

        with col_detail:
            st.subheader("💡 交易策略建議")
            if total_score >= 5:
                st.write("目前趨勢極強且動能配合，適合持股待漲。若股價回測 EMA10 不破，可考慮作為加碼點。")
            elif total_score <= -5:
                st.write("空頭趨勢強烈且動能向下，應保守看待，先行觀望，直到股價重新站上布林中軌或 KD 低檔金叉。")
            else:
                st.write("當前處於震盪區間，建議參考布林通道上下軌進行區間操作，或等待明顯的指標突破訊號。")

        # --- 底部歷史數據 ---
        with st.expander("查看原始數據明細"):
            st.dataframe(df.sort_index(ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
