"""
Web Dashboard for NSE Trading Engine.
Run with: streamlit run web_app.py
"""

import streamlit as st
import pandas as pd
import asyncio
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
import json
import os
from dataclasses import asdict

from core.scanner import AsyncScanner, ScanResult

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="NSE Pro Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS STYLING (PROFESSIONAL LIGHT THEME) ---
st.markdown("""
<style>
    /* Global Clean White Theme */
    .stApp {
        background-color: #ffffff;
        color: #24292f;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #f6f8fa; /* Light Gray */
        border-right: 1px solid #d0d7de;
    }
    section[data-testid="stSidebar"] .stMarkdown h1, h2, h3, p {
        color: #24292f !important;
    }
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {
        color: #1f2328 !important;
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* Buttons */
    .stButton>button {
        width: 100%;
        background-color: #1f883d; /* GitHub Green */
        color: white;
        border: 1px solid rgba(27,31,36,0.15);
        border-radius: 6px;
        height: 45px;
        font-weight: 600;
        box-shadow: 0 1px 0 rgba(27,31,36,0.1);
        transition: 0.2s cubic-bezier(0.3, 0, 0.5, 1);
    }
    .stButton>button:hover {
        background-color: #1a7f37;
        border-color: rgba(27,31,36,0.15);
    }
    .stButton>button:active {
        background-color: #197834;
        box-shadow: inset 0 2px 0 rgba(27,31,36,0.1);
    }
    
    /* Sell Button Red Override */
    div[data-testid="stVerticalBlock"] > div > div > div > div > .sell-btn > button {
        background-color: #d73a49 !important; /* GitHub Red */
    }
    div[data-testid="stVerticalBlock"] > div > div > div > div > .sell-btn > button:hover {
        background-color: #cb2431 !important;
    }
    
    /* Metrics */
    div[data-testid="stMetricValue"] {
        color: #1f2328;
        font-weight: 700;
    }
    div[data-testid="stMetricLabel"] {
        color: #656d76;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #ffffff;
        border-bottom: 1px solid #d0d7de;
        padding-bottom: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        background-color: transparent;
        border-radius: 6px;
        color: #656d76;
        border: none;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #f3f4f6;
        color: #1f2328;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #f1f8ff;
        color: #0969da; /* Blue */
        font-weight: 600;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] p {
        color: #0969da;
    }

    /* Inputs & Selectboxes */
    .stTextInput>div>div>input {
        background-color: #ffffff;
        color: #1f2328;
        border: 1px solid #d0d7de;
        border-radius: 6px;
    }
    .stTextInput>div>div>input:focus {
        border-color: #0969da;
        box-shadow: 0 0 0 3px rgba(9,105,218,0.3);
    }
    .stSelectbox>div>div>div {
        background-color: #ffffff;
        color: #1f2328;
        border-color: #d0d7de;
    }
    
    /* Dataframes */
    div[data-testid="stDataFrame"] {
        border: 1px solid #d0d7de;
        border-radius: 6px;
    }
    
</style>
""", unsafe_allow_html=True)

# --- STATE MANAGEMENT ---
CACHE_FILE = "scan_cache.json"

def save_cache(results):
    """Save results to local JSON file."""
    try:
        data = [asdict(r) for r in results]
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass

def load_cache():
    """Load results from local JSON file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                return [ScanResult(**d) for d in data]
        except Exception:
            return []
    return []

if 'scanner' not in st.session_state:
    st.session_state.scanner = AsyncScanner()

if 'results' not in st.session_state:
    st.session_state.results = load_cache()

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["RELIANCE.NS", "TCS.NS", "NIFTY_50.NS", "INFY.NS", "HDFCBANK.NS"]

if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = "RELIANCE.NS"

# --- HELPER FUNCTIONS ---

def run_scan():
    """Run full async market scan."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def on_progress(completed, total):
        pct = min(completed / total, 1.0)
        progress_bar.progress(pct)
        status_text.text(f"Scanning... {completed}/{total}")
        
    try:
        results = loop.run_until_complete(st.session_state.scanner.scan_market(on_progress))
        st.session_state.results = results
        save_cache(results)
        st.success(f"Scan Complete! Found {len(results)} opportunities.")
    except Exception as e:
        st.error(f"Scan Failed: {e}")
    finally:
        loop.close()
        progress_bar.empty()
        status_text.empty()

