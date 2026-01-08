# Enhanced Rule-Driven Execution Engine - User Guide

## Overview

The NSE Trading Engine now includes a sophisticated **rule-driven execution system** that enforces strict multi-factor confirmation before allowing any trade. This system prioritizes **capital protection, statistical edge, and decision accuracy** over trade frequency.

---

## Key Features

### 1. **Multi-Timeframe Confirmation**
Every trade requires alignment between:
- **Higher Timeframe (15m/1h/1d)**: Establishes trend direction
- **Lower Timeframe (1m/5m)**: Confirms momentum entry

**BUY Conditions**:
- HTF bullish trend + LTF bullish momentum
- Price **above** EMA-50, EMA-200, and VWAP
- Volume expansion confirms participation

**SELL/SHORT Conditions**:
- HTF bearish trend + LTF bearish momentum
- Price **below** EMA-50 and VWAP
- Momentum divergence or support failure confirmed

**HOLD Enforced When**:
- Timeframes misaligned
- Market regime sideways/consolidating
- Volatility abnormal (ATR > 95th percentile)

### 2. **Entry Type Logic**

The system identifies three entry types:

#### **Pullback Entry**
- Price pulls back to EMA-21 or VWAP in trending market
- Entry near **support** (bullish) or **resistance** (bearish)
- **Limit order** preferred for better pricing

#### **Breakout-Retest Entry**
- Breakout from resistance/support with volume confirmation
- Wait for retest of breakout level
- **Market order** if volume confirmed, limit order otherwise

#### **Momentum Continuation**
- Strong trend (strength > 70) with volume expansion
- Price making higher highs (bullish) or lower lows (bearish)
- **Market order** to capture momentum

### 3. **Hybrid Stop-Loss System**

Stop-loss calculated using **maximum** of:
1. **ATR-Based**: Entry ± (1.5 × ATR)
2. **Swing High/Low**: Recent 20-candle high/low
3. **VWAP Invalidation**: 0.5% beyond VWAP

**Constraints**:
- Minimum stop: 0.5% from entry
- Maximum stop: 5% from entry
- **Non-negotiable** - auto-exit if hit

### 4. **Target & Partial Profit Booking**

**Profit Booking Plan**:
- **Target 1 (1R)**: Book **50%** of position
- **Target 2 (2R)**: Book **30%** more (80% total booked)
- **Target 3 (3R)**: **Trail** remaining 20% using ATR or exit

**Minimum R:R**: 2:1 (reward must be 2x risk minimum)

**Structure-Based Targets**:
- System identifies nearby resistance/support levels
- Adjusts targets to align with structure

**Trailing Stop**:
- Activated after 1% profit
- Trail using 2× ATR from current price
- Never goes below entry (protects profits)

### 5. **Risk-Based Quantity Calculation**

**Formula**:
```
Quantity = (Max Risk Amount) ÷ (Entry Price - Stop Loss)
```

**Risk Parameters**:
- **Max Risk Per Trade**: 0.5-1% of total capital (configurable)
- **Confidence Adjustment**: Lower confidence = Reduced risk
  - 70% confidence = 0.7× base risk
  - 100% confidence = 1.0× base risk
- **Position Size Cap**: Max 10% of capital per trade

**Example**:
- Capital: ₹1,00,000
- Risk: 1% = ₹1,000
- Entry: ₹500, Stop: ₹475
- Risk per share: ₹25
- Quantity: 1,000 ÷ 25 = **40 shares**
- Capital used: 40 × ₹500 = **₹20,000 (20%)**

### 6 **Trade Lifecycle Management**

Every trade follows complete lifecycle:

1. **Signal Generated**: Initial signal creation
2. **Validated**: Passes all validation checks
3. **Entry Pending**: Order placed, awaiting execution
4. **Entered**: Position opened
5. **Monitoring**: Active position tracking
6. **Partial Exit 1**: 50% booked at T1
7. **Partial Exit 2**: 30% booked at T2
8. **Trailing**: 20% trailing to T3
9. **Exited**: Position fully closed
10. **Rejected**: Failed validation (with reason)

**All stages logged** with timestamp and reasoning.

### 7. **Enhanced Validation Rules**

**Signal must pass ALL of these**:

✅ **Multi-timeframe aligned** (HTF trend + LTF momentum)  
✅ **Confidence ≥ 70%** (strict threshold)  
✅ **Risk-reward ≥ 2:1** (minimum)  
✅ **Valid entry type** identified  
✅ **Price above/below key levels** (EMA-50, VWAP)  
✅ **Volume confirms** participation  
✅ **Volatility tradable** (ATR < 95th percentile)  
✅ **Regime not unknown** (trend/range/volatility)  
✅ **Stop-loss reasonable** (0.5-5% range)  
✅ **Capital available** for position  
✅ **Risk limits not breached**  
✅ **Daily loss limit okay**  
✅ **Max positions not exceeded**  
✅ **Trade cooldown passed**  

**If ANY check fails → HOLD with explicit reason logged**

---

## Trade Output Format

### **EXECUTE TRADE**
```
{
  'ACTION': 'EXECUTE_TRADE',
  'trade_id': 'T00001',
  'symbol': 'RELIANCE.NS',
  'direction': 'BUY',
  'entry_price': 2450.00,
  'entry_type': 'PULLBACK',
  'use_limit_order': true,
  'quantity': 40,
  'stop_loss': 2400.00,
  'targets': [
    {'price': 2500.00, 'rr_ratio': 1.0, 'book_percentage': 50, 'type': 'TARGET_1'},
    {'price': 2550.00, 'rr_ratio': 2.0, 'book_percentage': 30, 'type': 'TARGET_2'},
    {'price': 2600.00, 'rr_ratio': 3.0, 'book_percentage': 20, 'type': 'TARGET_3_TRAIL'}
  ],
  'confidence': 78.5,
  'risk_reward': 2.0,
  'capital_required': 98000.00,
  'risk_amount': 2000.00,
  'risk_pct': 1.0,
  'reasoning': 'MTF: HTF bullish + LTF momentum | Signal: BUY @ 78% | Entry: PULLBACK to VWAP | Stop: ATR @ 2400 (2.0%) | Targets: T1: 2500 (50%), T2: 2550 (30%), T3: 2600 (20% trail) | Risk: ₹2000 (1.0%), Qty: 40'
}
```

