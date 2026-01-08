"""Trend indicators: EMA, VWAP."""

import pandas as pd
import numpy as np
from typing import Dict, Any


class TrendIndicators:
    """Calculate trend-based technical indicators."""
    
    @staticmethod
    def calculate_ema(df: pd.DataFrame, periods: list = [9, 21, 50, 200]) -> pd.DataFrame:
        """Calculate Exponential Moving Averages.
        
        Args:
            df: DataFrame with 'close' column
            periods: List of EMA periods
            
        Returns:
            DataFrame with EMA columns added
        """
        df_result = df.copy()
        
        for period in periods:
            df_result[f'ema_{period}'] = df_result['close'].ewm(span=period, adjust=False).mean()
        
        return df_result
    
    @staticmethod
    def calculate_vwap(df: pd.DataFrame, reset_period: str = 'daily') -> pd.DataFrame:
        """Calculate Volume Weighted Average Price.
        
        Args:
            df: DataFrame with OHLCV data
            reset_period: How often to reset VWAP ('daily', 'weekly', 'none')
            
        Returns:
            DataFrame with VWAP column added
        """
        df_result = df.copy()
        
        # Typical price
        df_result['typical_price'] = (df_result['high'] + df_result['low'] + df_result['close']) / 3
        df_result['tp_volume'] = df_result['typical_price'] * df_result['volume']
        
        if reset_period == 'daily':
            # Reset VWAP at the start of each day
            df_result['date'] = pd.to_datetime(df_result['timestamp']).dt.date
            df_result['cumul_tp_vol'] = df_result.groupby('date')['tp_volume'].cumsum()
            df_result['cumul_vol'] = df_result.groupby('date')['volume'].cumsum()
            df_result = df_result.drop('date', axis=1)
        else:
            # Running VWAP
            df_result['cumul_tp_vol'] = df_result['tp_volume'].cumsum()
            df_result['cumul_vol'] = df_result['volume'].cumsum()
        
        df_result['vwap'] = df_result['cumul_tp_vol'] / df_result['cumul_vol']
        
        # Clean up temporary columns
        df_result = df_result.drop(['typical_price', 'tp_volume', 'cumul_tp_vol', 'cumul_vol'], axis=1)
        
        return df_result
    
    @staticmethod
    def analyze_trend(df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze overall trend based on EMAs and VWAP.
        
        Args:
            df: DataFrame with EMA and VWAP columns
            
        Returns:
            Dictionary with trend analysis
        """
        if df.empty or len(df) < 200:
            return {
                'trend': 'UNKNOWN',
                'strength': 0,
                'ema_alignment': False,
                'price_vs_vwap': 'NEUTRAL'
            }
        
        latest = df.iloc[-1]
        
        # Check EMA alignment (bullish: EMA9 > EMA21 > EMA50 > EMA200)
        ema_cols = ['ema_9', 'ema_21', 'ema_50', 'ema_200']
        ema_available = all(col in df.columns for col in ema_cols)
        
        if ema_available:
            ema_values = [latest[col] for col in ema_cols]
            bullish_alignment = all(ema_values[i] > ema_values[i+1] for i in range(len(ema_values)-1))
            bearish_alignment = all(ema_values[i] < ema_values[i+1] for i in range(len(ema_values)-1))
            
            if bullish_alignment:
                trend = 'BULLISH'
                strength = 80
            elif bearish_alignment:
                trend = 'BEARISH'
                strength = 80
            else:
                # Partial alignment - check short-term trend
                if latest['ema_9'] > latest['ema_21']:
                    trend = 'BULLISH'
                    strength = 50
                elif latest['ema_9'] < latest['ema_21']:
                    trend = 'BEARISH'
                    strength = 50
                else:
                    trend = 'NEUTRAL'
                    strength = 30
        else:
            trend = 'UNKNOWN'
            strength = 0
        
        # Price vs VWAP
        price_vs_vwap = 'NEUTRAL'
        if 'vwap' in df.columns:
            if latest['close'] > latest['vwap'] * 1.01:
                price_vs_vwap = 'ABOVE'
            elif latest['close'] < latest['vwap'] * 0.99:
                price_vs_vwap = 'BELOW'
        
        # Golden/Death cross detection
        golden_cross = False
        death_cross = False
        if 'ema_50' in df.columns and 'ema_200' in df.columns and len(df) >= 2:
            prev = df.iloc[-2]
            if prev['ema_50'] <= prev['ema_200'] and latest['ema_50'] > latest['ema_200']:
                golden_cross = True
            elif prev['ema_50'] >= prev['ema_200'] and latest['ema_50'] < latest['ema_200']:
                death_cross = True
        
        return {
            'trend': trend,
            'strength': strength,
            'ema_alignment': bullish_alignment if ema_available else False,
            'price_vs_vwap': price_vs_vwap,
            'golden_cross': golden_cross,
            'death_cross': death_cross
        }
