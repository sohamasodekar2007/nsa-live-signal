"""Async batch price fetcher using aiohttp for maximum speed."""

import asyncio
import aiohttp
from typing import Dict, List, Optional
from datetime import datetime
import time


class AsyncPriceFetcher:
    """High-performance async price fetcher."""
    
    NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol={}"
    BATCH_SIZE = 20  # Symbols per batch
    RATE_LIMIT_DELAY = 0.1  # Seconds between batches
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookies = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            # First hit NSE homepage to get cookies
            connector = aiohttp.TCPConnector(limit=50, limit_per_host=10)
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.HEADERS
            )
            
            # Get cookies from NSE
            try:
                async with self._session.get('https://www.nseindia.com') as resp:
                    self._cookies = resp.cookies
            except:
                pass
        
        return self._session
    
    async def fetch_single(self, symbol: str) -> Optional[Dict]:
        """Fetch quote for single symbol."""
        clean_symbol = symbol.replace('.NS', '')
        url = self.NSE_QUOTE_URL.format(clean_symbol)
        
        try:
            session = await self._get_session()
            async with session.get(url, cookies=self._cookies) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price_info = data.get('priceInfo', {})
                    return {
                        'symbol': symbol,
                        'ltp': price_info.get('lastPrice', 0),
                        'open': price_info.get('open', 0),
                        'high': price_info.get('intraDayHighLow', {}).get('max', 0),
                        'low': price_info.get('intraDayHighLow', {}).get('min', 0),
                        'prev_close': price_info.get('previousClose', 0),
                        'change': price_info.get('change', 0),
                        'change_pct': price_info.get('pChange', 0),
                    }
        except Exception:
            pass
        
        return None
    
    async def fetch_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch quotes for batch of symbols concurrently."""
        tasks = [self.fetch_single(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        output = {}
        for result in results:
            if isinstance(result, dict) and result:
                output[result['symbol']] = result
        
        return output
    
    async def fetch_all(self, symbols: List[str]) -> Dict[str, Dict]:
        """Fetch all symbols in batches with rate limiting."""
        all_results = {}
        
        for i in range(0, len(symbols), self.BATCH_SIZE):
            batch = symbols[i:i + self.BATCH_SIZE]
            batch_results = await self.fetch_batch(batch)
            all_results.update(batch_results)
            
            # Rate limit between batches
            if i + self.BATCH_SIZE < len(symbols):
                await asyncio.sleep(self.RATE_LIMIT_DELAY)
        
        return all_results
    
    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()


# Synchronous wrapper for non-async contexts
def fetch_prices_sync(symbols: List[str]) -> Dict[str, Dict]:
    """Synchronous wrapper for async fetcher."""
    fetcher = AsyncPriceFetcher()
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context already
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, fetcher.fetch_all(symbols))
                return future.result()
        else:
            return loop.run_until_complete(fetcher.fetch_all(symbols))
    except RuntimeError:
        return asyncio.run(fetcher.fetch_all(symbols))
    finally:
        asyncio.run(fetcher.close())
