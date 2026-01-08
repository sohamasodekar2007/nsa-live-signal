# NSE Trading Decision Engine

A professional, accuracy-focused probabilistic trading decision engine for NSE (National Stock Exchange) stocks.

## Features

### Core Capabilities
- **Multi-Layer Technical Analysis**: Trend (EMA, VWAP), Momentum (RSI, MACD, Stochastic), Volatility (ATR, Bollinger Bands), Structure (S/R, Breakouts, Volume Profile)
- **Market Regime Detection**: Automatically classify market as TREND, RANGE, or HIGH_VOLATILITY using ADX and volatility metrics
- **Probabilistic Signal Generation**: Every signal includes confidence %, risk-reward ratio, stop-loss, targets, and reasoning
- **Portfolio Management**: Track positions, P&L, drawdown, allocation
- **Risk Management**: ATR-based position sizing, max daily loss limits, cooldown periods
- **Professional GUI**: PyQt6-based interface with real-time updates, dashboard, signals panel, portfolio tracking

### Technical Indicators
- **Trend**: EMA (9, 21, 50, 200), VWAP
- **Momentum**: RSI (14), MACD (12, 26, 9), Stochastic (%K, %D)
- **Volatility**: ATR (14), Bollinger Bands (20, 2σ)
- **Structure**: Support/Resistance levels, Breakout detection, Volume Profile (POC, Value Area)
- **Regime**: ADX (14) for trend strength classification

### Risk Management
- Max capital per trade: 10% (configurable)
- Max daily loss: 3% (auto-halt trading)
- ATR-based stop-loss calculation
- Position sizing based on risk per trade
- Signal cooldown to prevent over-trading

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. **Clone or download the project**
   ```bash
   cd nse_trading_engine
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the system**
   Edit `config/config.yaml` to set:
   - Initial capital
   - Risk parameters
   - Watchlist symbols'
   - Refresh intervals

4. **Run the application**
   ```bash
   python main.py
   ```

## Usage

### GUI Application

Run the main GUI:
```bash
python main.py
```

The GUI provides:
- **Dashboard**: Portfolio summary and recent signals
- **Signals Tab**: All generated signals with confidence, R:R, SL, targets
- **Portfolio Tab**: Open positions and P&L tracking
- **Watchlist Tab**: Manage symbols to monitor
- **Logs Tab**: System logs and decision reasoning

### Adding Symbols to Watchlist

1. Go to the "Watchlist" tab
2. Enter symbol with `.NS` suffix (e.g., `RELIANCE.NS`, `TCS.NS`)
3. Click "Add to Watchlist"
4. System will validate and start monitoring

### Understanding Signals

Each signal includes:
- **Signal Type**: BUY, SELL, or HOLD
- **Confidence**: 0-100% based on multi-layer confluence
- **Regime**: Current market regime (TREND/RANGE/HIGH_VOLATILITY)
- **Entry Price**: Suggested entry level
- **Stop Loss**: ATR-based stop loss
- **Targets**: T1 (2x risk), T2 (3x risk)
- **Risk-Reward Ratio**: Reward/Risk (minimum 1.5)
- **Reasoning**: Technical analysis summary

### Signal Rejection Rules

Signals are automatically rejected if:
- Confidence < 60%
- Risk-Reward ratio < 1.5
- Conflicting indicators
- Insufficient data quality

## Configuration

### Main Config (`config/config.yaml`)

```yaml
portfolio:
  initial_capital: 100000  # Starting capital in INR

risk:
  max_capital_per_trade_percent: 10.0  # Max 10% per trade
  max_daily_loss_percent: 3.0  # Halt if daily loss > 3%
  risk_per_trade_percent: 1.5  # Risk 1.5% per trade
  max_open_positions: 8

signals:
  min_confidence_percent: 60.0  # Minimum confidence
  min_risk_reward_ratio: 1.5  # Minimum R:R

watchlist:
  - RELIANCE.NS
  - TCS.NS
  - INFY.NS
```

### Indicators Config (`config/indicators_config.yaml`)

Contains parameters for all technical indicators and regime-specific weights.

## Project Structure

```
nse_trading_engine/
├── config/              # Configuration files
├── core/                # Core infrastructure (DB, logging, enums)
├── data/                # Data fetching and validation
├── indicators/          # Technical indicators
├── analysis/            # Regime detection, confluence, signal generation
├── portfolio/           # Portfolio state, risk management, performance
├── gui/                 # PyQt6 GUI application
├── backtesting/         # Backtesting framework (future)
├── main.py              # Application entry point
└── requirements.txt     # Python dependencies
```

## Important Disclaimers

⚠️ **Risk Warning**: This system generates probabilistic trading signals based on technical analysis. It does NOT guarantee profits. Trading involves substantial risk of loss.

⚠️ **Not Financial Advice**: Signals are for informational purposes only. Always conduct your own research and consult a financial advisor before making investment decisions.

⚠️ **Past Performance**: Historical performance does not indicate future results. Market conditions change and past patterns may not repeat.

⚠️ **Use at Your Own Risk**: The developers are not responsible for any financial losses incurred from using this system.

## System Requirements

- **Operating System**: Windows, macOS, or Linux
- **Python**: 3.8 or higher
- **RAM**: Minimum 4GB (8GB recommended)
- **Internet**: Required for fetching market data
- **Display**: 1280x720 or higher for optimal GUI experience

## Data Sources

- **Primary**: yfinance (Yahoo Finance) - Free, no API key required
- **NSE Symbols**: Use `.NS` suffix (e.g., `RELIANCE.NS` for Reliance Industries)
- **Timeframes**: Supports 1m, 5m, 15m, 1h, 1d intervals
- **Historical Data**: Default 1 year lookback

## Support & Development

This is a production-ready system designed for serious traders who understand:
- Technical analysis fundamentals
- Risk management principles
- Market microstructure
- Statistical probability

### Future Enhancements
- Backtesting framework with walk-forward analysis
- Advanced charting with indicator overlays
- Multi-timeframe signal correlation
- Machine learning-based confidence calibration
- Broker API integration (Zerodha, Angel One, etc.)
- Real-time streaming data
- Mobile notifications

## License

This project is for educational and professional use. Modify as needed for your trading strategy.

---

**Remember**: Trading is risky. This tool assists decision-making but does not make decisions for you. Always manage your risk, stay disciplined, and never risk more than you can afford to lose.
