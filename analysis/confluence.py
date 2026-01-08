"""Multi-layer technical confluence calculator."""

import pandas as pd
from typing import Dict, Any


class ConfluenceCalculator:
    """Calculate multi-indicator confluence scores."""
    
    def __init__(self):
        """ Initialize confluence calculator."""
        pass
    
    def calculate_layer_scores(self, 
                               trend_analysis: Dict[str, Any],
                               momentum_analysis: Dict[str, Any],
                               volatility_analysis: Dict[str, Any],
                               structure_analysis: Dict[str, Any],
                               current_price: float) -> Dict[str, float]:
        """Calculate individual layer scores.
        
        Args:
            trend_analysis: Trend indicator analysis
            momentum_analysis: Momentum indicator analysis
            volatility_analysis: Volatility indicator analysis
            structure_analysis: Structure analysis
            current_price: Current market price
            
        Returns:
            Dictionary with layer scores (0-100 each)
        """
        scores = {
            'trend': 0,
            'momentum': 0,
            'volatility': 0,
            'structure': 0
        }
        
        # 1. Trend Layer Score (0-100)
        trend_score = 0
        trend_type = trend_analysis.get('trend', 'UNKNOWN')
        trend_strength = trend_analysis.get('strength', 0)
        price_vs_vwap = trend_analysis.get('price_vs_vwap', 'NEUTRAL')
        
        if trend_type == 'BULLISH':
            trend_score += trend_strength * 0.7  # Max 56
            if price_vs_vwap == 'ABOVE':
                trend_score += 20
            if trend_analysis.get('golden_cross', False):
                trend_score += 24
        elif trend_type == 'BEARISH':
            trend_score -= trend_strength * 0.7
            if price_vs_vwap == 'BELOW':
                trend_score -= 20
            if trend_analysis.get('death_cross', False):
                trend_score -= 24
        
        scores['trend'] = max(-100, min(100, trend_score))
        
        # 2. Momentum Layer Score (0-100)
        momentum_score = momentum_analysis.get('momentum_score', 0)
        scores['momentum'] = max(-100, min(100, momentum_score))
        
        # 3. Volatility Layer Score (0-100)
        volatility_score = 0
        bb_position = volatility_analysis.get('bb_position', 'NEUTRAL')
        vol_regime = volatility_analysis.get('regime', 'UNKNOWN')
        
        if bb_position == 'BELOW_LOWER':
            volatility_score += 40  # Oversold condition
        elif bb_position == 'ABOVE_UPPER':
            volatility_score -= 40  # Overbought condition
        elif bb_position == 'LOWER_HALF':
            volatility_score += 15
        elif bb_position == 'UPPER_HALF':
            volatility_score -= 15
        
        # Favor low volatility for entries (squeeze = potential breakout)
        if volatility_analysis.get('bb_squeeze', False):
            volatility_score += 20
        
        # Penalize extremely high volatility
        atr_percentile = volatility_analysis.get('atr_percentile', 50)
        if atr_percentile > 90:
            volatility_score -= 20
        
        scores['volatility'] = max(-100, min(100, volatility_score))
        
        # 4. Structure Layer Score (0-100)
        structure_score = 0
        
        # Breakout detection
        breakout = structure_analysis.get('breakout', {})
        if breakout.get('breakout', False):
            direction = breakout.get('direction')
            strength = breakout.get('strength', 'WEAK')
            
            if direction == 'BULLISH':
                structure_score += 60 if strength == 'STRONG' else 35
            elif direction == 'BEARISH':
                structure_score -= 60 if strength == 'STRONG' else 35
        
        # Support/Resistance proximity
        support_levels = structure_analysis.get('support_levels', [])
        resistance_levels = structure_analysis.get('resistance_levels', [])
        
        for support in support_levels:
            if abs(current_price - support) / support < 0.01:  # Within 1%
                structure_score += 25
                break
        
        for resistance in resistance_levels:
            if abs(current_price - resistance) / resistance < 0.01:  # Within 1%
                structure_score -= 25
                break
        
        # Pattern score
        pattern = structure_analysis.get('pattern', 'UNKNOWN')
        if pattern == 'BULLISH_TREND':
            structure_score += 20
        elif pattern == 'BEARISH_TREND':
            structure_score -= 20
        
        scores['structure'] = max(-100, min(100, structure_score))
        
        return scores
    
    def calculate_confluence(self, 
                           layer_scores: Dict[str, float],
                           weights: Dict[str, float]) -> Dict[str, Any]:
        """Calculate weighted confluence score.
        
        Args:
            layer_scores: Individual layer scores (-100 to +100)
            weights: Layer weights (must sum to 1.0)
            
        Returns:
            Dictionary with confluence score and details
        """
        # Weighted score
        weighted_score = 0
        for layer, score in layer_scores.items():
            weight = weights.get(f'{layer}_indicators', 0.25)
            weighted_score += score * weight
        
        # Normalize to 0-100 scale (from -100 to +100)
        confluence_score = (weighted_score + 100) / 2
        
        # Determine signal direction and strength
        if weighted_score > 40:
            direction = 'BULLISH'
            strength = 'STRONG' if weighted_score > 70 else 'MODERATE'
        elif weighted_score < -40:
            direction = 'BEARISH'
            strength = 'STRONG' if weighted_score < -70 else 'MODERATE'
        else:
            direction = 'NEUTRAL'
            strength = 'WEAK'
        
        # Agreement factor (how many layers agree)
        bullish_layers = sum(1 for score in layer_scores.values() if score > 20)
        bearish_layers = sum(1 for score in layer_scores.values() if score < -20)
        total_layers = len(layer_scores)
        
        agreement = max(bullish_layers, bearish_layers) / total_layers * 100
        
        return {
            'score': confluence_score,
            'weighted_score': weighted_score,
            'direction': direction,
            'strength': strength,
            'agreement': agreement,
            'layer_scores': layer_scores,
            'weights': weights
        }
