import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- 網頁設定 ---
st.set_page_config(page_title="專業級全指標技術看板", layout="wide")

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
        st.title("📈 股票技術分析看板")
        st.error("數據不足，請在左側增加日期範圍或檢查代碼是否正確。")
    else:
        # --- 1. 計算所有技術指標 (邏輯必須先執行) ---
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA60'] = ta.sma(df['Close'], length=60)
        
        macd = ta.macd(df['Close'])
        df['MACD'] = macd.iloc[:, 0]
        df['MACD_H'] = macd.iloc[:, 1]
        df['MACD_S'] = macd.iloc[:, 2]
        
        kd = ta.stoch(df['High'], df['Low'], df['Close'])
        df['K'] = kd.iloc[:, 0]
        df['D'] = kd.iloc[:, 1]
        
        df['RSI'] = ta.rsi(df['Close'], length=14)

        # --- 2. 顯示標題與最新盤後摘要 (移到上方) ---
        st.title(f"📈 {ticker} 技術分析看板")
        
        # 獲取最新數據與變化
        curr_p = float(df['Close'].iloc[-1])
        prev_p = float(df['Close'].iloc[-2])
        price_diff = curr_p - prev_p
        price_perc = (price_diff / prev_p) * 100
        
        k_val = df['K'].iloc[-1]
        d_val = df['D'].iloc[-1]
        macdh = df['MACD_H'].iloc[-1]
        rsi_val = df['RSI'].iloc[-1]

        # 使用 Container 製作漂亮的摘要列
        with st.container():
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("最新股價", f"{curr_p:.2f}", f"{price_diff:+.2f} ({price_perc:+.2f}%)")
            c2.metric("RSI(14) 強弱", f"{rsi_val:.1f}", "超買(>70)" if rsi_val > 70 else ("超賣(<30)" if rsi_val < 30 else "中性"))
            
            # KD 狀態判斷
            kd_status = "黃金交叉" if k_val > d_val else "死亡交叉"
            kd_color = "normal" if k_val > d_val else "inverse"
            c3.metric("KD 狀態", kd_status, f"K:{k_val:.1f} / D:{d_val:.1f}")
            
            # MACD 狀態判斷
            macd_status = "多頭動能" if macdh > 0 else "空頭動能"
            c4.metric("MACD 動能", macd_status, f"{macdh:.2f}")
            
            # 均線狀態
            ma_status = "多頭排列" if curr_p > df['MA20'].iloc[-1] > df['MA60'].iloc[-1] else "非多頭排列"
            c5.metric("均線趨勢", ma_status)
        
        st.markdown("---") # 分割線

        # --- 3. 建立多層整合圖表 ---
        fig = make_subplots(
            rows=4, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, 
            row_heights=[0.5, 0.2, 0.2, 0.1]
        )

        # 第一層：K線與均線
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], 
            low=df['Low'], close=df['Close'], name="K線"
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1.2), name='MA20'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], line=dict(color='deepskyblue', width=1.2), name='MA60'), row=1, col=1)

        # 第二層：MACD
        colors = ['#26A69A' if x > 0 else '#EF5350' for x in df['MACD_H']]
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_H'], name='MACD柱狀', marker_color=colors), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='white', width=1), name='MACD線'), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_S'], line=dict(color='yellow', width=1), name='訊號線'), row=2, col=1)

        # 第三層：KD
        fig.add_trace(go.Scatter(x=df.index, y=df['K'], line=dict(color='cyan', width=1.2), name='K值'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['D'], line=dict(color='magenta', width=1.2), name='D值'), row=3, col=1)
        fig.add_hline(y=80, line_dash="dash", line_color="rgba(255,0,0,0.5)", row=3, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="rgba(0,255,0,0.5)", row=3, col=1)

        # 第四層：RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='gold', width=1), name='RSI'), row=4, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)

        fig.update_layout(
            height=850,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=10, r=10, t=20, b=10)
        )
        
        fig.update_xaxes(showticklabels=False, row=1, col=1)
        fig.update_xaxes(showticklabels=False, row=2, col=1)
        fig.update_xaxes(showticklabels=False, row=3, col=1)

        st.plotly_chart(fig, use_container_width=True)

        # --- 4. 底部歷史數據 ---
        with st.expander("查看歷史明細數據"):
            st.dataframe(df.sort_index(ascending=False), use_container_width=True)

except Exception as e:
    st.error(f"分析失敗: {e}")