### **HOLD Decision**
```
{
  'ACTION': 'HOLD',
  'symbol': 'RELIANCE.NS',
  'reason': 'Confidence 65.2% below threshold 70%',
  'validation_passed': false
}
```

---

## Usage Example

```python
from execution.execution_engine import RuleDrivenExecutionEngine

# Initialize (portfolio, risk_manager, data_fetcher already created)
engine = RuleDrivenExecutionEngine(
    portfolio=portfolio,
    risk_manager=risk_manager,
    data_fetcher=data_fetcher,
    min_confidence=70.0,  # 70% threshold
    min_rr=2.0,  # Minimum 1:2 R:R
    risk_per_trade_pct=1.0  # 1% risk per trade
)

# Evaluate trade opportunity
trade_order = engine.evaluate_trade_opportunity(
    symbol='RELIANCE.NS',
    higher_tf='15m',  # Higher timeframe for trend
    lower_tf='5m'     # Lower timeframe for entry
)

# Check result
if trade_order['ACTION'] == 'EXECUTE_TRADE':
    print(f"✅ TRADE APPROVED")
    print(f"Symbol: {trade_order['symbol']}")
    print(f"Direction: {trade_order['direction']}")
    print(f"Entry: ₹{trade_order['entry_price']:.2f}")
    print(f"Quantity: {trade_order['quantity']}")
    print(f"Stop: ₹{trade_order['stop_loss']:.2f}")
    print(f"Confidence: {trade_order['confidence']:.1f}%")
    print(f"Reasoning: {trade_order['reasoning']}")
    
    # Execute trade
    success = engine.execute_trade(trade_order)
else:
    print(f"⏸️ HOLD: {trade_order['reason']}")
```

---

## Risk Management Integration

The execution engine enforces existing risk rules:

- **Max Daily Loss**: 3% → Trading halted if breached
- **Max Open Positions**: 8 trades maximum
- **Trade Frequency**: Max 3 trades/stock/day
- **Signal Cooldown**: Prevents over-trading same symbol
- **Position Sizing**: ATR-based or fixed, confidence-adjusted

---

## Decision Audit Trail

Every decision is logged:

```
[2026-01-06 13:05:23] RELIANCE.NS | HOLD - Multi-timeframe misalignment: HTF bearish vs LTF bullish
[2026-01-06 13:06:45] TCS.NS | HOLD - Confidence 65% below threshold 70%
[2026-01-06 13:08:12] INFY.NS | SIGNAL: BUY @ 78% confidence | Entry: PULLBACK | Stop: ATR
[2026-01-06 13:08:15] Trade T00015 EXECUTED: INFY.NS | BUY 50 @ ₹1450.00 | SL: ₹1425.00
```

---

## Key Differences from Basic System

| Feature | Basic System | Enhanced System |
|---------|-------------|-----------------|
| **Confidence Threshold** | 60% | **70%** (stricter) |
| **Timeframe Analysis** | Single TF | **Multi-TF** (HTF+LTF) |
| **Entry Types** | Generic | **Pullback/Breakout/Momentum** |
| **Stop-Loss** | ATR only | **Hybrid** (ATR + Swing + VWAP) |
| **Targets** | Fixed R:R | **Partial booking** (50/30/20) |
| **Quantity** | Fixed or simple | **Risk-based** (0.5-1%) |
| **Lifecycle** | Basic tracking | **Complete** (10 stages) |
| **Validation** | 5 checks | **14 checks** (comprehensive) |

---

## Best Practices

1. **Start with Higher Confidence**: Use 75-80% threshold initially
2. **Lower Risk**: Start with 0.5% risk per trade
3. **Prefer Limit Orders**: Don't chase prices
4. **Honor Partial Booking**: Discipline in profit-taking
5. **Never Override Stop-Loss**: System enforces automatically
6. **Review Rejection Reasons**: Learn from HOLD decisions
7. **Monitor Lifecycle Stages**: Track trade progression
8. **Analyze Performance**: Review win rate by entry type

---

## Rejection Reasons (Examples)

Common reasons for HOLD:
- "Multi-timeframe misalignment: HTF bearish vs LTF bullish"
- "Confidence 65.2% below threshold 70%"
- "Risk-reward 1.8 below minimum 2.0"
- "No valid entry setup: Price too far from support"
- "Abnormal volatility: ATR at 97th percentile"
- "Market regime unknown"
- "Daily loss limit breached"
- "Insufficient capital for minimum position"

**Every rejection is logged and explainable.**

---

## Integration with GUI

The enhanced execution engine integrates with the existing GUI:
- Signals panel shows entry type and lifecycle stage
- Portfolio panel tracks partial exits
- Logs show complete reasoning for every decision

---

## Disclaimer

⚠️ **This system generates rule-based trade signals with strict validation.**  
⚠️ **It does NOT guarantee profits. All trading involves substantial risk.**  
⚠️ **Past performance does not indicate future results.**  
⚠️ **You are responsible for your trading decisions.**

---

**The enhanced execution engine prioritizes accuracy and capital protection over trade frequency. It is designed for serious traders who understand that consistency and discipline matter more than prediction.**
