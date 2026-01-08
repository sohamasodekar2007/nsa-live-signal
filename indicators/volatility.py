"""Volatility indicators: ATR, Bollinger Bands."""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple


class VolatilityIndicators:
    """Calculate volatility-based technical indicators."""
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Calculate Average True Range.
        
        Args:
            df: DataFrame with OHLC data
            period: ATR period
            
        Returns:
            DataFrame with ATR column added
        """
        df_result = df.copy()
        
        # True Range components
        high_low = df_result['high'] - df_result['low']
        high_close = np.abs(df_result['high'] - df_result['close'].shift(1))
        low_close = np.abs(df_result['low'] - df_result['close'].shift(1))
        
        # True Range
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Average True Range
        df_result['atr'] = true_range.rolling(window=period).mean()
        
        return df_result
    
    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, 
                                 std_dev: float = 2.0) -> pd.DataFrame:
        """Calculate Bollinger Bands.
        
        Args:
            df: DataFrame with 'close' column
            period: Moving average period
            std_dev: Number of standard deviations
            
        Returns:
            DataFrame with Bollinger Bands columns added
        """
        df_result = df.copy()
        
        # Middle band (SMA)
        df_result['bb_middle'] = df_result['close'].rolling(window=period).mean()
        
        # Standard deviation
        rolling_std = df_result['close'].rolling(window=period).std()
        
        # Upper and lower bands
        df_result['bb_upper'] = df_result['bb_middle'] + (rolling_std * std_dev)
        df_result['bb_lower'] = df_result['bb_middle'] - (rolling_std * std_dev)
        
        # Bandwidth (volatility measure)
        df_result['bb_bandwidth'] = (df_result['bb_upper'] - df_result['bb_lower']) / df_result['bb_middle']
        
        return df_result
    
    @staticmethod
    def calculate_stop_loss_target(current_price: float, atr: float, 
                                   sl_multiplier: float = 1.5,
                                   target_multipliers: list = [2.0, 3.0],
                                   signal_type: str = 'BUY') -> Dict[str, Any]:
        """Calculate stop-loss and target prices based on ATR.
        
        Args:
            current_price: Current market price
            atr: Average True Range value
            sl_multiplier: ATR multiplier for stop-loss
            target_multipliers: ATR multipliers for targets
            signal_type: 'BUY' or 'SELL'
            
        Returns:
            Dictionary with stop-loss and target prices
        """
        if signal_type == 'BUY':
            stop_loss = current_price - (atr * sl_multiplier)
            targets = [current_price + (atr * mult) for mult in target_multipliers]
            risk = current_price - stop_loss
        else:  # SELL
            stop_loss = current_price + (atr * sl_multiplier)
            targets = [current_price - (atr * mult) for mult in target_multipliers]
            risk = stop_loss - current_price
        
        # Calculate risk-reward ratios
        rewards = [abs(target - current_price) for target in targets]
        risk_rewards = [reward / risk if risk > 0 else 0 for reward in rewards]
        
        return {
            'entry': current_price,
            'stop_loss': stop_loss,
            'targets': targets,
            'risk': risk,
            'rewards': rewards,
            'risk_reward_ratios': risk_rewards,
            'best_risk_reward': max(risk_rewards) if risk_rewards else 0
        }
    
    @staticmethod
    def analyze_volatility(df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze volatility indicators.
        
        Args:
            df: DataFrame with volatility indicators
            
        Returns:
            Dictionary with volatility analysis
        """
        if df.empty or len(df) < 20:
            return {
                'regime': 'UNKNOWN',
                'atr_percentile': 0,
                'bb_position': 'NEUTRAL',
                'bb_squeeze': False
            }
        
        latest = df.iloc[-1]
        
        # ATR Percentile
        atr_percentile = 0
        if 'atr' in df.columns:
            current_atr = latest['atr']
            atr_series = df['atr'].dropna()
            if len(atr_series) > 0:
                atr_percentile = (atr_series < current_atr).sum() / len(atr_series) * 100
        
        # Volatility Regime
        if atr_percentile > 80:
            regime = 'HIGH_VOLATILITY'
        elif atr_percentile > 50:
            regime = 'MODERATE_VOLATILITY'
        else:
            regime = 'LOW_VOLATILITY'
        
        # Bollinger Band Position
        bb_position = 'NEUTRAL'
        if all(col in df.columns for col in ['bb_upper', 'bb_middle', 'bb_lower']):
            price = latest['close']
            upper = latest['bb_upper']
            lower = latest['bb_lower']
            middle = latest['bb_middle']
            
            if price > upper:
                bb_position = 'ABOVE_UPPER'
            elif price < lower:
                bb_position = 'BELOW_LOWER'
            elif price > middle:
                bb_position = 'UPPER_HALF'
            else:
                bb_position = 'LOWER_HALF'
        
        # Bollinger Band Squeeze (low volatility condition)
        bb_squeeze = False
        if 'bb_bandwidth' in df.columns:
            current_bw = latest['bb_bandwidth']
            bw_series = df['bb_bandwidth'].dropna()
            if len(bw_series) > 0:
                bw_percentile = (bw_series < current_bw).sum() / len(bw_series) * 100
                bb_squeeze = bw_percentile < 20  # Bottom 20% = squeeze
        
        return {
            'regime': regime,
            'atr_value': latest.get('atr', None),
            'atr_percentile': atr_percentile,
            'bb_position': bb_position,
            'bb_squeeze': bb_squeeze,
            'bb_bandwidth': latest.get('bb_bandwidth', None)
        }
