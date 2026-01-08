"""
Enhanced Market Scanner Worker - With Technical Analysis, Targets & Stop Loss.

Provides:
- Stop Loss (based on day's low / ATR)
- Target 1 (1:1 risk-reward)
- Target 2 (2:1 risk-reward)
- Proper signal analysis
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, field
from PyQt6.QtCore import QThread, pyqtSignal

from data.nse_symbol_loader import get_nse_symbol_loader


@dataclass
class ScanResult:
    """Enhanced result with targets and stop loss."""
    symbol: str
    ltp: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    volume: int = 0
    change: float = 0.0
    change_pct: float = 0.0
    
    # Signal info
    signal: str = "NEUTRAL"
    confidence: float = 0.0
    
    # Technical levels (THE NEW FIELDS)
    stop_loss: float = 0.0
    target1: float = 0.0
    target2: float = 0.0
    risk: float = 0.0
    reward: float = 0.0
    risk_reward_ratio: float = 0.0
    
    # Analysis reasoning
    analysis: str = ""
    
    scan_time: datetime = field(default_factory=datetime.now)
    error: str = ""


class MarketScanWorker(QThread):
    """
    Enhanced market scanner with proper technical analysis.
    """
    
    # Signals
    scan_started = pyqtSignal(int)
    scan_progress = pyqtSignal(int, int)
    stock_scanned = pyqtSignal(str, str, float)
    scan_complete = pyqtSignal(list)
    scan_error = pyqtSignal(str)
    
    # Settings
    BATCH_SIZE = 50
    CONCURRENCY = 30
    TIMEOUT = 15
    
    NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol={}"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/'
    }
    
    def __init__(self):
        super().__init__()
        self._symbol_loader = get_nse_symbol_loader()
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookies = None
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    def run(self):
        """Execute full market scan."""
        self._running = True
        
        try:
            symbols = self._symbol_loader.get_all_symbols()
            total = len(symbols)
            
            if total == 0:
                self.scan_error.emit("No symbols loaded")
                return
            
            self.scan_started.emit(total)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            results = loop.run_until_complete(self._scan_all(symbols))
            
            loop.close()
            
            if self._running:
                self.scan_complete.emit(results)
            
        except Exception as e:
            self.scan_error.emit(str(e))
        
        self._running = False
    
    async def _scan_all(self, symbols: List[str]) -> List[ScanResult]:
        """Async scan all symbols."""
        total = len(symbols)
        results: List[ScanResult] = []
        scanned = 0
        
        self._semaphore = asyncio.Semaphore(self.CONCURRENCY)
        
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=20, ssl=False)
        timeout = aiohttp.ClientTimeout(total=self.TIMEOUT)
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.HEADERS
        )
        
        try:
            async with self._session.get('https://www.nseindia.com') as resp:
                self._cookies = resp.cookies
        except:
            pass
        
        for i in range(0, total, self.BATCH_SIZE):
            if not self._running:
                break
            
            batch = symbols[i:i + self.BATCH_SIZE]
            tasks = [self._fetch_single(s) for s in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for r in batch_results:
                if isinstance(r, ScanResult):
                    results.append(r)
            
            scanned += len(batch)
            self.scan_progress.emit(scanned, total)
            
            if i + self.BATCH_SIZE < total:
                await asyncio.sleep(0.1)
        
        if self._session and not self._session.closed:
            await self._session.close()
        
        # Filter and sort
        valid_results = [r for r in results if r.ltp > 0]
        valid_results.sort(key=lambda x: (x.signal != "NEUTRAL", x.confidence, abs(x.risk_reward_ratio)), reverse=True)
        
        return valid_results
    
    async def _fetch_single(self, symbol: str) -> ScanResult:
        """Fetch data for single symbol with technical analysis."""
        async with self._semaphore:
            result = ScanResult(symbol=symbol)
            clean_symbol = symbol.replace('.NS', '')
            url = self.NSE_QUOTE_URL.format(clean_symbol)
            
            try:
                async with self._session.get(url, cookies=self._cookies) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        price_info = data.get('priceInfo', {})
                        
                        result.ltp = price_info.get('lastPrice', 0) or 0
                        result.open = price_info.get('open', 0) or 0
                        result.prev_close = price_info.get('previousClose', 0) or 0
                        result.change = price_info.get('change', 0) or 0
                        result.change_pct = price_info.get('pChange', 0) or 0
                        
                        intra = price_info.get('intraDayHighLow', {})
                        result.high = intra.get('max', 0) or 0
                        result.low = intra.get('min', 0) or 0
                        
                        sec_info = data.get('securityWiseDP', {})
                        result.volume = sec_info.get('quantityTraded', 0) or 0
                        
                        # TECHNICAL ANALYSIS
                        # Optimization: Only deep analyze if significant movement (> 1%)
                        if abs(result.change_pct) >= 1.0:
                            self._deep_technical_analysis(result)
                        else:
                            self._calculate_levels(result)
                        
                        status = f"✓ {result.signal}" if result.ltp > 0 else "✗ No data"
                        self.stock_scanned.emit(symbol, status, result.ltp)
                        
                        return result
                    
                    elif resp.status == 429:
                        result.error = "rate_limited"
                        self.stock_scanned.emit(symbol, "⏳ Rate limited", 0)
                    else:
                        result.error = f"HTTP {resp.status}"
                        self.stock_scanned.emit(symbol, f"✗ HTTP {resp.status}", 0)
                
            except asyncio.TimeoutError:
                result.error = "timeout"
                self.stock_scanned.emit(symbol, "⏳ Timeout", 0)
            except Exception as e:
                result.error = str(e)[:30]
                self.stock_scanned.emit(symbol, "✗ Error", 0)
            
            return result
    
    def _deep_technical_analysis(self, result: ScanResult):
        """
        Perform deep technical analysis with historical data (RSI, EMA).
        Warning: This is slower, so only use for active stocks.
        """
        import yfinance as yf
        import pandas as pd
        import numpy as np
        
        try:
            # Fetch history (enough for EMA 50)
            ticker = yf.Ticker(result.symbol)
            hist = ticker.history(period="3mo", interval="1d")
            
            if hist.empty or len(hist) < 50:
                self._calculate_levels(result)
                return
            
            closes = hist['Close'].values
            
            # --- RSI (14) ---
            delta = np.diff(closes)
            gain = (delta * (delta > 0)).copy()
            loss = (-delta * (delta < 0)).copy()
            
            avg_gain = np.mean(gain[:14])
            avg_loss = np.mean(loss[:14])
            
            # Simple RSI approximation for speed
            for i in range(14, len(delta)):
                avg_gain = (avg_gain * 13 + gain[i]) / 14
                avg_loss = (avg_loss * 13 + loss[i]) / 14
                
            rs = avg_gain / avg_loss if avg_loss != 0 else 0
            rsi = 100 - (100 / (1 + rs))
            
            # --- EMA (50) ---
            ema50 = pd.Series(closes).ewm(span=50, adjust=False).mean().iloc[-1]
            
            # Update Signal Reasoning
            rsi_signal = ""
            if rsi < 30: rsi_signal = "Oversold (RSI < 30)"
            elif rsi > 70: rsi_signal = "Overbought (RSI > 70)"
            else: rsi_signal = f"RSI Neutral ({rsi:.0f})"
            
            trend = "Bullish" if result.ltp > ema50 else "Bearish"
            
            # Recalculate Levels with Tech Confirmation
            self._calculate_levels(result)
            
            # Boost confidence if indicators align
            if "BUY" in result.signal:
                if result.ltp > ema50: result.confidence += 10
                if rsi < 40: result.confidence += 10  # Buying dip
                result.analysis = f"{result.analysis} | {trend} > EMA50. {rsi_signal}."
                
            elif "SELL" in result.signal:
                if result.ltp < ema50: result.confidence += 10
                if rsi > 60: result.confidence += 10  # Selling top
                result.analysis = f"{result.analysis} | {trend} < EMA50. {rsi_signal}."
                
            result.confidence = min(result.confidence, 100)
            
        except Exception:
            # Fallback to basic levels if yfinance fails
            self._calculate_levels(result)

    def _calculate_levels(self, result: ScanResult):
        """
        Calculate Stop Loss, Target 1, Target 2 with proper analysis.
        
        Analysis Logic:
        - For BUY: SL = Day Low - buffer, Targets above LTP
        - For SELL: SL = Day High + buffer, Targets below LTP
        - Risk-Reward ratio calculated
        """
        if result.ltp <= 0 or result.prev_close <= 0:
            result.signal = "NEUTRAL"
            result.confidence = 0
            return
        
        ltp = result.ltp
        high = result.high if result.high > 0 else ltp * 1.01
        low = result.low if result.low > 0 else ltp * 0.99
        change_pct = result.change_pct
        
        # Calculate day range (ATR proxy)
        day_range = high - low
        buffer = day_range * 0.2  # 20% buffer beyond day range
        
        # Minimum buffer of 0.5% of price
        min_buffer = ltp * 0.005
        buffer = max(buffer, min_buffer)
        
        # BUY SIGNAL ANALYSIS
        if change_pct >= 2.0:
            result.signal = "STRONG BUY" if change_pct >= 4.0 else "BUY"
            result.confidence = min(60 + change_pct * 5, 80) # Cap base confidence, let Deep Analysis boost it
            
            # Stop Loss: Below day's low with buffer
            result.stop_loss = round(low - buffer, 2)
            
            # Risk calculation
            result.risk = ltp - result.stop_loss
            
            # Target 1: 1:1 risk-reward
            result.target1 = round(ltp + result.risk, 2)
            
            # Target 2: 2:1 risk-reward
            result.target2 = round(ltp + (result.risk * 2), 2)
            
            # Risk-Reward Ratio
            result.reward = result.target1 - ltp
            result.risk_reward_ratio = round(result.reward / result.risk, 2) if result.risk > 0 else 0
            
            result.analysis = f"Momentum +{change_pct:.1f}%"
        
        # SELL SIGNAL ANALYSIS
        elif change_pct <= -2.0:
            result.signal = "STRONG SELL" if change_pct <= -4.0 else "SELL"
            result.confidence = min(60 + abs(change_pct) * 5, 80)
            
            # Stop Loss: Above day's high with buffer
            result.stop_loss = round(high + buffer, 2)
            
            # Risk calculation
            result.risk = result.stop_loss - ltp
            
            # Target 1: 1:1 risk-reward (below LTP for sell)
            result.target1 = round(ltp - result.risk, 2)
            
            # Target 2: 2:1 risk-reward
            result.target2 = round(ltp - (result.risk * 2), 2)
            
            # Risk-Reward Ratio
            result.reward = ltp - result.target1
            result.risk_reward_ratio = round(result.reward / result.risk, 2) if result.risk > 0 else 0
            
            result.analysis = f"Momentum {change_pct:.1f}%"
        
        # WEAK SIGNALS
        elif change_pct >= 1.0:
            result.signal = "WEAK BUY"
            result.confidence = 40 + change_pct * 5
            
            result.stop_loss = round(low - buffer, 2)
            result.risk = ltp - result.stop_loss
            result.target1 = round(ltp + result.risk, 2)
            result.target2 = round(ltp + (result.risk * 1.5), 2)
            result.risk_reward_ratio = 1.0
            
            result.analysis = f"Mild Bullish +{change_pct:.1f}%"
        
        elif change_pct <= -1.0:
            result.signal = "WEAK SELL"
            result.confidence = 40 + abs(change_pct) * 5
            
            result.stop_loss = round(high + buffer, 2)
            result.risk = result.stop_loss - ltp
            result.target1 = round(ltp - result.risk, 2)
            result.target2 = round(ltp - (result.risk * 1.5), 2)
            result.risk_reward_ratio = 1.0
            
            result.analysis = f"Mild Bearish {change_pct:.1f}%"
        
        # NEUTRAL
        else:
            result.signal = "NEUTRAL"
            result.confidence = 30
            
            # Still calculate levels for reference
            result.stop_loss = round(low - buffer, 2)
            result.target1 = round(high, 2)
            result.target2 = round(high + (high - low) * 0.5, 2)
            result.risk = ltp - result.stop_loss
            result.risk_reward_ratio = 0
            
            result.analysis = "Consolidating"
    
    def stop(self):
        """Stop the worker."""
        self._running = False
