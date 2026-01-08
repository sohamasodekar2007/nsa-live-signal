"""Data validation and cleaning utilities."""

import pandas as pd
import numpy as np
from typing import Tuple, List

from core.logger import get_logger


class DataValidator:
    """Validate and clean OHLCV data."""
    
    def __init__(self, logger=None):
        """Initialize the validator.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger or get_logger()
    
    def validate_ohlcv(self, df: pd.DataFrame, symbol: str = "") -> Tuple[pd.DataFrame, List[str]]:
        """Validate and clean OHLCV data.
        
        Args:
            df: DataFrame with OHLCV data
            symbol: Stock symbol (for logging)
            
        Returns:
            Tuple of (cleaned DataFrame, list of issues found)
        """
        if df.empty:
            return df, ["Empty DataFrame"]
        
        issues = []
        original_count = len(df)
        
        # 1. Check required columns
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            issues.append(f"Missing columns: {missing_cols}")
            return df, issues
        
        # 2. Remove null values
        null_counts = df[required_cols].isnull().sum()
        if null_counts.any():
            issues.append(f"Found null values: {null_counts[null_counts > 0].to_dict()}")
            df = df.dropna(subset=required_cols)
        
        # 3. Validate OHLC relationships
        # High should be >= Open, Low, Close
        invalid_high = df[(df['high'] < df['open']) | 
                         (df['high'] < df['low']) | 
                         (df['high'] < df['close'])]
        if len(invalid_high) > 0:
            issues.append(f"Found {len(invalid_high)} rows with invalid high prices")
            df = df.drop(invalid_high.index)
        
        # Low should be <= Open, High, Close
        invalid_low = df[(df['low'] > df['open']) | 
                        (df['low'] > df['high']) | 
                        (df['low'] > df['close'])]
        if len(invalid_low) > 0:
            issues.append(f"Found {len(invalid_low)} rows with invalid low prices")
            df = df.drop(invalid_low.index)
        
        # 4. Check for zero or negative prices
        price_cols = ['open', 'high', 'low', 'close']
        invalid_prices = df[(df[price_cols] <= 0).any(axis=1)]
        if len(invalid_prices) > 0:
            issues.append(f"Found {len(invalid_prices)} rows with zero/negative prices")
            df = df.drop(invalid_prices.index)
        
        # 5. Check for zero volume
        zero_volume = df[df['volume'] == 0]
        if len(zero_volume) > 0:
            issues.append(f"Found {len(zero_volume)} rows with zero volume")
            df = df[df['volume'] > 0]
        
        # 6. Check for outliers (price changes > 20% in one candle - likely data error)
        df_sorted = df.sort_values('timestamp').reset_index(drop=True)
        if len(df_sorted) > 1:
            price_change_pct = df_sorted['close'].pct_change().abs() * 100
            outliers = df_sorted[price_change_pct > 20]
            if len(outliers) > 0:
                issues.append(f"Found {len(outliers)} potential outliers (>20% price change)")
                # Don't remove outliers automatically - could be legitimate gap up/down
                # Just flag for review
        
        # 7. Check for duplicate timestamps
        duplicates = df_sorted[df_sorted.duplicated(subset=['timestamp'], keep=False)]
        if len(duplicates) > 0:
            issues.append(f"Found {len(duplicates)} duplicate timestamps")
            df = df_sorted.drop_duplicates(subset=['timestamp'], keep='first')
        
        # 8. Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Log results
        cleaned_count = len(df)
        removed_count = original_count - cleaned_count
        
        if removed_count > 0:
            self.logger.warning(
                f"Data validation for {symbol}: Removed {removed_count}/{original_count} rows"
            )
        
        if issues:
            self.logger.debug(f"Validation issues for {symbol}: {'; '.join(issues)}")
        
        return df, issues
    
    def fill_missing_candles(self, df: pd.DataFrame, freq: str = '1D') -> pd.DataFrame:
        """Fill missing candles with forward-fill for small gaps.
        
        Args:
            df: DataFrame with OHLCV data
            freq: Frequency string (e.g., '1D', '1H', '5T' for 5 minutes)
            
        Returns:
            DataFrame with filled gaps
        """
        if df.empty:
            return df
        
        # Set timestamp as index
        df_indexed = df.set_index('timestamp')
        
        # Create complete date range
        full_range = pd.date_range(
            start=df_indexed.index.min(),
            end=df_indexed.index.max(),
            freq=freq
        )
        
        # Reindex and forward-fill
        df_filled = df_indexed.reindex(full_range)
        
        # Only forward-fill price data, not volume
        price_cols = ['open', 'high', 'low', 'close']
        df_filled[price_cols] = df_filled[price_cols].fillna(method='ffill', limit=3)
        df_filled['volume'] = df_filled['volume'].fillna(0)
        
        # Reset index
        df_filled = df_filled.reset_index()
        df_filled = df_filled.rename(columns={'index': 'timestamp'})
        
        # Remove rows still containing NaN (gaps too large)
        df_filled = df_filled.dropna(subset=price_cols)
        
        return df_filled
    
    def calculate_data_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate a data quality score (0-100).
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Quality score (0-100)
        """
        if df.empty:
            return 0.0
        
        score = 100.0
        
        # Deduct for missing data
        null_ratio = df.isnull().sum().sum() / (len(df) * len(df.columns))
        score -= null_ratio * 30
        
        # Deduct for zero volume candles
        zero_vol_ratio = (df['volume'] == 0).sum() / len(df)
        score -= zero_vol_ratio * 20
        
        # Check consistency
        try:
            _, issues = self.validate_ohlcv(df.copy())
            score -= len(issues) * 5
        except:
            score -= 20
        
        return max(0.0, min(100.0, score))