def fast_refresh_quotes():
    """Optimized batch refresh for existing results."""
    if not st.session_state.results: return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    symbols = [r.symbol for r in st.session_state.results]
    
    try:
        updated = loop.run_until_complete(st.session_state.scanner.refresh_batch(symbols))
        updated.sort(key=lambda x: (x.signal != "NEUTRAL", abs(x.change_pct)), reverse=True)
        st.session_state.results = updated
        save_cache(updated)
    finally:
        loop.close()

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚡ NSE Terminal")
    st.markdown("---")
    
    st.markdown("### 📡 Scanner Control")
    if st.button("START FULL MARKET SCAN", type="primary"):
        with st.spinner("Scanning 2000+ stocks..."):
            run_scan()
            
    st.markdown("### ⏱️ Realtime Settings")
    auto_refresh = st.toggle("Auto-Refresh (Fast)", value=False)
    
    if auto_refresh:
        fast_refresh_quotes()
        import time
        time.sleep(5) 
        st.rerun()

    st.markdown("---")
    st.caption("System Ready | v2.4 Light Pro")

# --- MAIN LAYOUT ---
tab_scanner, tab_dashboard, tab_portfolio = st.tabs(["🚀 Live Scanner", "📊 Trading Dashboard", "💼 Portfolio"])

# ==========================================
# TAB 1: LIVE SCANNER (Enhanced)
# ==========================================
with tab_scanner:
    if st.session_state.results:
        df = pd.DataFrame([vars(r) for r in st.session_state.results])
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Active Stocks", len(df))
        m2.metric("Buy Signals", len(df[df['signal'].str.contains("BUY")]), delta_color="normal")
        m3.metric("Sell Signals", len(df[df['signal'].str.contains("SELL")]), delta_color="inverse")
        adv = len(df[df['change_pct'] > 0])
        dec = len(df[df['change_pct'] < 0])
        m4.metric("A/D Ratio", f"{adv}/{dec}")
        
        st.divider()
        
        col_f1, col_f2 = st.columns([3, 1])
        with col_f1:
            filter_sigs = st.multiselect("Filter Signals", 
                                       ["STRONG BUY", "BUY", "STRONG SELL", "SELL", "NEUTRAL"],
                                       default=["STRONG BUY", "BUY", "STRONG SELL", "SELL"])
        
        if filter_sigs:
            df = df[df['signal'].isin(filter_sigs)]
            
        st.dataframe(
            df[['symbol', 'signal', 'ltp', 'change_pct', 'confidence', 'target1', 'stop_loss', 'analysis']],
            use_container_width=True,
            column_config={
                "symbol": "Stock",
                "signal": "Signal",
                "ltp": st.column_config.NumberColumn("Price", format="₹%.2f"),
                "change_pct": st.column_config.NumberColumn("Change %", format="%.2f%%"),
                "confidence": st.column_config.ProgressColumn("Conf", min_value=0, max_value=100, format="%.0f%%"),
                "target1": st.column_config.NumberColumn("Target 1", format="₹%.2f"),
                "stop_loss": st.column_config.NumberColumn("Stop Loss", format="₹%.2f"),
            },
            height=600
        )
    else:
        st.info("No scan results. Click 'START FULL MARKET SCAN' in the sidebar.")

