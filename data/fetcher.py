"""NSE data fetcher with multi-source support."""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List
import time

from core.logger import get_logger


class NSEDataFetcher:
    """Fetch NSE stock data from multiple sources."""
    
    def __init__(self, nse_suffix: str = ".NS", logger=None):
        """Initialize the data fetcher.
        
        Args:
            nse_suffix: Suffix for NSE tickers (default: .NS for yfinance)
            logger: Logger instance
        """
        self.nse_suffix = nse_suffix
        self.logger = logger or get_logger()
    
    def _add_nse_suffix(self, symbol: str) -> str:
        """Add NSE suffix if not present.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Symbol with NSE suffix
        """
        if not symbol.endswith(self.nse_suffix):
            return f"{symbol}{self.nse_suffix}"
        return symbol
    
    def fetch_historical(self, symbol: str, period: str = "1y", 
                        interval: str = "1d") -> Optional[pd.DataFrame]:
        """Fetch historical OHLCV data.
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE' or 'RELIANCE.NS')
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
            interval: Data interval (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            symbol_with_suffix = self._add_nse_suffix(symbol)
            self.logger.info(f"Fetching historical data for {symbol_with_suffix} "
                           f"(period={period}, interval={interval})")
            
            ticker = yf.Ticker(symbol_with_suffix)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                self.logger.warning(f"No data returned for {symbol_with_suffix}")
                return None
            
            # Rename columns to lowercase and reset index
            df = df.reset_index()
            df.columns = df.columns.str.lower()
            
            # Rename 'date' or 'datetime' to 'timestamp'
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'timestamp'})
            elif 'datetime' in df.columns:
                df = df.rename(columns={'datetime': 'timestamp'})
            
            # Select required columns
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            df = df[required_cols]
            
            # Clean data
            df = df.dropna()
            df = df[df['volume'] > 0]  # Remove zero-volume candles
            
            self.logger.info(f"Fetched {len(df)} candles for {symbol_with_suffix}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return None
    
    def fetch_latest(self, symbol: str, interval: str = "1m", 
                    period: str = "1d") -> Optional[pd.DataFrame]:
        """Fetch latest/real-time data.
        
        Args:
            symbol: Stock symbol
            interval: Data interval
            period: Lookback period
            
        Returns:
            DataFrame with latest OHLCV data
        """
        return self.fetch_historical(symbol, period=period, interval=interval)
    
    def fetch_multiple_symbols(self, symbols: List[str], period: str = "1y",
                              interval: str = "1d") -> dict:
        """Fetch data for multiple symbols.
        
        Args:
            symbols: List of stock symbols
            period: Data period
            interval: Data interval
            
        Returns:
            Dictionary mapping symbol to DataFrame
        """
        results = {}
        
        for symbol in symbols:
            df = self.fetch_historical(symbol, period=period, interval=interval)
            if df is not None:
                results[symbol] = df
            
            # Rate limiting - be respectful to the API
            time.sleep(0.5)
        
        return results
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current price or None
        """
        try:
            # 1. Try nsepython first (Real-time from NSE)
            try:
                from nsepython import nse_quote
                clean_symbol = symbol.replace('.NS', '')
                quote = nse_quote(clean_symbol)
                
                price = 0.0
                if quote and isinstance(quote, dict):
                    if 'priceInfo' in quote:
                        price = quote['priceInfo'].get('lastPrice') or quote['priceInfo'].get('close')
                    elif 'lastPrice' in quote:
                        price = quote['lastPrice']
                
                if price:
                    return float(price)
            except Exception:
                pass # Silently fail back to yfinance

            # 2. Fallback to yfinance
            symbol_with_suffix = self._add_nse_suffix(symbol)
            ticker = yf.Ticker(symbol_with_suffix)
            
            # Try to get current price from info
            info = ticker.info
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if price is None:
                # Fallback: get latest close from 1d data
                df = self.fetch_historical(symbol, period="1d", interval="1m")
                if df is not None and not df.empty:
                    price = df.iloc[-1]['close']
            
            return float(price) if price else 0.0
            
        except Exception as e:
            self.logger.error(f"Error fetching current price for {symbol}: {str(e)}")
            return 0.0
    
    def validate_symbol(self, symbol: str) -> bool:
        """Check if a symbol is valid and has data.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            True if valid, False otherwise
        """
        try:
            symbol_with_suffix = self._add_nse_suffix(symbol)
            ticker = yf.Ticker(symbol_with_suffix)
            info = ticker.info
            
            # Check if we got valid info
            return bool(info and info.get('symbol'))
            
        except:
            return False
