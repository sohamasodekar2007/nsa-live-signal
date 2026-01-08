"""Multi-timeframe analysis for trade confirmation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime

from data.fetcher import NSEDataFetcher
from indicators.trend import TrendIndicators
from indicators.momentum import MomentumIndicators


class MultiTimeframeAnalyzer:
    """Analyze multiple timeframes for trade confirmation."""
    
    def __init__(self, data_fetcher: NSEDataFetcher):
        """Initialize multi-timeframe analyzer.
        
        Args:
            data_fetcher: Data fetcher instance
        """
        self.data_fetcher = data_fetcher
    
    def analyze_timeframes(self, symbol: str, 
                          higher_tf: str = "15m",
                          lower_tf: str = "5m") -> Dict[str, Any]:
        """Analyze multiple timeframes for alignment.
        
        Args:
            symbol: Stock symbol
            higher_tf: Higher timeframe (15m, 1h, 1d)
            lower_tf: Lower timeframe (1m, 5m)
            
        Returns:
            Dictionary with multi-timeframe analysis
        """
        # Fetch data for both timeframes
        htf_data = self.data_fetcher.fetch_historical(
            symbol, period="5d", interval=higher_tf
        )
        ltf_data = self.data_fetcher.fetch_historical(
            symbol, period="1d", interval=lower_tf
        )
        
        if htf_data is None or ltf_data is None:
            return {
                'aligned': False,
                'reason': 'Insufficient data',
                'htf_trend': 'UNKNOWN',
                'ltf_momentum': 'UNKNOWN'
            }
        
        # Calculate indicators for higher timeframe
        htf_data = TrendIndicators.calculate_ema(htf_data, [50, 200])
        htf_data = TrendIndicators.calculate_vwap(htf_data)
        htf_trend = TrendIndicators.analyze_trend(htf_data)
        
        # Calculate indicators for lower timeframe
        ltf_data = TrendIndicators.calculate_ema(ltf_data, [9, 21])
        ltf_data = MomentumIndicators.calculate_rsi(ltf_data)
        ltf_data = MomentumIndicators.calculate_macd(ltf_data)
        ltf_momentum = MomentumIndicators.analyze_momentum(ltf_data)
        
        # Check alignment
        htf_bullish = htf_trend['trend'] == 'BULLISH'
        htf_bearish = htf_trend['trend'] == 'BEARISH'
        
        ltf_momentum_bullish = ltf_momentum['momentum_score'] > 30
        ltf_momentum_bearish = ltf_momentum['momentum_score'] < -30
        
        # Price above key levels (higher timeframe)
        htf_latest = htf_data.iloc[-1]
        price_above_ema50 = htf_latest['close'] > htf_latest.get('ema_50', 0)
        price_above_ema200 = htf_latest['close'] > htf_latest.get('ema_200', 0)
        price_above_vwap = htf_latest['close'] > htf_latest.get('vwap', 0)
        
        # Determine alignment
        aligned = False
        direction = 'NEUTRAL'
        reason = []
        
        if htf_bullish and ltf_momentum_bullish:
            if price_above_ema50 and price_above_vwap:
                aligned = True
                direction = 'BULLISH'
                reason.append("HTF bullish trend + LTF bullish momentum")
                if price_above_ema200:
                    reason.append("Price above EMA-200")
        
        elif htf_bearish and ltf_momentum_bearish:
            if not price_above_ema50 and not price_above_vwap:
                aligned = True
                direction = 'BEARISH'
                reason.append("HTF bearish trend + LTF bearish momentum")
        
        else:
            reason.append("Timeframe misalignment")
        
        return {
            'aligned': aligned,
            'direction': direction,
            'reason': ' | '.join(reason) if reason else 'No clear alignment',
            'htf_trend': htf_trend['trend'],
            'htf_strength': htf_trend['strength'],
            'ltf_momentum_score': ltf_momentum['momentum_score'],
            'price_above_ema50': price_above_ema50,
            'price_above_ema200': price_above_ema200,
            'price_above_vwap': price_above_vwap,
            'htf_data': htf_data,
            'ltf_data': ltf_data
        }
