"""
Market-Wide Scan Engine - Scans ALL NSE stocks, not just watchlist.

WHY THIS EXISTS:
- Old code scanned only dashboard symbols (wrong)
- This engine is INDEPENDENT of UI
- Uses async batch fetching for speed
- Emits results only after full scan (no per-stock spam)
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
import logging

from data.nse_symbol_loader import get_nse_symbol_loader


# Only critical errors logged
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


@dataclass
class ScanResult:
    """Result for a single stock."""
    symbol: str
    ltp: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    prev_close: float = 0.0
    volume: int = 0
    change: float = 0.0
    change_pct: float = 0.0
    signal: str = "NEUTRAL"  # BUY, SELL, NEUTRAL
    confidence: float = 0.0
    scan_time: datetime = field(default_factory=datetime.now)
    error: str = ""


class MarketScanEngine:
    """
    Independent market scanner.
    
    CRITICAL: This does NOT use UI symbol list.
    It loads ALL NSE symbols internally.
    """
    
    # Parallelism settings
    BATCH_SIZE = 50  # Symbols per batch
    CONCURRENCY = 30  # Parallel requests
    TIMEOUT = 15  # Seconds per request
    RETRY_COUNT = 1  # Retry failed once
    
    # NSE API (no auth needed for basic quote)
    NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol={}"
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.nseindia.com/'
    }
    
    def __init__(self):
        self._symbol_loader = get_nse_symbol_loader()
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookies = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        # Callbacks
        self._on_progress: Optional[Callable[[int, int], None]] = None
        self._on_complete: Optional[Callable[[List[ScanResult]], None]] = None
    
    def set_callbacks(self, 
                     on_progress: Callable[[int, int], None] = None,
                     on_complete: Callable[[List[ScanResult]], None] = None):
        """Set progress and completion callbacks."""
        self._on_progress = on_progress
        self._on_complete = on_complete
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Create or get aiohttp session with NSE cookies."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=20, ssl=False)
            timeout = aiohttp.ClientTimeout(total=self.TIMEOUT)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.HEADERS
            )
            
            # Get NSE cookies (required)
            try:
                async with self._session.get('https://www.nseindia.com') as resp:
                    self._cookies = resp.cookies
            except:
                pass
        
        return self._session
    
    async def _fetch_single(self, symbol: str) -> ScanResult:
        """Fetch data for single symbol with semaphore."""
        async with self._semaphore:
            result = ScanResult(symbol=symbol)
            clean_symbol = symbol.replace('.NS', '')
            url = self.NSE_QUOTE_URL.format(clean_symbol)
            
            for attempt in range(self.RETRY_COUNT + 1):
                try:
                    session = await self._get_session()
                    async with session.get(url, cookies=self._cookies) as resp:
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
                            
                            # Simple signal logic
                            result.signal, result.confidence = self._generate_signal(result)
                            
                            return result
                        
                        elif resp.status == 429:
                            # Rate limited - wait and retry
                            await asyncio.sleep(1)
                            continue
                        
                except asyncio.TimeoutError:
                    result.error = "timeout"
                except Exception as e:
                    result.error = str(e)[:50]
            
            return result
    
    def _generate_signal(self, result: ScanResult) -> tuple:
        """
        Simple signal generation based on scan data.
        WHY: Quick signal for scan results, not full analysis.
        """
        if result.ltp <= 0 or result.prev_close <= 0:
            return "NEUTRAL", 0.0
        
        change_pct = result.change_pct
        
        # Momentum-based quick signal
        if change_pct >= 3.0:
            return "BUY", min(60 + change_pct * 5, 90)
        elif change_pct <= -3.0:
            return "SELL", min(60 + abs(change_pct) * 5, 90)
        elif change_pct >= 1.5:
            return "BUY", 50 + change_pct * 5
        elif change_pct <= -1.5:
            return "SELL", 50 + abs(change_pct) * 5
        
        return "NEUTRAL", 30.0
    
    async def scan_all_async(self) -> List[ScanResult]:
        """
        Scan ALL NSE stocks asynchronously.
        
        This is the main entry point for full market scan.
        """
        # Load ALL symbols (not from UI!)
        symbols = self._symbol_loader.get_all_symbols()
        total = len(symbols)
        
        if total == 0:
            return []
        
        # Initialize
        self._semaphore = asyncio.Semaphore(self.CONCURRENCY)
        results: List[ScanResult] = []
        scanned = 0
        
        # Process in batches
        for i in range(0, total, self.BATCH_SIZE):
            batch = symbols[i:i + self.BATCH_SIZE]
            
            # Fetch batch in parallel
            tasks = [self._fetch_single(s) for s in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for r in batch_results:
                if isinstance(r, ScanResult):
                    results.append(r)
            
            scanned += len(batch)
            
            # Progress callback
            if self._on_progress:
                self._on_progress(scanned, total)
            
            # Small delay between batches to avoid rate limit
            if i + self.BATCH_SIZE < total:
                await asyncio.sleep(0.2)
        
        # Close session
        if self._session and not self._session.closed:
            await self._session.close()
        
        # Filter valid results and sort by signal strength
        valid_results = [r for r in results if r.ltp > 0]
        valid_results.sort(key=lambda x: (x.signal != "NEUTRAL", x.confidence), reverse=True)
        
        # Completion callback
        if self._on_complete:
            self._on_complete(valid_results)
        
        return valid_results
    
    def scan_all_sync(self) -> List[ScanResult]:
        """Synchronous wrapper for scan_all_async."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in async context - can't use run_until_complete
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.scan_all_async())
                    return future.result()
            else:
                return loop.run_until_complete(self.scan_all_async())
        except RuntimeError:
            return asyncio.run(self.scan_all_async())
    
    def get_buy_signals(self, results: List[ScanResult], min_confidence: float = 60.0) -> List[ScanResult]:
        """Filter BUY signals with minimum confidence."""
        return [r for r in results if r.signal == "BUY" and r.confidence >= min_confidence]
    
    def get_sell_signals(self, results: List[ScanResult], min_confidence: float = 60.0) -> List[ScanResult]:
        """Filter SELL signals with minimum confidence."""
        return [r for r in results if r.signal == "SELL" and r.confidence >= min_confidence]


# Singleton
_engine: Optional[MarketScanEngine] = None

def get_market_scan_engine() -> MarketScanEngine:
    """Get singleton scan engine."""
    global _engine
    if _engine is None:
        _engine = MarketScanEngine()
    return _engine
