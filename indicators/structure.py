"""Structure analysis: Support/Resistance, Breakouts, Volume Profile."""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple


class StructureAnalysis:
    """Analyze market structure and price patterns."""
    
    @staticmethod
    def find_support_resistance(df: pd.DataFrame, lookback: int = 50,
                               proximity_pct: float = 0.5) -> Dict[str, List[float]]:
        """Find support and resistance levels using swing highs/lows.
        
        Args:
            df: DataFrame with OHLC data
            lookback: Lookback period for finding swing points
            proximity_pct: Percentage proximity to cluster levels
            
        Returns:
            Dictionary with support and resistance levels
        """
        if df.empty or len(df) < lookback:
            return {'support': [], 'resistance': []}
        
        df_lookback = df.tail(lookback)
        
        # Find swing highs and lows
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(df_lookback) - 2):
            # Swing high: higher than 2 candles on each side
            if (df_lookback.iloc[i]['high'] > df_lookback.iloc[i-1]['high'] and
                df_lookback.iloc[i]['high'] > df_lookback.iloc[i-2]['high'] and
                df_lookback.iloc[i]['high'] > df_lookback.iloc[i+1]['high'] and
                df_lookback.iloc[i]['high'] > df_lookback.iloc[i+2]['high']):
                swing_highs.append(df_lookback.iloc[i]['high'])
            
            # Swing low: lower than 2 candles on each side
            if (df_lookback.iloc[i]['low'] < df_lookback.iloc[i-1]['low'] and
                df_lookback.iloc[i]['low'] < df_lookback.iloc[i-2]['low'] and
                df_lookback.iloc[i]['low'] < df_lookback.iloc[i+1]['low'] and
                df_lookback.iloc[i]['low'] < df_lookback.iloc[i+2]['low']):
                swing_lows.append(df_lookback.iloc[i]['low'])
        
        # Cluster similar levels
        def cluster_levels(levels: List[float], proximity: float) -> List[float]:
            if not levels:
                return []
            
            levels_sorted = sorted(levels)
            clusters = []
            current_cluster = [levels_sorted[0]]
            
            for level in levels_sorted[1:]:
                if level <= current_cluster[-1] * (1 + proximity / 100):
                    current_cluster.append(level)
                else:
                    clusters.append(sum(current_cluster) / len(current_cluster))
                    current_cluster = [level]
            
            clusters.append(sum(current_cluster) / len(current_cluster))
            return clusters
        
        support_levels = cluster_levels(swing_lows, proximity_pct)
        resistance_levels = cluster_levels(swing_highs, proximity_pct)
        
        return {
            'support': sorted(support_levels, reverse=True)[:3],  # Top 3
            'resistance': sorted(resistance_levels)[:3]  # Top 3
        }
    
    @staticmethod
    def detect_breakout(df: pd.DataFrame, sr_levels: Dict[str, List[float]],
                       volume_multiplier: float = 1.5) -> Dict[str, Any]:
        """Detect breakouts from support/resistance levels.
        
        Args:
            df: DataFrame with OHLCV data
            sr_levels: Support and resistance levels
            volume_multiplier: Required volume increase for valid breakout
            
        Returns:
            Dictionary with breakout information
        """
        if df.empty or len(df) < 20:
            return {'breakout': False, 'direction': None}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Average volume
        avg_volume = df.tail(20)['volume'].mean()
        current_volume = latest['volume']
        
        # Check for volume confirmation
        volume_confirmed = current_volume > avg_volume * volume_multiplier
        
        # Check for resistance breakout (bullish)
        for resistance in sr_levels.get('resistance', []):
            if prev['close'] < resistance and latest['close'] > resistance:
                return {
                    'breakout': True,
                    'direction': 'BULLISH',
                    'level': resistance,
                    'volume_confirmed': volume_confirmed,
                    'strength': 'STRONG' if volume_confirmed else 'WEAK'
                }
        
        # Check for support breakdown (bearish)
        for support in sr_levels.get('support', []):
            if prev['close'] > support and latest['close'] < support:
                return {
                    'breakout': True,
                    'direction': 'BEARISH',
                    'level': support,
                    'volume_confirmed': volume_confirmed,
                    'strength': 'STRONG' if volume_confirmed else 'WEAK'
                }
        
        return {'breakout': False, 'direction': None}
    
    @staticmethod
    def calculate_volume_profile(df: pd.DataFrame, bins: int = 20) -> Dict[str, Any]:
        """Calculate volume profile (POC, Value Area).
        
        Args:
            df: DataFrame with OHLCV data
            bins: Number of price bins
            
        Returns:
            Dictionary with volume profile data
        """
        if df.empty or len(df) < 20:
            return {'poc': None, 'value_area_high': None, 'value_area_low': None}
        
        # Get price range
        price_min = df['low'].min()
        price_max = df['high'].max()
        
        # Create price bins
        bin_edges = np.linspace(price_min, price_max, bins + 1)
        
        # Assign volume to each bin based on where price traded
        bin_volumes = np.zeros(bins)
        
        for _, row in df.iterrows():
            # Find which bins this candle's range covers
            low_bin = np.digitize(row['low'], bin_edges) - 1
            high_bin = np.digitize(row['high'], bin_edges) - 1
            
            # Distribute volume across bins
            affected_bins = range(max(0, low_bin), min(bins, high_bin + 1))
            for bin_idx in affected_bins:
                bin_volumes[bin_idx] += row['volume'] / max(1, len(affected_bins))
        
        # Find Point of Control (highest volume bin)
        poc_bin = np.argmax(bin_volumes)
        poc_price = (bin_edges[poc_bin] + bin_edges[poc_bin + 1]) / 2
        
        # Calculate Value Area (70% of volume)
        total_volume = bin_volumes.sum()
        target_volume = total_volume * 0.70
        
        # Expand from POC until we reach 70% of volume
        value_area_bins = [poc_bin]
        accumulated_volume = bin_volumes[poc_bin]
        
        while accumulated_volume < target_volume and len(value_area_bins) < bins:
            # Check bins above and below
            above_bin = max(value_area_bins) + 1
            below_bin = min(value_area_bins) - 1
            
            above_volume = bin_volumes[above_bin] if above_bin < bins else 0
            below_volume = bin_volumes[below_bin] if below_bin >= 0 else 0
            
            if above_volume > below_volume and above_bin < bins:
                value_area_bins.append(above_bin)
                accumulated_volume += above_volume
            elif below_bin >= 0:
                value_area_bins.append(below_bin)
                accumulated_volume += below_volume
            else:
                break
        
        value_area_high = bin_edges[max(value_area_bins) + 1]
        value_area_low = bin_edges[min(value_area_bins)]
        
        return {
            'poc': poc_price,
            'value_area_high': value_area_high,
            'value_area_low': value_area_low
        }
    
    @staticmethod
    def analyze_structure(df: pd.DataFrame) -> Dict[str, Any]:
        """Comprehensive structure analysis.
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            Dictionary with structure analysis
        """
        # Find S/R levels
        sr_levels = StructureAnalysis.find_support_resistance(df)
        
        # Detect breakout
        breakout_info = StructureAnalysis.detect_breakout(df, sr_levels)
        
        # Volume profile
        volume_profile = StructureAnalysis.calculate_volume_profile(df)
        
        # Price action patterns
        if len(df) >= 3:
            latest = df.iloc[-1]
            prev1 = df.iloc[-2]
            prev2 = df.iloc[-3]
            
            # Higher highs / Lower lows
            higher_highs = latest['high'] > prev1['high'] > prev2['high']
            lower_lows = latest['low'] < prev1['low'] < prev2['low']
            
            if higher_highs and latest['close'] > prev1['close']:
                pattern = 'BULLISH_TREND'
            elif lower_lows and latest['close'] < prev1['close']:
                pattern = 'BEARISH_TREND'
            else:
                pattern = 'CONSOLIDATION'
        else:
            pattern = 'UNKNOWN'
        
        return {
            'support_levels': sr_levels['support'],
            'resistance_levels': sr_levels['resistance'],
            'breakout': breakout_info,
            'volume_profile': volume_profile,
            'pattern': pattern
        }
