"""Risk-based quantity calculator (0.5-1% max risk per trade)."""

from typing import Dict, Any


class QuantityCalculator:
    """Calculate position size based on risk percentage."""
    
    @staticmethod
    def calculate_quantity(total_capital: float,
                          entry_price: float,
                          stop_loss: float,
                          risk_per_trade_pct: float = 1.0,
                          confidence: float = 70.0,
                          max_position_value_pct: float = 10.0) -> Dict[str, Any]:
        """Calculate position quantity based on risk.
        
        Formula: Quantity = (Max Risk Amount) / (Entry Price - Stop Loss)
        
        Args:
            total_capital: Total portfolio capital
            entry_price: Entry price per share
            stop_loss: Stop-loss price per share
            risk_per_trade_pct: Max risk percentage (0.5-1%)
            confidence: Signal confidence (adjusts risk)
            max_position_value_pct: Max position size as % of capital
            
        Returns:
            Dictionary with quantity and risk details
        """
        # Calculate maximum risk amount in rupees
        base_risk_amount = total_capital * (risk_per_trade_pct / 100)
        
        # Adjust risk based on confidence
        # Lower confidence = reduce risk
        # 70% confidence = 0.7x base risk
        # 100% confidence = 1.0x base risk
        confidence_multiplier = min(1.0, max(0.5, confidence / 100))
        adjusted_risk_amount = base_risk_amount * confidence_multiplier
        
        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)
        
        if risk_per_share == 0:
            return {
                'quantity': 0,
                'valid': False,
                'reason': 'Invalid stop-loss: zero risk per share',
                'capital_required': 0,
                'risk_amount': 0
            }
        
        # Calculate quantity
        quantity = int(adjusted_risk_amount / risk_per_share)
        
        # Calculate required capital
        capital_required = quantity * entry_price
        
        # Check max position size limit
        max_position_value = total_capital * (max_position_value_pct / 100)
        
        if capital_required > max_position_value:
            # Reduce quantity to fit within max position size
            quantity = int(max_position_value / entry_price)
            capital_required = quantity * entry_price
            
            # Recalculate actual risk with reduced quantity
            actual_risk = quantity * risk_per_share
            reason = f'Position capped at {max_position_value_pct}% of capital'
        else:
            actual_risk = adjusted_risk_amount
            reason = 'Quantity calculated based on risk'
        
        # Validate quantity is positive
        if quantity <= 0:
            return {
                'quantity': 0,
                'valid': False,
                'reason': 'Insufficient capital for minimum position',
                'capital_required': capital_required,
                'risk_amount': 0
            }
        
        # Calculate actual risk percentage
        actual_risk_pct = (actual_risk / total_capital) * 100
        
        # Validate risk is within acceptable bounds
        if actual_risk_pct > risk_per_trade_pct * 1.2:  # Allow 20% tolerance
            return {
                'quantity': 0,
                'valid': False,
                'reason': f'Risk {actual_risk_pct:.2f}% exceeds limit {risk_per_trade_pct}%',
                'capital_required': capital_required,
                'risk_amount': actual_risk
            }
        
        return {
            'quantity': quantity,
            'valid': True,
            'reason': reason,
            'capital_required': capital_required,
            'risk_amount': actual_risk,
            'risk_pct': actual_risk_pct,
            'risk_per_share': risk_per_share,
            'base_risk_pct': risk_per_trade_pct,
            'confidence_multiplier': confidence_multiplier,
            'position_value_pct': (capital_required / total_capital) * 100
        }
