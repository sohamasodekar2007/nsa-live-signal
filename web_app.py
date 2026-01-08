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

from core.scanner import AsyncScanner, ScanResult

st.set_page_config(
    page_title="NSE Pro Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        background-color: #238636;
        color: white;
        border: none;
        height: 50px;
        font-weight: bold;
    }
    .big-font {
        font-size:20px !important;
    }
</style>
""", unsafe_allow_html=True)

# Application State
CACHE_FILE = "scan_cache.json"
import json
import os
from dataclasses import asdict

def save_cache(results):
    """Save results to local JSON file (Server-side persistence)."""
    try:
        data = [asdict(r) for r in results]
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        st.error(f"Cache Save Failed: {e}")

def load_cache():
    """Load results from local JSON file."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                # Reconstruct ScanResult objects
                return [ScanResult(**d) for d in data]
        except Exception:
            return []
    return []

if 'scanner' not in st.session_state:
    st.session_state.scanner = AsyncScanner()
    
# Load cache on first run if results empty
if 'results' not in st.session_state:
    cached = load_cache()
    if cached:
        st.session_state.results = cached
        st.toast(f"Restored {len(cached)} stocks from previous scan!", icon="🔄")
    else:
        st.session_state.results = []

def run_scan():
    """Run async scan in sync context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def on_progress(completed, total):
        pct = min(completed / total, 1.0)
        progress_bar.progress(pct)
        status_text.text(f"Scanning... {completed}/{total}")
        
    results = loop.run_until_complete(st.session_state.scanner.scan_market(on_progress))
    st.session_state.results = results
    
    # PERISTENCE: Save to cache
    save_cache(results)
    
    loop.close()
    
    status_text.text(f"Scan Complete! Found {len(results)} active stocks.")
    progress_bar.empty()

def update_quotes():
    """Quickly update prices of EXISTING results (Real-time mode)."""
    if not st.session_state.results: return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # We only re-scan the symbols we already found
    symbols = [r.symbol for r in st.session_state.results]
    
    # Sort
    valid_results.sort(key=lambda x: (x.signal != "NEUTRAL", abs(x.change_pct)), reverse=True)
    
    st.session_state.results = valid_results
    save_cache(valid_results)
    loop.close()

def update_quotes():
    """Quickly update prices of EXISTING results (Real-time mode)."""
    if not st.session_state.results: return
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # We only re-scan the symbols we already found
    symbols = [r.symbol for r in st.session_state.results]
    
    # Use the robust batch method
    updated_results = loop.run_until_complete(st.session_state.scanner.refresh_batch(symbols))
    
    # Sort
    updated_results.sort(key=lambda x: (x.signal != "NEUTRAL", abs(x.change_pct)), reverse=True)
    
    st.session_state.results = updated_results
    save_cache(updated_results)
    loop.close()

# --- SIDEBAR ---
with st.sidebar:
    st.title("🚀 NSE Scanner Pro")
    st.markdown("---")
    
    if st.button("START FULL MARKET SCAN"):
        with st.spinner("Analyzing 2000+ stocks..."):
            run_scan()
            
    st.markdown("### Filters")
    filter_signals = st.multiselect(
        "Filter Signals", 
        ["STRONG BUY", "BUY", "STRONG SELL", "SELL", "NEUTRAL"], 
        default=["STRONG BUY", "BUY", "STRONG SELL", "SELL"]
    )
    
    st.markdown("### Realtime")
    auto_refresh = st.checkbox("Auto-Refresh Prices (15s)", value=False)
    if auto_refresh:
        # Simple auto-refresh mechanism
        import time
        time.sleep(15)
        st.rerun()
    
    st.markdown("---")
    st.info("Created by Soham Asodekar")

# --- MAIN CONTENT ---
st.title("Market Intelligence Dashboard")

# Top Stats
if st.session_state.results:
    df = pd.DataFrame([vars(r) for r in st.session_state.results])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Active Stocks", len(df))
    with col2:
        buys = len(df[df['signal'].str.contains("BUY")])
        st.metric("Buy Signals", buys, delta_color="normal")
    with col3:
        sells = len(df[df['signal'].str.contains("SELL")])
        st.metric("Sell Signals", sells, delta_color="inverse")
    with col4:
        adv = len(df[df['change_pct'] > 0])
        dec = len(df[df['change_pct'] < 0])
        st.metric("Market Breadth (A/D)", f"{adv}/{dec}")
        
    # Table Results
    st.subheader("Live Signals")
    
    # Filtering
    display_df = df.copy()
    if filter_signals:
        display_df = display_df[display_df['signal'].isin(filter_signals)]
    
    # Styling columns
    st.dataframe(
        display_df[['symbol', 'signal', 'ltp', 'change_pct', 'confidence', 'target1', 'stop_loss', 'analysis']],
        use_container_width=True,
        column_config={
            "change_pct": st.column_config.NumberColumn(
                "Change %", format="%.2f%%"
            ),
            "ltp": st.column_config.NumberColumn(
                "Price (₹)", format="₹%.2f"
            ),
            "confidence": st.column_config.ProgressColumn(
                "Conf.", format="%.0f", min_value=0, max_value=100
            )
        }
    )
    
    # --- CHARTING ---
    st.markdown("---")
    st.subheader("Professional Technical Chart")
    
    col_stock, col_tf = st.columns([3, 1])
    with col_stock:
        selected_stock = st.selectbox("Select Stock to Analyze", display_df['symbol'].unique())
    with col_tf:
        timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"], index=5)
        
    # Timeframe Mapping
    tf_map = {
        "1m": ("1d", "1m"), "5m": ("5d", "5m"), "15m": ("5d", "15m"), 
        "30m": ("5d", "30m"), "1h": ("1mo", "1h"), "1d": ("1y", "1d"), 
        "1wk": ("2y", "1wk"), "1mo": ("5y", "1mo")
    }
    period, interval = tf_map[timeframe]
    
    if selected_stock:
        # Get the result object for this stock (Base data from scan)
        base_data = display_df[display_df['symbol'] == selected_stock].iloc[0]
        
        # Fetch Data for Chart
        with st.spinner(f"Loading {timeframe} Chart Data..."):
            ticker = yf.Ticker(selected_stock)
            hist = ticker.history(period=period, interval=interval)
        
        if not hist.empty:
            # --- CALCULATIONS (Dynamic based on Timeframe) ---
            # EMA
            hist['EMA50'] = hist['Close'].ewm(span=50, adjust=False).mean()
            hist['EMA200'] = hist['Close'].ewm(span=200, adjust=False).mean()
            
            # RSI
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            hist['RSI'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            hist['SMA20'] = hist['Close'].rolling(window=20).mean()
            hist['STD20'] = hist['Close'].rolling(window=20).std()
            hist['BB_Upper'] = hist['SMA20'] + (hist['STD20'] * 2)
            hist['BB_Lower'] = hist['SMA20'] - (hist['STD20'] * 2)
            
            # --- DYNAMIC SIGNAL ANALYSIS ---
            last_close = hist['Close'].iloc[-1]
            ema50_val = hist['EMA50'].iloc[-1]
            rsi_val = hist['RSI'].iloc[-1]
            
            # Generate signal for THIS specific timeframe
            tf_signal = "NEUTRAL"
            if last_close > ema50_val:
                if rsi_val < 30: tf_signal = "STRONG BUY"
                elif last_close > hist['Close'].iloc[-2]: tf_signal = "BUY"
            elif last_close < ema50_val:
                if rsi_val > 70: tf_signal = "STRONG SELL"
                elif last_close < hist['Close'].iloc[-2]: tf_signal = "SELL"
                
            # --- PLOTTING ---
            from plotly.subplots import make_subplots
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.05, row_heights=[0.7, 0.3],
                                subplot_titles=(f"{selected_stock} ({timeframe}) - {tf_signal}", "RSI Momentum"))
            
            # 1. Candlestick
            fig.add_trace(go.Candlestick(x=hist.index,
                            open=hist['Open'], high=hist['High'],
                            low=hist['Low'], close=hist['Close'],
                            name='Price'), row=1, col=1)
            
            # 2. Overlays (EMA, BB)
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA50'], line=dict(color='orange', width=1.5), name='EMA 50'), row=1, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA200'], line=dict(color='white', width=1.5), name='EMA 200'), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Upper'], line=dict(color='rgba(0, 100, 255, 0.3)', width=1), showlegend=False, name='BB Upper'), row=1, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Lower'], line=dict(color='rgba(0, 100, 255, 0.3)', width=1), fill='tonexty', fillcolor='rgba(0, 100, 255, 0.1)', name='Bollinger Bands'), row=1, col=1)
            
            # 3. Targets (Keep generic levels from base scan for reference, or recalc? Let's use base for persistency)
            if base_data['stop_loss'] > 0:
                # Only show these if we are on daily timeframe, otherwise they might not make sense? 
                # Actually, day levels are useful reference.
                pass 

            # 4. Markers for Signal (Dynamic)
            last_candle = hist.iloc[-1]
            marker_symbol = "triangle-up" if "BUY" in tf_signal else "triangle-down"
            marker_color = "#00c853" if "BUY" in tf_signal else "#ff4b4b"
            
            if "NEUTRAL" not in tf_signal:
                fig.add_trace(go.Scatter(
                    x=[hist.index[-1]], 
                    y=[last_candle['High'] if "SELL" in tf_signal else last_candle['Low']],
                    mode='markers+text',
                    marker=dict(symbol=marker_symbol, size=15, color=marker_color),
                    text=[tf_signal],
                    textposition="top center" if "SELL" in tf_signal else "bottom center",
                    textfont=dict(color=marker_color, size=14, family="Arial Black"),
                    name='Current Signal'
                ), row=1, col=1)

            # 5. RSI Subplot
            fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], line=dict(color='#a371f7', width=2), name='RSI'), row=2, col=1)
            
            # RSI Levels
            fig.add_shape(type="line", x0=hist.index[0], x1=hist.index[-1], y0=70, y1=70, line=dict(color="red", width=1, dash="dot"), row=2, col=1)
            fig.add_shape(type="line", x0=hist.index[0], x1=hist.index[-1], y0=30, y1=30, line=dict(color="green", width=1, dash="dot"), row=2, col=1)
            
            # Layout Updates
            fig.update_layout(
                height=800,
                xaxis_rangeslider_visible=False,
                template="plotly_dark",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Signal Details Box
            st.info(f"**{timeframe} Analysis:** {tf_signal} | **Price:** {last_close:.2f} | **RSI:** {rsi_val:.1f}")

else:
    st.info("Click 'START FULL MARKET SCAN' in the sidebar to begin.")
