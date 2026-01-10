import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 網頁設定 ---
st.set_page_config(page_title="全方位股票分析系統", layout="wide")
st.title("📊 專業級全指標技術看板")

# --- 側邊欄設定 ---
st.sidebar.header("查詢參數")
ticker = st.sidebar.text_input("輸入股票代碼", "2330.TW")
start_date = st.sidebar.date_input("開始日期", datetime.now() - timedelta(days=365))
end_date = st.sidebar.date_input("結束日期", datetime.now())

# --- 數據抓取 ---
@st.cache_data
def load_data(symbol, start, end):
    data = yf.download(symbol, start=start, end=end, auto_adjust=True)
    if data.empty: return data
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

try:
    df = load_data(ticker, start_date, end_date)

    if df.empty or len(df) < 40:
        st.error("數據不足，請增加日期範圍。")
    else:
        # --- 1. 計算所有技術指標 ---
        # MA
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA60'] = ta.sma(df['Close'], length=60)
        
        # MACD
        macd = ta.macd(df['Close'])
        df['MACD'] = macd.iloc[:, 0]
        df['MACD_H'] = macd.iloc[:, 1]
        df['MACD_S'] = macd.iloc[:, 2]
        
        # KD
        kd = ta.stoch(df['High'], df['Low'], df['Close'])
        df['K'] = kd.iloc[:, 0]
        df['D'] = kd.iloc[:, 1]
        
        # RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)

        # --- 2. 建立多層子圖 ---
        # 設定 4 列，高度比例分別為 4:1.5:1.5:1 (K線最寬)
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, 
            row_heights=[0.5, 0.2, 0.2, 0.1]
        )

        # --- 第一層：K線與均線 ---
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name="K線"
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='deepskyblue', width=1), name='MA60'), row=1, col=1)

        # --- 第二層：MACD ---
        colors = ['red' if x < 0 else 'green' for x in df['MACD_H']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD柱狀', marker_color=colors), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='white', width=1), name='MACD線'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_S'], line=dict(color='yellow', width=1), name='訊號線'), row=2, col=1)

        # --- 第三層：KD ---
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1.2), name='K值'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1.2), name='D值'), row=3, col=1)
        # 加入 20, 80 基準線
        fig.add_hline(y=80, line_dash="dash", line_color="rgba(255,0,0,0.5)", row=3, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="rgba(0,255,0,0.5)", row=3, col=1)

        # --- 第四層：RSI ---
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1), name='RSI'), row=4, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

        # --- 圖表佈局設定 ---
        fig.update_layout(
            height=900,  # 設定總高度
            template="plotly_dark",
            title_text=f"{ticker} 綜合技術分析",
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=80, b=50)
        )
        
        # 隱藏中間子圖的 X 軸標籤，只保留最下方
        fig.update_xaxes(showticklabels=False, row=1, col=1)
        fig.update_xaxes(showticklabels=False, row=2, col=1)
        fig.update_xaxes(showticklabels=False, row=3, col=1)

        # 顯示圖表
        st.plotly_chart(fig, use_container_width=True)

       # --- 4. 策略建議引擎 ---
        st.divider()
        st.header("🤖 技術面操作建議 (未來三個月展望)")

        # 提取最新數據
        last_close = df['Close'].iloc[-1]
        ma20_now = df['MA20'].iloc[-1]
        ma60_now = df['MA60'].iloc[-1]
        k_now = df['K'].iloc[-1]
        d_now = df['D'].iloc[-1]
        macd_h_now = df['MACD_H'].iloc[-1]
        rsi_now = df['RSI'].iloc[-1]

        # 判斷趨勢
        if last_close > ma20_now > ma60_now:
            trend = "強勢多頭"
            trend_color = "green"
        elif last_close < ma20_now < ma60_now:
            trend = "弱勢空頭"
            trend_color = "red"
        else:
            trend = "震盪整理"
            trend_color = "orange"

        # 策略生成
        suggestion = ""
        action = "觀望"
        
        if trend == "強勢多頭":
            if k_now < 40:
                action = "逢低佈局"
                suggestion = "目前處於上升趨勢中的回檔，若 KD 出現金叉可考慮分批進場。"
            elif rsi_now > 75:
                action = "不宜追高"
                suggestion = "股價處於超買區，短期乖離率過大，建議等待拉回均線再行考慮。"
            else:
                action = "持股續抱"
                suggestion = "均線多頭排列，MACD 動能尚存，建議續抱並以 MA20 作為停損點。"
        
        elif trend == "弱勢空頭":
            if rsi_now < 25:
                action = "跌深反彈準備"
                suggestion = "目前極度超跌，隨時可能有技術性反彈，但不建議長線攤平。"
            else:
                action = "減碼/空手"
                suggestion = "趨勢向下，建議避開，待股價重新站上 MA60 且均線走平後再觀察。"
        
        else:
            action = "區間操作"
            suggestion = "目前方向不明朗，建議在區間高低點附近進行短線來回，或靜待帶量突破。"

        # 顯示建議卡片
        col_s1, col_s2 = st.columns([1, 3])
        with col_s1:
            st.markdown(f"### 建議行動：\n## :{trend_color}[{action}]")
        with col_s2:
            st.write(f"**當前趨勢評估：** {trend}")
            st.write(f"**詳細分析：** {suggestion}")

        # 未來三個月風險提示
        with st.expander("📌 未來三個月觀測重點"):
            st.write(f"""
            1. **支撐位觀測**：目前下方的強力支撐位約在 {df['Low'].tail(60).min():.2f} (三個月低點)。
            2. **壓力位觀測**：上方的反壓區約在 {df['High'].tail(60).max():.2f} (三個月高點)。
            3. **量能變化**：需注意未來是否出現倍量紅棒，這通常是波段起漲訊號。
            4. **總經影響**：建議同步關注聯準會 (Fed) 利率決策與相關產業財報發布。
            """)

        st.caption("⚠️ 免責聲明：本建議僅基於技術指標之邏輯運算，不代表未來必然走勢。投資有風險，操作前請謹慎評估。")
