"""Momentum indicators: RSI, MACD, Stochastic."""

import pandas as pd
import numpy as np
from typing import Dict, Any


class MomentumIndicators:
    """Calculate momentum-based technical indicators."""
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Calculate Relative Strength Index.
        
        Args:
            df: DataFrame with 'close' column
            period: RSI period
            
        Returns:
            DataFrame with RSI column added
        """
        df_result = df.copy()
        
        # Price changes
        delta = df_result['close'].diff()
        
        # Separate gains and losses
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Calculate average gain and loss
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        df_result['rsi'] = 100 - (100 / (1 + rs))
        
        return df_result
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, 
                      signal: int = 9) -> pd.DataFrame:
        """Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            df: DataFrame with 'close' column
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
            
        Returns:
            DataFrame with MACD, signal, and histogram columns
        """
        df_result = df.copy()
        
        # Calculate MACD line
        ema_fast = df_result['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df_result['close'].ewm(span=slow, adjust=False).mean()
        df_result['macd_line'] = ema_fast - ema_slow
        
        # Calculate signal line
        df_result['macd_signal'] = df_result['macd_line'].ewm(span=signal, adjust=False).mean()
        
        # Calculate histogram
        df_result['macd_histogram'] = df_result['macd_line'] - df_result['macd_signal']
        
        return df_result
    
    @staticmethod
    def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, 
                           d_period: int = 3) -> pd.DataFrame:
        """Calculate Stochastic Oscillator.
        
        Args:
            df: DataFrame with OHLCV data
            k_period: %K period
            d_period: %D period (SMA of %K)
            
        Returns:
            DataFrame with stochastic %K and %D columns
        """
        df_result = df.copy()
        
        # Calculate %K
        low_min = df_result['low'].rolling(window=k_period).min()
        high_max = df_result['high'].rolling(window=k_period).max()
        
        df_result['stoch_k'] = 100 * (df_result['close'] - low_min) / (high_max - low_min)
        
        # Calculate %D (SMA of %K)
        df_result['stoch_d'] = df_result['stoch_k'].rolling(window=d_period).mean()
        
        return df_result
    
    @staticmethod
    def analyze_momentum(df: pd.DataFrame, rsi_overbought: float = 70,
                        rsi_oversold: float = 30, stoch_overbought: float = 80,
                        stoch_oversold: float = 20) -> Dict[str, Any]:
        """Analyze momentum indicators.
        
        Args:
            df: DataFrame with momentum indicators
            rsi_overbought: RSI overbought threshold
            rsi_oversold: RSI oversold threshold
            stoch_overbought: Stochastic overbought threshold
            stoch_oversold: Stochastic oversold threshold
            
        Returns:
            Dictionary with momentum analysis
        """
        if df.empty or len(df) < 26:
            return {
                'rsi_signal': 'NEUTRAL',
                'macd_signal': 'NEUTRAL',
                'stoch_signal': 'NEUTRAL',
                'momentum_score': 0
            }
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else latest
        
        # RSI Analysis
        rsi_signal = 'NEUTRAL'
        if 'rsi' in df.columns:
            rsi_value = latest['rsi']
            if rsi_value > rsi_overbought:
                rsi_signal = 'OVERBOUGHT'
            elif rsi_value < rsi_oversold:
                rsi_signal = 'OVERSOLD'
            elif 40 <= rsi_value <= 60:
                rsi_signal = 'NEUTRAL'
            elif rsi_value > 50:
                rsi_signal = 'BULLISH'
            else:
                rsi_signal = 'BEARISH'
        
        # MACD Analysis
        macd_signal = 'NEUTRAL'
        macd_crossover = False
        if all(col in df.columns for col in ['macd_line', 'macd_signal', 'macd_histogram']):
            macd_line = latest['macd_line']
            signal_line = latest['macd_signal']
            histogram = latest['macd_histogram']
            
            # Check for crossover
            if prev['macd_line'] <= prev['macd_signal'] and macd_line > signal_line:
                macd_crossover = True
                macd_signal = 'BULLISH_CROSS'
            elif prev['macd_line'] >= prev['macd_signal'] and macd_line < signal_line:
                macd_crossover = True
                macd_signal = 'BEARISH_CROSS'
            elif macd_line > signal_line and histogram > 0:
                macd_signal = 'BULLISH'
            elif macd_line < signal_line and histogram < 0:
                macd_signal = 'BEARISH'
        
        # Stochastic Analysis
        stoch_signal = 'NEUTRAL'
        stoch_crossover = False
        if all(col in df.columns for col in ['stoch_k', 'stoch_d']):
            k_value = latest['stoch_k']
            d_value = latest['stoch_d']
            
            if k_value > stoch_overbought and d_value > stoch_overbought:
                stoch_signal = 'OVERBOUGHT'
            elif k_value < stoch_oversold and d_value < stoch_oversold:
                stoch_signal = 'OVERSOLD'
            elif prev['stoch_k'] <= prev['stoch_d'] and k_value > d_value:
                stoch_crossover = True
                stoch_signal = 'BULLISH_CROSS'
            elif prev['stoch_k'] >= prev['stoch_d'] and k_value < d_value:
                stoch_crossover = True
                stoch_signal = 'BEARISH_CROSS'
            elif k_value > d_value:
                stoch_signal = 'BULLISH'
            else:
                stoch_signal = 'BEARISH'
        
        # Calculate overall momentum score (-100 to +100)
        score = 0
        
        if rsi_signal == 'BULLISH':
            score += 25
        elif rsi_signal == 'BEARISH':
            score -= 25
        elif rsi_signal == 'OVERSOLD':
            score += 40
        elif rsi_signal == 'OVERBOUGHT':
            score -= 40
        
        if macd_signal == 'BULLISH_CROSS':
            score += 40
        elif macd_signal == 'BEARISH_CROSS':
            score -= 40
        elif macd_signal == 'BULLISH':
            score += 20
        elif macd_signal == 'BEARISH':
            score -= 20
        
        if stoch_signal == 'BULLISH_CROSS':
            score += 35
        elif stoch_signal == 'BEARISH_CROSS':
            score -= 35
        elif stoch_signal == 'OVERSOLD':
            score += 30
        elif stoch_signal == 'OVERBOUGHT':
            score -= 30
        elif stoch_signal == 'BULLISH':
            score += 15
        elif stoch_signal == 'BEARISH':
            score -= 15
        
        return {
            'rsi_signal': rsi_signal,
            'rsi_value': latest.get('rsi', None),
            'macd_signal': macd_signal,
            'macd_crossover': macd_crossover,
            'stoch_signal': stoch_signal,
            'stoch_crossover': stoch_crossover,
            'momentum_score': max(-100, min(100, score))
        }
