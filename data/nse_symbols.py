"""NSE Symbol List Manager - Fetch once, cache forever."""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path


class NSESymbolManager:
    """Manages NSE equity symbol list with disk caching."""
    
    # NIFTY 50 + NIFTY NEXT 50 + Popular stocks
    CORE_SYMBOLS = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
        "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "HCLTECH",
        "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN",
        "BAJFINANCE", "WIPRO", "ULTRACEMCO", "NESTLEIND", "TATAMOTORS",
        "POWERGRID", "NTPC", "TECHM", "ONGC", "TATASTEEL", "JSWSTEEL",
        "ADANIENT", "ADANIPORTS", "COALINDIA", "DRREDDY", "BAJAJFINSV",
        "HINDALCO", "GRASIM", "DIVISLAB", "BRITANNIA", "CIPLA", "EICHERMOT",
        "APOLLOHOSP", "HEROMOTOCO", "INDUSINDBK", "SBILIFE", "TATACONSUM",
        "BPCL", "HDFCLIFE", "UPL", "M&M", "BAJAJ-AUTO"
    ]
    
    CACHE_FILE = "data_storage/nse_symbols.json"
    CACHE_EXPIRY_DAYS = 7
    
    def __init__(self):
        self._symbols: List[str] = []
        self._metadata: Dict[str, Dict] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load symbols from cache if valid."""
        cache_path = Path(self.CACHE_FILE)
        
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                
                # Check expiry
                cached_time = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
                if datetime.now() - cached_time < timedelta(days=self.CACHE_EXPIRY_DAYS):
                    self._symbols = data.get('symbols', [])
                    self._metadata = data.get('metadata', {})
                    return
            except:
                pass
        
        # Fallback to core symbols
        self._symbols = [f"{s}.NS" for s in self.CORE_SYMBOLS]
        self._save_cache()
    
    def _save_cache(self):
        """Save symbols to disk."""
        cache_path = Path(self.CACHE_FILE)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'cached_at': datetime.now().isoformat(),
            'symbols': self._symbols,
            'metadata': self._metadata
        }
        
        with open(cache_path, 'w') as f:
            json.dump(data, f)
    
    def get_all_symbols(self) -> List[str]:
        """Get all cached symbols."""
        return self._symbols.copy()
    
    def get_watchlist_default(self) -> List[str]:
        """Get default watchlist (top 10 by market cap)."""
        return self._symbols[:10]
    
    def add_symbol(self, symbol: str) -> bool:
        """Add a symbol to the list."""
        if not symbol.endswith('.NS'):
            symbol = f"{symbol}.NS"
        
        if symbol not in self._symbols:
            self._symbols.append(symbol)
            self._save_cache()
            return True
        return False
    
    def refresh_from_nse(self):
        """Refresh symbol list from NSE (expensive, use sparingly)."""
        try:
            from nsepython import nse_eq_symbols
            symbols = nse_eq_symbols()
            if symbols:
                self._symbols = [f"{s}.NS" for s in symbols]
                self._save_cache()
        except Exception:
            pass  # Keep existing cache


# Singleton instance
_symbol_manager: Optional[NSESymbolManager] = None

def get_symbol_manager() -> NSESymbolManager:
    global _symbol_manager
    if _symbol_manager is None:
        _symbol_manager = NSESymbolManager()
    return _symbol_manager
