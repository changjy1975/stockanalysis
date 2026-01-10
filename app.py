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

        # --- 數據摘要 ---
        st.subheader("最新盤後摘要")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("價格", f"{df['Close'].iloc[-1]:.2f}")
        c2.metric("RSI(14)", f"{df['RSI'].iloc[-1]:.2f}")
        
        k_val = df['K'].iloc[-1]
        d_val = df['D'].iloc[-1]
        c3.metric("KD狀態", f"{'黃金交叉' if k_val > d_val else '死亡交叉'}", f"K:{k_val:.1f}")
        
        macdh = df['MACD_H'].iloc[-1]
        c4.metric("MACD動能", f"{'多頭' if macdh > 0 else '空頭'}", f"{macdh:.2f}")

except Exception as e:
    st.error(f"分析失敗: {e}")
