"""
Headless Markets Scanner - For Web/Cloud Usage (Streamlit).
Decoupled from PyQt for Fly.io deployment.
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import List, Optional, Callable
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
import yfinance as yf

from data.nse_symbol_loader import get_nse_symbol_loader

@dataclass
class ScanResult:
    """Standardized scan result."""
    symbol: str
    ltp: float = 0.0
    change_pct: float = 0.0
    signal: str = "NEUTRAL"
    confidence: float = 0.0
    stop_loss: float = 0.0
    target1: float = 0.0
    target2: float = 0.0
    analysis: str = ""
    error: str = ""

class AsyncScanner:
    """
    Async market scanner for Web/CLI usage (No GUI dependencies).
    """
    
    NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol={}"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.nseindia.com/'
    }
    
    def __init__(self):
        self._symbol_loader = get_nse_symbol_loader()
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookies = None
        # Optimization: Thread pool for blocking yfinance calls
        self._executor = None 
        
    async def scan_market(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> List[ScanResult]:
        """Run full market scan."""
        symbols = self._symbol_loader.get_all_symbols()
        total = len(symbols)
        results = []
        
        # Optimization: Higher concurrency (Aggressive)
        semaphore = asyncio.Semaphore(100) 
        
        # Optimization: Initialize Executor in run
        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
        
        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(limit=0, limit_per_host=20, ssl=False) # No global limit
        self._session = aiohttp.ClientSession(connector=connector, headers=self.HEADERS, timeout=timeout)
        
        # Get cookies
        try:
            async with self._session.get('https://www.nseindia.com', timeout=5) as resp:
                self._cookies = resp.cookies
        except:
            pass
            
        async def fetch(symbol):
            async with semaphore:
                return await self._analyze_symbol(symbol)
        
        # Generator for progress tracking
        pending = [fetch(s) for s in symbols]
        completed = 0
        
        # Process in larger batches
        batch_size = 100
        for i in range(0, total, batch_size):
            batch = pending[i:i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for res in batch_results:
                if isinstance(res, ScanResult):
                    results.append(res)
            
            completed += len(batch)
            if progress_callback:
                progress_callback(completed, total)
                
            # Reduced sleep
            await asyncio.sleep(0.01)
            
        await self._session.close()
        # Shutdown executor
        self._executor.shutdown(wait=False)
        
        # Sort by Signal importance
        results.sort(key=lambda x: (x.signal != "NEUTRAL", abs(x.change_pct)), reverse=True)
        return [r for r in results if r.ltp > 0] # Return only valid
    
    async def refresh_batch(self, symbols: List[str]) -> List[ScanResult]:
        """Refresh specific symbols (for Realtime View)."""
        results = []
        
        # Initialize resources
        timeout = aiohttp.ClientTimeout(total=5)
        connector = aiohttp.TCPConnector(limit=50, ssl=False)
        self._session = aiohttp.ClientSession(connector=connector, headers=self.HEADERS, timeout=timeout)
        
        # Initialize Executor if needed (though _deep_analysis checks it, better to have it)
        import concurrent.futures
        if self._executor is None:
            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        try:
            tasks = [self._analyze_symbol(sym) for sym in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter valid
            valid = [r for r in results if isinstance(r, ScanResult)]
            return valid
        finally:
            await self._session.close() # Ensure cleanup
    
    async def _analyze_symbol(self, symbol: str) -> ScanResult:
        """Fetch and analyze single symbol."""
        result = ScanResult(symbol=symbol)
        clean_symbol = symbol.replace('.NS', '')
        url = self.NSE_QUOTE_URL.format(clean_symbol)
        
        try:
            async with self._session.get(url, cookies=self._cookies) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    info = data.get('priceInfo', {})
                    
                    result.ltp = info.get('lastPrice', 0) or 0
                    result.change_pct = info.get('pChange', 0) or 0
                    h = info.get('intraDayHighLow', {}).get('max', 0) or 0
                    l = info.get('intraDayHighLow', {}).get('min', 0) or 0
                    
                    # Logic: Momentum + Volatility
                    self._calculate_signals(result, h, l)
                    
                    # Deep Analysis for Movers
                    if abs(result.change_pct) > 1.0:
                        await self._deep_analysis(result)
                        
                else:
                    result.error = f"HTTP {resp.status}"
                    
        except Exception as e:
            result.error = str(e)
            
        return result

    def _calculate_signals(self, result: ScanResult, high: float, low: float):
        """Basic signal calculation."""
        if result.ltp == 0: return

        # Dynamic Buffer (ATR proxy)
        day_range = high - low
        buffer = max(day_range * 0.2, result.ltp * 0.005)
        
        if result.change_pct >= 2.0:
            result.signal = "STRONG BUY" if result.change_pct > 4 else "BUY"
            result.confidence = 60 + result.change_pct * 2
            result.stop_loss = round(low - buffer, 2)
            result.target1 = round(result.ltp + (result.ltp - result.stop_loss), 2)
            result.target2 = round(result.ltp + (result.ltp - result.stop_loss) * 2, 2)
            result.analysis = f"Momentum +{result.change_pct}%"
            
        elif result.change_pct <= -2.0:
            result.signal = "STRONG SELL" if result.change_pct < -4 else "SELL"
            result.confidence = 60 + abs(result.change_pct) * 2
            result.stop_loss = round(high + buffer, 2)
            result.target1 = round(result.ltp - (result.stop_loss - result.ltp), 2)
            result.target2 = round(result.ltp - (result.stop_loss - result.ltp) * 2, 2)
            result.analysis = f"Momentum {result.change_pct}%"
            
    async def _deep_analysis(self, result: ScanResult):
        """Fetch history for RSI/EMA (Non-Blocking via Executor)."""
        loop = asyncio.get_running_loop()
        
        def blocking_logic():
            try:
                ticker = yf.Ticker(result.symbol)
                # Fetch more history for stability
                hist = ticker.history(period="6mo", interval="1d")
                
                if len(hist) < 50: return
                
                # --- INDICATORS ---
                closes = hist['Close']
                highs = hist['High']
                lows = hist['Low']
                
                # 1. EMA Trend
                ema50 = closes.ewm(span=50, adjust=False).mean().iloc[-1]
                ema200 = closes.ewm(span=200, adjust=False).mean().iloc[-1]
                
                # 2. RSI (14)
                delta = closes.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                rsi_val = rsi.iloc[-1]
                
                # 3. ATR (14) for Volatility-Based Stop Loss
                tr1 = highs - lows
                tr2 = (highs - closes.shift()).abs()
                tr3 = (lows - closes.shift()).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr = tr.rolling(window=14).mean().iloc[-1]
                
                # --- PRO STRATEGY LOGIC ---
                result.analysis = f"RSI {rsi_val:.1f}"
                
                # Trend Filter: Only Buy above EMA200, Sell below EMA200
                is_uptrend = result.ltp > ema200
                is_downtrend = result.ltp < ema200
                
                # Signal Generation
                new_signal = "NEUTRAL"
                
                # LONG Setup (Trend + Dip or Momentum)
                if is_uptrend:
                    result.analysis += " | Uptrend"
                    # Pullback Strategy: Price > 200EMA but RSI < 40 (Oversold Dip)
                    if rsi_val < 40 and result.ltp > ema50:
                        new_signal = "STRONG BUY"
                        result.analysis += " | Dip Buy"
                    # Momentum Strategy: RSI crosses 50 + Price > 50EMA
                    elif rsi_val > 50 and rsi_val < 70 and result.ltp > ema50 and result.change_pct > 1:
                        new_signal = "BUY"
                        result.analysis += " | Momentum"
                        
                # SHORT Setup
                elif is_downtrend:
                    result.analysis += " | Downtrend"
                    # Pullback Strategy: Price < 200EMA but RSI > 60 (Overbought Rally)
                    if rsi_val > 60 and result.ltp < ema50:
                        new_signal = "STRONG SELL"
                        result.analysis += " | Rally Sell"
                    # Momentum Strategy
                    elif rsi_val < 50 and rsi_val > 30 and result.ltp < ema50 and result.change_pct < -1:
                        new_signal = "SELL"
                        result.analysis += " | Breakdown"

                # Update Signal if valid
                if new_signal != "NEUTRAL":
                    result.signal = new_signal
                    # RISK MANAGEMENT (ATR Based)
                    # Stop Loss = 2 * ATR
                    sl_pips = atr * 2
                    
                    if "BUY" in new_signal:
                        result.stop_loss = round(result.ltp - sl_pips, 2)
                        risk = result.ltp - result.stop_loss
                        result.target1 = round(result.ltp + (risk * 1.5), 2) # 1:1.5
                        result.target2 = round(result.ltp + (risk * 3.0), 2) # 1:3 (Jackpot)
                        result.confidence = 80 if "STRONG" in new_signal else 65
                    else:
                        result.stop_loss = round(result.ltp + sl_pips, 2)
                        risk = result.stop_loss - result.ltp
                        result.target1 = round(result.ltp - (risk * 1.5), 2)
                        result.target2 = round(result.ltp - (risk * 3.0), 2)
                        result.confidence = 80 if "STRONG" in new_signal else 65

            except Exception:
                pass

        # Run in thread pool to prevent blocking main loop
        await loop.run_in_executor(self._executor, blocking_logic)
