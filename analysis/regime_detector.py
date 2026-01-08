"""Market regime detection with dynamic indicator weighting."""

import pandas as pd
import yaml
from typing import Dict, Any
from pathlib import Path

from core.enums import MarketRegime


class RegimeDetector:
    """Detect and classify market regimes."""
    
    def __init__(self, config_path: str = "config/indicators_config.yaml"):
        """Initialize the regime detector.
        
        Args:
            config_path: Path to indicators configuration
        """
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            # Default config
            self.config = {
                'regime': {
                    'adx': {
                        'period': 14,
                        'trend_threshold': 25,
                        'strong_trend_threshold': 40,
                        'range_threshold': 20
                    }
                },
                'weights': {
                    'trend': {
                        'trend_indicators': 0.40,
                        'momentum_indicators': 0.30,
                        'volatility_indicators': 0.15,
                        'structure_indicators': 0.15
                    },
                    'range': {
                        'trend_indicators': 0.15,
                        'momentum_indicators': 0.40,
                        'volatility_indicators': 0.20,
                        'structure_indicators': 0.25
                    },
                    'high_volatility': {
                        'trend_indicators': 0.20,
                        'momentum_indicators': 0.25,
                        'volatility_indicators': 0.25,
                        'structure_indicators': 0.30
                    }
                }
            }
    
    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Calculate Average Directional Index (ADX).
        
        Args:
            df: DataFrame with OHLC data
            period: ADX period
            
        Returns:
            DataFrame with ADX, +DI, -DI columns added
        """
        df_result = df.copy()
        
        # True Range
        high_low = df_result['high'] - df_result['low']
        high_close = abs(df_result['high'] - df_result['close'].shift(1))
        low_close = abs(df_result['low'] - df_result['close'].shift(1))
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Directional Movement
        plus_dm = df_result['high'] - df_result['high'].shift(1)
        minus_dm = df_result['low'].shift(1) - df_result['low']
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        plus_dm[(plus_dm < minus_dm)] = 0
        minus_dm[(minus_dm < plus_dm)] = 0
        
       # Smoothed True Range and DM
        atr = true_range.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # Directional Index
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        
        # ADX (smoothed DX)
        df_result['adx'] = dx.rolling(window=period).mean()
        df_result['plus_di'] = plus_di
        df_result['minus_di'] = minus_di
        
        return df_result
    
    def detect_regime(self, df: pd.DataFrame, 
                     trend_analysis: Dict[str, Any],
                     volatility_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Detect current market regime.
        
        Args:
            df: DataFrame with price data and indicators
            trend_analysis: Output from TrendIndicators.analyze_trend()
            volatility_analysis: Output from VolatilityIndicators.analyze_volatility()
            
        Returns:
            Dictionary with regime classification and weights
        """
        if df.empty or len(df) < 50:
            return {
                'regime': MarketRegime.UNKNOWN,
                'confidence': 0,
                'weights': self.config['weights']['trend']
            }
        
        # Calculate ADX if not present
        if 'adx' not in df.columns:
            df = self.calculate_adx(df)
        
        latest = df.iloc[-1]
        adx_value = latest.get('adx', 0)
        
        adx_config = self.config['regime']['adx']
        trend_threshold = adx_config['trend_threshold']
        strong_trend_threshold = adx_config['strong_trend_threshold']
        range_threshold = adx_config['range_threshold']
        
        # Regime classification logic
        regime = MarketRegime.UNKNOWN
        confidence = 0
        
        # Check volatility first
        atr_percentile = volatility_analysis.get('atr_percentile', 50)
        bb_squeeze = volatility_analysis.get('bb_squeeze', False)
        
        if atr_percentile > 80:
            # High volatility regime
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = 75
        
        elif adx_value > strong_trend_threshold:
            # Strong trend regime
            regime = MarketRegime.TREND
            confidence = 90
            
        elif adx_value > trend_threshold:
            # Moderate trend regime
            # Verify with EMA alignment
            ema_aligned = trend_analysis.get('ema_alignment', False)
            if ema_aligned:
                regime = MarketRegime.TREND
                confidence = 75
            else:
                regime = MarketRegime.TREND
                confidence = 60
        
        elif adx_value < range_threshold or bb_squeeze:
            # Range-bound / consolidation regime
            regime = MarketRegime.RANGE
            confidence = 70
        
        else:
            # Undefined regime - use trend as default
            regime = MarketRegime.TREND
            confidence = 40
        
        # Get appropriate weights for this regime
        regime_key = regime.value.lower() if regime != MarketRegime.UNKNOWN else 'trend'
        weights = self.config['weights'].get(regime_key, self.config['weights']['trend'])
        
        return {
            'regime': regime,
            'confidence': confidence,
            'adx': adx_value,
            'weights': weights,
            'details': {
                'atr_percentile': atr_percentile,
                'bb_squeeze': bb_squeeze,
                'trend_strength': trend_analysis.get('strength', 0)
            }
        }