# ==========================================
# TAB 2: TRADING DASHBOARD (Replica of GUI)
# ==========================================
with tab_dashboard:
    col_watch, col_chart, col_action = st.columns([1.2, 3, 1])
    
    # --- LEFT: WATCHLIST ---
    with col_watch:
        st.markdown("### Market Watch")
        
        new_sym = st.text_input("Add Symbol", placeholder="e.g. MRF", label_visibility="collapsed")
        if new_sym:
            s = new_sym.upper()
            if not s.endswith(".NS"): s += ".NS"
            if s not in st.session_state.watchlist:
                st.session_state.watchlist.append(s)
                st.rerun()
        
        wl_data = []
        if st.session_state.watchlist:
            scan_map = {r.symbol: r for r in st.session_state.results} if st.session_state.results else {}
            
            for sym in st.session_state.watchlist:
                if sym in scan_map:
                    r = scan_map[sym]
                    wl_data.append({"Symbol": sym, "Price": r.ltp, "Change": r.change_pct})
                else:
                    wl_data.append({"Symbol": sym, "Price": 0.0, "Change": 0.0})
                    
        wl_df = pd.DataFrame(wl_data)
        
        event = st.dataframe(
            wl_df,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
            column_config={
                "Price": st.column_config.NumberColumn(format="₹%.2f"),
                "Change": st.column_config.NumberColumn(format="%.2f%%")
            }
        )
        
        try:
            if len(event.selection.rows) > 0:
                selected_row_idx = event.selection.rows[0]
                st.session_state.selected_symbol = wl_df.iloc[selected_row_idx]['Symbol']
        except:
            pass
            
    # --- MIDDLE: CHART (Light Theme) ---
    with col_chart:
        st.markdown(f"### 📈 {st.session_state.selected_symbol}")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            tf = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=4, label_visibility="collapsed")
        with c2:
            show_ema = st.checkbox("EMA 50/200", value=True)
        with c3:
            show_bb = st.checkbox("Bollinger", value=True)
        with c4:
            show_rsi = st.checkbox("RSI", value=True)
        
        if st.session_state.selected_symbol:
            try:
                tf_map = {"1m": "1d", "5m": "5d", "15m": "5d", "1h": "1mo", "1d": "1y"}
                period = tf_map.get(tf, "1y")
                
                df_chart = yf.Ticker(st.session_state.selected_symbol).history(period=period, interval=tf)
                
                if not df_chart.empty:
                    # --- INDICATOR CALCULATIONS ---
                    df_chart['EMA50'] = df_chart['Close'].ewm(span=50).mean()
                    df_chart['EMA200'] = df_chart['Close'].ewm(span=200).mean()
                    
                    # RSI
                    delta = df_chart['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    df_chart['RSI'] = 100 - (100 / (1 + rs))
                    
                    last_close = df_chart['Close'].iloc[-1]
                    prev_close = df_chart['Close'].iloc[-2]
                    ema50_val = df_chart['EMA50'].iloc[-1]
                    rsi_val = df_chart['RSI'].iloc[-1]
                    
                    # --- SIGNAL LOGIC ---
                    signal_text = "N/A"
                    signal_color = "#656d76" # Neutral Grey
                    
                    # Logic
                    if last_close > ema50_val:
                        if rsi_val < 35: 
                            signal_text = "STRONG BUY (Dip)"
                            signal_color = "#1f883d" # Green
                        elif last_close > prev_close * 1.005: 
                            signal_text = "BUY (Momentum)"
                            signal_color = "#1f883d"
                    elif last_close < ema50_val:
                        if rsi_val > 65:
                            signal_text = "STRONG SELL (Top)"
                            signal_color = "#d73a49" # Red
                        elif last_close < prev_close * 0.995:
                            signal_text = "SELL (Momentum)"
                            signal_color = "#d73a49"

                    # --- PLOTTING ---
                    fig = go.Figure()
                    
                    # 1. Candlestick
                    fig.add_trace(go.Candlestick(x=df_chart.index,
                                    open=df_chart['Open'], high=df_chart['High'],
                                    low=df_chart['Low'], close=df_chart['Close'],
                                    name='Price'))
                    
                    # 2. Overlays
                    if show_ema:
                        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA50'], line=dict(color='#cf222e', width=1), name='EMA 50'))
                        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA200'], line=dict(color='#24292f', width=1), name='EMA 200'))
                        
                    if show_bb:
                        sma20 = df_chart['Close'].rolling(20).mean()
                        std20 = df_chart['Close'].rolling(20).std()
                        upper = sma20 + (std20 * 2)
                        lower = sma20 - (std20 * 2)
                        fig.add_trace(go.Scatter(x=df_chart.index, y=upper, line=dict(color='rgba(9, 105, 218, 0.4)'), showlegend=False))
                        fig.add_trace(go.Scatter(x=df_chart.index, y=lower, line=dict(color='rgba(9, 105, 218, 0.4)'), fill='tonexty', fillcolor='rgba(9, 105, 218, 0.1)', name='BB'))
                    
                    # 3. SIGNAL VISUALIZATION
                    if "BUY" in signal_text or "SELL" in signal_text:
                        volatility = df_chart['High'].iloc[-5:].max() - df_chart['Low'].iloc[-5:].min()
                        if volatility == 0: volatility = last_close * 0.01
                        
                        if "BUY" in signal_text:
                            sl = last_close - (volatility * 0.5)
                            t1 = last_close + volatility
                            t2 = last_close + (volatility * 2)
                            line_col = "#1f883d"
                        else:
                            sl = last_close + (volatility * 0.5)
                            t1 = last_close - volatility
                            t2 = last_close - (volatility * 2)
                            line_col = "#d73a49"
                        
                        # Big Text Annotation
                        fig.add_annotation(
                            xref="paper", yref="paper",
                            x=0.02, y=0.98,
                            text=f"<b>{signal_text}</b><br><span style='font-size:12px;color:#24292f'>LTP: {last_close:.2f} | RSI: {rsi_val:.1f}</span>",
                            showarrow=False,
                            font=dict(size=24, color=line_col),
                            align="left",
                            bgcolor="rgba(255,255,255,0.8)",
                            bordercolor=line_col,
                            borderwidth=1,
                            borderpad=10
                        )
                            
                        # Dotted Levels
                        fig.add_hline(y=t1, line_dash="dash", line_color=line_col, annotation_text=f"T1: {t1:.2f}", annotation_position="top right", annotation_font_color=line_col)
                        fig.add_hline(y=t2, line_dash="dash", line_color=line_col, annotation_text=f"T2: {t2:.2f}", annotation_position="top right", annotation_font_color=line_col)
                        fig.add_hline(y=sl, line_dash="dash", line_color="#d73a49", annotation_text=f"SL: {sl:.2f}", annotation_position="bottom right", annotation_font_color="#d73a49")

                    fig.update_layout(
                        height=550, 
                        template="plotly_white", # Light theme
                        xaxis_rangeslider_visible=False,
                        margin=dict(l=0, r=0, t=0, b=0),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        legend=dict(orientation="h", y=1.02, x=0.8, bgcolor='rgba(255,255,255,0.7)'),
                        font=dict(color="#24292f")
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # RSI Subplot
                    if show_rsi:
                        fig_rsi = go.Figure()
                        fig_rsi.add_trace(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='#8250df')))
                        fig_rsi.add_hline(y=70, line_dash="dot", line_color="#d73a49")
                        fig_rsi.add_hline(y=30, line_dash="dot", line_color="#1f883d")
                        fig_rsi.update_layout(
                            height=150, 
                            template="plotly_white", 
                            margin=dict(l=0,r=0,t=0,b=0), 
                            yaxis=dict(range=[0,100]),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color="#24292f")
                        )
                        st.plotly_chart(fig_rsi, use_container_width=True)
                        
            except Exception as e:
                st.error(f"Chart Error: {e}")

    # --- RIGHT: TRADE PANEL ---
    with col_action:
        st.markdown("### ⚡ Quick Trade")
        
        current_price = 0.0
        if not df_chart.empty:
            current_price = df_chart['Close'].iloc[-1]
            
        st.metric("LTP", f"₹{current_price:.2f}")
        
        st.markdown("**Order Details**")
        qty = st.number_input("Quantity", min_value=1, value=10)
        
        st.markdown("")
        if st.button("🔼 BUY NOW", key="btn_buy"):
            st.toast(f"Limit BUY Order: {qty} @ Market", icon="✅")
            
        st.markdown("")
        st.markdown('<div class="sell-btn">', unsafe_allow_html=True)
        if st.button("🔽 SELL NOW", key="btn_sell"):
            st.toast(f"Limit SELL Order: {qty} @ Market", icon="🔻")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.divider()
        st.caption("Active Account: DEMO-USER")
        st.caption("Margin Available: ₹1,00,000")

# ==========================================
# TAB 3: PORTFOLIO
# ==========================================
with tab_portfolio:
    st.markdown("### My Portfolio")
    data = {
        "Symbol": ["INFY.NS", "TCS.NS"],
        "Qty": [10, 5],
        "Avg Price": [1400.0, 3200.0],
        "LTP": [1420.0, 3180.0],
        "P&L": [200.0, -100.0]
    }
    st.dataframe(pd.DataFrame(data), use_container_width=True)
