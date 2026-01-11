import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 1. 網頁設定 ---
st.set_page_config(page_title="專業級全指標技術分析看板", layout="wide")

# 自定義 CSS 優化深色模式下的閱讀體驗
st.markdown("""
    <style>
    .report-box {
        padding: 20px;
        border-radius: 10px;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    .stMetric { background-color: #1e2130; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 側邊欄參數 ---
st.sidebar.header("📊 查詢參數")
ticker = st.sidebar.text_input("輸入股票代碼 (台股請加 .TW)", "2330.TW")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

# --- 3. 數據抓取與計算核心 (確保穩健性) ---
@st.cache_data
def load_and_process_data(symbol, start, end):
    try:
        data = yf.download(symbol, start=start, end=end, auto_adjust=True)
        if data.empty or len(data) < 40:
            return None
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        
        df = data.copy()
        
        # 布林通道 (使用 iloc 避免欄位名稱解析錯誤)
        bbands = ta.bbands(df['Close'], length=20, std=2)
        if bbands is not None:
            df['BBL'] = bbands.iloc[:, 0]
            df['BBM'] = bbands.iloc[:, 1]
            df['BBU'] = bbands.iloc[:, 2]

        # 均線指標
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['EMA10'] = ta.ema(df['Close'], length=10)
        df['EMA20'] = ta.ema(df['Close'], length=20)

        # MACD
        macd = ta.macd(df['Close'])
        if macd is not None:
            df['MACD'] = macd.iloc[:, 0]
            df['MACD_H'] = macd.iloc[:, 1]
            df['MACD_S'] = macd.iloc[:, 2]

        # KD
        kd = ta.stoch(df['High'], df['Low'], df['Close'])
        if kd is not None:
            df['K'] = kd.iloc[:, 0]
            df['D'] = kd.iloc[:, 1]

        # RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        return df.dropna(subset=['BBU', 'MACD', 'K', 'RSI'])
    except Exception as e:
        st.error(f"數據讀取失敗: {e}")
        return None

# --- 4. 精準加權評分系統 ---
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
    if curr['MACD_H'] > 0:
        score += 2
        details.append("MACD 柱狀體位於零軸上方 (+2)")
    else:
        score -= 2
        details.append("MACD 柱狀體位於零軸下方 (-2)")
        
    if curr['K'] > curr['D']:
        score += 2
        details.append("KD 呈金叉狀態 (+2)")
    else:
        score -= 2
        details.append("KD 呈死叉狀態 (-2)")

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

    if df is None or len(df) == 0:
        st.title("📈 專業技術分析看板")
        st.warning("數據獲取中或查無資料，請確認代碼格式。")
    else:
        # 計算多空分數
        total_score, score_details = calculate_advanced_score(df)
        
        # 標題與即時摘要
        st.title(f"📈 {ticker} 專業技術分析看板")
        
        curr_p = float(df['Close'].iloc[-1])
        prev_p = float(df['Close'].iloc[-2])
        diff = curr_p - prev_p
        perc = (diff / prev_p) * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("最新報價", f"{curr_p:.2f}", f"{diff:+.2f} ({perc:+.2f}%)")
        
        if total_score >= 5: score_label = "🟢 強力看多"
        elif 0 < total_score < 5: score_label = "🔵 偏多看待"
        elif -5 < total_score <= 0: score_label = "🟡 中性偏空"
        else: score_label = "🔴 強力看空"
        
        c2.metric("多空綜合評分", f"{total_score} 分", score_label)
        c3.metric("RSI (14)", f"{df['RSI'].iloc[-1]:.1f}")
        c4.metric("布林位置", "超漲" if curr_p > df['BBU'].iloc[-1] else ("超跌" if curr_p < df['BBL'].iloc[-1] else "震盪區間"))

        st.markdown("---")

        # --- 第一部分：專業技術圖表 ---
        st.subheader("📊 專業技術看板")
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, 
            row_heights=[0.5, 0.15, 0.15, 0.2]
        )

        # 1. 主圖：K線 + 布林 + 均線
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BBL'], line=dict(color='rgba(173, 216, 230, 0.2)', width=1), name='布林下軌'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BBU'], line=dict(color='rgba(173, 216, 230, 0.2)', width=1), name='布林上軌', fill='tonexty', fillcolor='rgba(173, 216, 230, 0.05)'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1.5), name='SMA20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], line=dict(color='lightgreen', width=1, dash='dot'), name='EMA10'), row=1, col=1)

        # 2. MACD
        colors = ['#26A69A' if x > 0 else '#EF5350' for x in df['MACD_H']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD柱', marker_color=colors), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='white', width=1), name='MACD'), row=2, col=1)

        # 3. KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1.2), name='K值'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1.2), name='D值'), row=3, col=1)

        # 4. RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1.2), name='RSI'), row=4, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- 第二部分：分析報告與策略建議 (圖表下方) ---
        st.subheader("📑 深度分析與決策建議")
        
        col_report, col_strat = st.columns([1.5, 1])
        
        with col_report:
            st.markdown("#### 🔍 AI 技術面解析")
            report_text = "\n\n".join([f"**{i+1}.** {d}" for i, d in enumerate(score_details)])
            
            # 根據分數動態調整報告背景色
            if total_score >= 5:
                st.success(report_text)
            elif 0 < total_score < 5:
                st.info(report_text)
            elif -5 < total_score <= 0:
                st.warning(report_text)
            else:
                st.error(report_text)

        with col_strat:
            st.markdown("#### 💡 交易策略參考")
            if total_score >= 5:
                st.markdown("""
                - **操作心法**：目前處於強烈攻擊態勢。
                - **進場建議**：可順勢持股，或待回測 EMA10 不破時小量加碼。
                - **風險控制**：以 SMA20 或布林中軌作為移動止盈位。
                """)
            elif total_score <= -5:
                st.markdown("""
                - **操作心法**：空方力道強勁，切勿盲目攤平。
                - **建議動作**：保持觀望或先行減碼。
                - **觀察重點**：等待股價站回布林中軌，或 KD 在低檔出現黃金交叉。
                """)
            else:
                st.markdown("""
                - **操作心法**：方向不明確，適合區間操作。
                - **建議動作**：在布林通道下軌附近尋求支撐買點，上軌附近尋求壓力賣點。
                - **提醒**：若指標出現交叉（如 MACD 翻紅），則是轉強訊號。
                """)

        # 底部數據表
        with st.expander("📊 查看歷史數據明細 (含技術指標)"):
            st.dataframe(df.sort_index(ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"系統運行錯誤: {e}")
