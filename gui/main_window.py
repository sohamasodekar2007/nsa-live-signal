"""Production-Grade Trading GUI - Zero-Lag, Thread-Safe, with Live Scan Log."""

import sys
from datetime import datetime
from typing import Dict, Optional, List
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QPushButton, QTableWidget, 
                           QTableWidgetItem, QTabWidget, QGroupBox, QSpinBox, 
                           QHeaderView, QMessageBox, QSplitter, QLineEdit,
                           QProgressBar, QTextEdit, QComboBox, QCheckBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QTextCursor
import pyqtgraph as pg

from core.enums import SignalType, PositionType
from data.nse_symbols import get_symbol_manager
from data.snapshot_store import get_snapshot_store, StockSnapshot
from gui.workers import PriceWorker, SignalWorker, DataBridge
from gui.market_scan_worker import MarketScanWorker, ScanResult


class TradingEngineGUI(QMainWindow):
    """Production-grade trading GUI with zero-lag updates and live scan log."""
    
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("NSE Trading Engine Pro - Full Market Scanner")
        self.setGeometry(100, 100, 1700, 950)
        
        # Data
        self._symbol_manager = get_symbol_manager()
        self._snapshot_store = get_snapshot_store()
        self._watchlist = self._symbol_manager.get_watchlist_default()
        self._selected_symbol = self._watchlist[0] if self._watchlist else "RELIANCE.NS"
        
        # Workers
        self._data_bridge = DataBridge()
        self._price_worker: Optional[PriceWorker] = None
        self._signal_worker: Optional[SignalWorker] = None
        self._market_scanner: Optional[MarketScanWorker] = None
        
        # Scan results cache
        self._last_scan_results: List[ScanResult] = []
        
        # Styling
        self._apply_dark_theme()
        
        # UI Setup
        self._setup_ui()
        
        # Start workers
        self._start_workers()
        
        # Real-time update timers
        self._price_timer = QTimer()
        self._price_timer.timeout.connect(self._refresh_prices)
        self._price_timer.start(2000)  # Update every 2 seconds
        
        self._chart_timer = QTimer()
        self._chart_timer.timeout.connect(self._update_chart)
        self._chart_timer.start(30000)  # Update chart every 30 seconds
        
        # Initial chart load
        QTimer.singleShot(1000, self._update_chart)
    
    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI'; }
            QGroupBox { border: 1px solid #30363d; margin-top: 15px; border-radius: 6px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 8px; color: #58a6ff; }
            QLineEdit, QTextEdit { background: #161b22; border: 1px solid #30363d; padding: 8px; color: #c9d1d9; border-radius: 4px; }
            QLineEdit:focus, QTextEdit:focus { border-color: #58a6ff; }
            QComboBox { background: #161b22; border: 1px solid #30363d; padding: 6px; color: #c9d1d9; border-radius: 4px; }
            QPushButton { background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d; padding: 8px 16px; border-radius: 6px; }
            QPushButton:hover { background-color: #30363d; border-color: #58a6ff; }
            QPushButton:disabled { background-color: #161b22; color: #484f58; }
            QPushButton#buy { background-color: #238636; border: none; color: white; font-weight: bold; }
            QPushButton#buy:hover { background-color: #2ea043; }
            QPushButton#sell { background-color: #da3633; border: none; color: white; font-weight: bold; }
            QPushButton#sell:hover { background-color: #f85149; }
            QPushButton#scan { background-color: #1f6feb; border: none; color: white; font-weight: bold; }
            QPushButton#scan:hover { background-color: #388bfd; }
            QTableWidget { background-color: #0d1117; gridline-color: #21262d; border: 1px solid #30363d; alternate-background-color: #161b22; }
            QHeaderView::section { background-color: #161b22; padding: 8px; border: none; font-weight: bold; color: #8b949e; }
            QTableWidget::item { padding: 6px; }
            QTableWidget::item:selected { background-color: #1f6feb; }
            QProgressBar { border: 1px solid #30363d; border-radius: 4px; text-align: center; background: #0d1117; }
            QProgressBar::chunk { background-color: #238636; border-radius: 3px; }
            QTabWidget::pane { border: 1px solid #30363d; border-radius: 6px; }
            QTabBar::tab { background: #161b22; padding: 10px 20px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #0d1117; border-bottom: 2px solid #58a6ff; }
        """)
    
    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Stats Bar
        self._setup_stats_bar(main_layout)
        
        # Tabs
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        
        # Dashboard
        dashboard = QWidget()
        tabs.addTab(dashboard, "📊 Dashboard")
        self._setup_dashboard(dashboard)
        
        # Live Signals (Enhanced)
        signals_tab = QWidget()
        tabs.addTab(signals_tab, "🎯 Live Signals")
        self._setup_signals_tab(signals_tab)
        
        # Portfolio
        portfolio_tab = QWidget()
        tabs.addTab(portfolio_tab, "💼 Portfolio")
        self._setup_portfolio_tab(portfolio_tab)
    
    def _setup_stats_bar(self, parent):
        bar = QWidget()
        bar.setStyleSheet("background-color: #161b22; border-radius: 8px; padding: 10px;")
        layout = QHBoxLayout(bar)
        
        self.lbl_capital = QLabel(f"💰 Capital: ₹{self.engine.portfolio.total_capital:,.2f}")
        self.lbl_capital.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_capital.setStyleSheet("color: #58a6ff;")
        
        self.lbl_pnl = QLabel("📈 P&L: ₹0.00")
        self.lbl_pnl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        
        self.lbl_positions = QLabel("📦 Positions: 0")
        self.lbl_positions.setStyleSheet("color: #8b949e;")
        
        # Show loaded symbol count
        from data.nse_symbol_loader import get_nse_symbol_loader
        symbol_count = get_nse_symbol_loader().get_symbol_count()
        self.lbl_symbols = QLabel(f"📋 NSE Stocks: {symbol_count}")
        self.lbl_symbols.setStyleSheet("color: #3fb950; font-weight: bold;")
        
        self.lbl_status = QLabel("● LIVE")
        self.lbl_status.setStyleSheet("color: #3fb950; font-weight: bold;")
        
        # Breadth Dashboard
        self.lbl_breadth = QLabel("A: 0 | D: 0")
        self.lbl_breadth.setStyleSheet("color: #c9d1d9; font-weight: bold; background: #21262d; padding: 2px 8px; border-radius: 4px;")
        
        # Credits
        lbl_credits = QLabel('<a href="https://www.linkedin.com/in/soham-asodekar-0a4495381" style="color: #58a6ff; text-decoration: none;">Created by Soham Asodekar</a>')
        lbl_credits.setOpenExternalLinks(True)
        lbl_credits.setFont(QFont("Segoe UI", 10))
        lbl_credits.setStyleSheet("padding-left: 15px;")
        
        layout.addWidget(self.lbl_capital)
        layout.addWidget(self.lbl_pnl)
        layout.addStretch()
        layout.addWidget(self.lbl_breadth)  # Added Breadth
        layout.addSpacing(15)
        layout.addWidget(self.lbl_symbols)
        layout.addWidget(self.lbl_positions)
        layout.addWidget(self.lbl_status)
        layout.addWidget(lbl_credits)
        parent.addWidget(bar)
    
    def _setup_dashboard(self, parent):
        layout = QHBoxLayout(parent)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Watchlist
        wl_widget = self._create_watchlist_panel()
        splitter.addWidget(wl_widget)
        
        # Chart
        chart_widget = self._create_chart_panel()
        splitter.addWidget(chart_widget)
        
        # Trade Panel
        trade_widget = self._create_trade_panel()
        splitter.addWidget(trade_widget)
        
        splitter.setSizes([320, 700, 320])
        layout.addWidget(splitter)
    
    def _create_watchlist_panel(self) -> QWidget:
        group = QGroupBox("📋 Market Watch")
        layout = QVBoxLayout(group)
        
        # Search
        search_layout = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Add symbol (e.g. MRF)")
        self.txt_search.returnPressed.connect(self._add_symbol)
        btn_add = QPushButton("+")
        btn_add.setFixedWidth(40)
        btn_add.clicked.connect(self._add_symbol)
        search_layout.addWidget(self.txt_search)
        search_layout.addWidget(btn_add)
        layout.addLayout(search_layout)
        
        # Table
        self.watchlist_table = QTableWidget()
        self.watchlist_table.setColumnCount(4)
        self.watchlist_table.setHorizontalHeaderLabels(["Symbol", "LTP", "Chg%", ""])
        self.watchlist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.watchlist_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.watchlist_table.setAlternatingRowColors(True)
        self.watchlist_table.cellClicked.connect(self._on_symbol_selected)
        layout.addWidget(self.watchlist_table)
        
        self._populate_watchlist()
        return group
    
    def _create_chart_panel(self) -> QWidget:
        group = QGroupBox("📈 Chart")
        layout = QVBoxLayout(group)
        
        # Header with symbol and timeframe
        header_layout = QHBoxLayout()
        
        self.lbl_chart_symbol = QLabel(self._selected_symbol)
        self.lbl_chart_symbol.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_chart_symbol.setStyleSheet("color: #f0883e;")
        header_layout.addWidget(self.lbl_chart_symbol)
        
        header_layout.addStretch()
        
        self.combo_timeframe = QComboBox()
        self.combo_timeframe.addItems(["1m", "5m", "15m", "30m", "1h", "1d", "1wk", "1mo"])
        self.combo_timeframe.setCurrentText("1d")
        self.combo_timeframe.currentTextChanged.connect(self._update_chart)
        self.combo_timeframe.setStyleSheet("background: #161b22; color: #c9d1d9; border: 1px solid #30363d; padding: 4px;")
        header_layout.addWidget(self.combo_timeframe)
        
        layout.addLayout(header_layout)
        
        # Chart Controls (Overlays)
        controls_layout = QHBoxLayout()
        
        self.chk_ema = QCheckBox("EMA 50/200")
        self.chk_ema.stateChanged.connect(self._update_chart)
        self.chk_ema.setStyleSheet("color: #c9d1d9;")
        controls_layout.addWidget(self.chk_ema)
        
        self.chk_bb = QCheckBox("Bollinger Bands")
        self.chk_bb.stateChanged.connect(self._update_chart)
        self.chk_bb.setStyleSheet("color: #c9d1d9;")
        controls_layout.addWidget(self.chk_bb)
        
        self.chk_rsi = QCheckBox("RSI (Subplot)")
        self.chk_rsi.stateChanged.connect(self._update_chart)
        self.chk_rsi.setStyleSheet("color: #c9d1d9;")
        controls_layout.addWidget(self.chk_rsi)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Main Price Chart
        self.chart = pg.PlotWidget()
        self.chart.setBackground('#0d1117')
        self.chart.showGrid(x=True, y=True, alpha=0.2)
        self.chart.setLabel('left', 'Price (₹)')
        self.chart.setLabel('bottom', 'Date')
        self.chart.addLegend()
        layout.addWidget(self.chart)
        
        # RSI Subplot (Hidden by default)
        self.rsi_chart = pg.PlotWidget()
        self.rsi_chart.setBackground('#0d1117')
        self.rsi_chart.showGrid(x=True, y=True, alpha=0.2)
        self.rsi_chart.setLabel('left', 'RSI')
        self.rsi_chart.setMaximumHeight(150)
        self.rsi_chart.setVisible(False)
        
        # Add lines for 70/30 levels
        self.rsi_chart.addItem(pg.InfiniteLine(pos=70, angle=0, pen=pg.mkPen('#ff6b6b', width=1, style=Qt.PenStyle.DashLine)))
        self.rsi_chart.addItem(pg.InfiniteLine(pos=30, angle=0, pen=pg.mkPen('#3fb950', width=1, style=Qt.PenStyle.DashLine)))
        
        layout.addWidget(self.rsi_chart)
        
        # Link X-axis
        self.rsi_chart.setXLink(self.chart)
        
        return group
    
    def _create_trade_panel(self) -> QWidget:
        group = QGroupBox("⚡ Quick Trade")
        layout = QVBoxLayout(group)
        
        self.lbl_trade_symbol = QLabel(self._selected_symbol)
        self.lbl_trade_symbol.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_trade_symbol.setStyleSheet("color: #58a6ff;")
        layout.addWidget(self.lbl_trade_symbol)
        
        self.lbl_ltp = QLabel("LTP: ₹0.00")
        self.lbl_ltp.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self.lbl_ltp.setStyleSheet("color: #f0883e;")
        layout.addWidget(self.lbl_ltp)
        
        layout.addSpacing(10)
        
        layout.addWidget(QLabel("Quantity:"))
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 10000)
        self.spin_qty.setValue(10)
        self.spin_qty.setStyleSheet("padding: 10px; font-size: 16px;")
        layout.addWidget(self.spin_qty)
        
        layout.addSpacing(15)
        
        btn_buy = QPushButton("🔼 BUY")
        btn_buy.setObjectName("buy")
        btn_buy.setFixedHeight(55)
        btn_buy.clicked.connect(lambda: self._execute_trade('BUY'))
        layout.addWidget(btn_buy)
        
        btn_sell = QPushButton("🔽 SELL")
        btn_sell.setObjectName("sell")
        btn_sell.setFixedHeight(55)
        btn_sell.clicked.connect(lambda: self._execute_trade('SELL'))
        layout.addWidget(btn_sell)
        
        layout.addStretch()
        
        self.lbl_msg = QLabel("")
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setStyleSheet("padding: 10px; border-radius: 4px;")
        layout.addWidget(self.lbl_msg)
        
        return group
    
    def _setup_signals_tab(self, parent):
        layout = QHBoxLayout(parent)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Controls + Live Log
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Scan Controls
        ctrl_group = QGroupBox("🔍 Scanner Controls")
        ctrl_layout = QVBoxLayout(ctrl_group)
        
        self.btn_scan = QPushButton("🚀 SCAN ALL NSE STOCKS")
        self.btn_scan.setObjectName("scan")
        self.btn_scan.setFixedHeight(50)
        self.btn_scan.clicked.connect(self._scan_market)
        ctrl_layout.addWidget(self.btn_scan)
        
        # Filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.cmb_filter = QComboBox()
        self.cmb_filter.addItems(["All Signals", "BUY Only", "SELL Only", "Strong Only"])
        self.cmb_filter.currentTextChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.cmb_filter)
        ctrl_layout.addLayout(filter_layout)
        
        # Progress
        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        ctrl_layout.addWidget(self.scan_progress)
        
        # Show loaded symbol count
        from data.nse_symbol_loader import get_nse_symbol_loader
        loader = get_nse_symbol_loader()
        count = loader.get_symbol_count()
        self.lbl_scan_status = QLabel(f"✅ Loaded {count} NSE stocks. Ready to scan!")
        self.lbl_scan_status.setStyleSheet("color: #3fb950; padding: 5px;")
        ctrl_layout.addWidget(self.lbl_scan_status)
        
        left_layout.addWidget(ctrl_group)
        
        # Live Log
        log_group = QGroupBox("📜 Live Scan Log")
        log_layout = QVBoxLayout(log_group)
        
        self.txt_scan_log = QTextEdit()
        self.txt_scan_log.setReadOnly(True)
        self.txt_scan_log.setMaximumHeight(400)
        self.txt_scan_log.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px;")
        log_layout.addWidget(self.txt_scan_log)
        
        left_layout.addWidget(log_group)
        left_layout.addStretch()
        
        splitter.addWidget(left_panel)
        
        # Right: Results Table
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        results_group = QGroupBox("📊 Scan Results")
        results_layout = QVBoxLayout(results_group)
        
        self.lbl_results_count = QLabel("0 signals found")
        self.lbl_results_count.setStyleSheet("color: #58a6ff; font-weight: bold;")
        results_layout.addWidget(self.lbl_results_count)
        
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(10)
        self.signals_table.setHorizontalHeaderLabels([
            "Symbol", "Signal", "Conf%", "LTP", "Change%", 
            "Stop Loss", "Target 1", "Target 2", "R:R", ""
        ])
        self.signals_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.signals_table.setAlternatingRowColors(True)
        self.signals_table.setSortingEnabled(True)
        results_layout.addWidget(self.signals_table)
        
        right_layout.addWidget(results_group)
        splitter.addWidget(right_panel)
        
        splitter.setSizes([400, 900])
        layout.addWidget(splitter)
    
    def _setup_portfolio_tab(self, parent):
        layout = QHBoxLayout(parent)
        
        # Positions
        pos_group = QGroupBox("📦 Active Positions")
        pos_layout = QVBoxLayout(pos_group)
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(7)
        self.positions_table.setHorizontalHeaderLabels(["Symbol", "Side", "Qty", "Avg", "LTP", "P&L", ""])
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.positions_table.setAlternatingRowColors(True)
        pos_layout.addWidget(self.positions_table)
        layout.addWidget(pos_group)
        
        # History
        hist_group = QGroupBox("📋 Trade History")
        hist_layout = QVBoxLayout(hist_group)
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Time", "Symbol", "Side", "Qty", "Price"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setAlternatingRowColors(True)
        hist_layout.addWidget(self.history_table)
        layout.addWidget(hist_group)
    
    # --- Workers ---
    
    def _start_workers(self):
        """Start background data workers."""
        self._price_worker = PriceWorker(self._watchlist, interval_ms=2000)
        self._price_worker.prices_updated.connect(self._on_prices_updated)
        self._price_worker.start()
    
    def _refresh_prices(self):
        """Force UI refresh with latest prices from store (polling fallback)."""
        snapshots = self._snapshot_store.get_all()
        if snapshots:
            self._on_prices_updated(snapshots)
    
    def _on_prices_updated(self, snapshots: Dict[str, StockSnapshot]):
        """Handle price updates from worker (thread-safe)."""
        for row in range(self.watchlist_table.rowCount()):
            sym_item = self.watchlist_table.item(row, 0)
            if not sym_item:
                continue
            
            symbol = sym_item.text()
            snap = snapshots.get(symbol)
            if snap:
                self.watchlist_table.setItem(row, 1, QTableWidgetItem(f"₹{snap.ltp:,.2f}"))
                
                chg_item = QTableWidgetItem(f"{snap.change_pct:+.2f}%")
                chg_item.setForeground(QColor("#3fb950") if snap.change_pct >= 0 else QColor("#f85149"))
                self.watchlist_table.setItem(row, 2, chg_item)
                
                if symbol == self._selected_symbol:
                    self.lbl_ltp.setText(f"LTP: ₹{snap.ltp:,.2f}")
        
        self._update_portfolio_pnl(snapshots)
    
    def _update_portfolio_pnl(self, snapshots: Dict[str, StockSnapshot]):
        """Update portfolio positions with latest prices."""
        positions = getattr(self.engine.portfolio, 'positions', {})
        total_pnl = 0.0
        
        self.positions_table.setRowCount(0)
        for symbol, pos in positions.items():
            snap = snapshots.get(symbol)
            ltp = snap.ltp if snap else pos.get('current_price', pos['entry_price'])
            pnl = (ltp - pos['entry_price']) * pos['quantity']
            total_pnl += pnl
            
            row = self.positions_table.rowCount()
            self.positions_table.insertRow(row)
            self.positions_table.setItem(row, 0, QTableWidgetItem(symbol))
            self.positions_table.setItem(row, 1, QTableWidgetItem("LONG"))
            self.positions_table.setItem(row, 2, QTableWidgetItem(str(pos['quantity'])))
            self.positions_table.setItem(row, 3, QTableWidgetItem(f"₹{pos['entry_price']:.2f}"))
            self.positions_table.setItem(row, 4, QTableWidgetItem(f"₹{ltp:.2f}"))
            
            pnl_item = QTableWidgetItem(f"₹{pnl:+,.2f}")
            pnl_item.setForeground(QColor("#3fb950") if pnl >= 0 else QColor("#f85149"))
            self.positions_table.setItem(row, 5, pnl_item)
            
            # Close button
            btn_close = QPushButton("✕")
            btn_close.setStyleSheet("background: #da3633; color: white; padding: 4px;")
            btn_close.clicked.connect(lambda ch, s=symbol: self._close_position(s))
            self.positions_table.setCellWidget(row, 6, btn_close)
        
        color = "#3fb950" if total_pnl >= 0 else "#f85149"
        self.lbl_pnl.setText(f"📈 P&L: ₹{total_pnl:+,.2f}")
        self.lbl_pnl.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
        self.lbl_positions.setText(f"📦 Positions: {len(positions)}")
    
    # --- Actions ---
    
    def _populate_watchlist(self):
        self.watchlist_table.setRowCount(0)
        for sym in self._watchlist:
            row = self.watchlist_table.rowCount()
            self.watchlist_table.insertRow(row)
            self.watchlist_table.setItem(row, 0, QTableWidgetItem(sym))
            self.watchlist_table.setItem(row, 1, QTableWidgetItem("--"))
            self.watchlist_table.setItem(row, 2, QTableWidgetItem("--"))
            
            btn_del = QPushButton("×")
            btn_del.setFixedWidth(30)
            btn_del.setStyleSheet("background: transparent; color: #f85149; font-size: 18px;")
            btn_del.clicked.connect(lambda ch, s=sym: self._remove_symbol(s))
            self.watchlist_table.setCellWidget(row, 3, btn_del)
    
    def _add_symbol(self):
        txt = self.txt_search.text().strip().upper()
        if not txt:
            return
        
        if not txt.endswith('.NS'):
            txt += '.NS'
        
        if txt not in self._watchlist:
            self._watchlist.append(txt)
            self._symbol_manager.add_symbol(txt)
            if self._price_worker:
                self._price_worker.add_symbol(txt)
            self._populate_watchlist()
        
        self.txt_search.clear()
    
    def _remove_symbol(self, symbol: str):
        if symbol in self._watchlist:
            self._watchlist.remove(symbol)
            self._populate_watchlist()
    
    def _on_symbol_selected(self, row, col):
        item = self.watchlist_table.item(row, 0)
        if item:
            self._selected_symbol = item.text()
            self.lbl_chart_symbol.setText(self._selected_symbol)
            self.lbl_trade_symbol.setText(self._selected_symbol)
            self._update_chart()
    
    def _update_chart(self):
        """Update chart with candlestick view (multi-timeframe)."""
        try:
            import yfinance as yf
            
            timeframe = self.combo_timeframe.currentText()
            
            # Map timeframe to yfinance period/interval
            tf_map = {
                "1m": ("1d", "1m"),
                "5m": ("5d", "5m"),
                "15m": ("5d", "15m"),
                "30m": ("5d", "30m"),
                "1h": ("1mo", "1h"),
                "1d": ("1y", "1d"),
                "1wk": ("2y", "1wk"),
                "1mo": ("5y", "1mo")
            }
            
            period, interval = tf_map.get(timeframe, ("1y", "1d"))
            
            # Fetch OHLC data
            ticker = yf.Ticker(self._selected_symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df is not None and not df.empty:
                self.chart.clear()
                
                # Limit candle count for performance (max 100 candles)
                if len(df) > 100:
                    df = df.iloc[-100:]
                
                # Prepare candlestick data
                for i, (idx, row) in enumerate(df.iterrows()):
                    open_price = row['Open']
                    high = row['High']
                    low = row['Low']
                    close = row['Close']
                    
                    # Determine color
                    if close >= open_price:
                        color = '#3fb950'  # Green (bullish)
                    else:
                        color = '#f85149'  # Red (bearish)
                    
                    # Draw wick (high-low line)
                    wick = pg.PlotCurveItem(
                        x=[i, i],
                        y=[low, high],
                        pen=pg.mkPen(color, width=1)
                    )
                    self.chart.addItem(wick)
                    
                    # Draw body (open-close bar)
                    body_low = min(open_price, close)
                    body_high = max(open_price, close)
                    
                    # Use bar graph for body
                    body = pg.BarGraphItem(
                        x=[i],
                        height=[body_high - body_low],
                        width=0.6,
                        y0=body_low,
                        brush=pg.mkBrush(color),
                        pen=pg.mkPen(color)
                    )
                    self.chart.addItem(body)
                
                # Add current price line
                current_price = df['Close'].iloc[-1]
                price_line = pg.InfiniteLine(
                    pos=current_price,
                    angle=0,
                    pen=pg.mkPen('#58a6ff', width=1, style=Qt.PenStyle.DashLine)
                )
                self.chart.addItem(price_line)
                
                # --- OVERLAYS: EMA 50/200 ---
                if hasattr(self, 'chk_ema') and self.chk_ema.isChecked():
                    ema50 = df['Close'].ewm(span=50, adjust=False).mean()
                    ema200 = df['Close'].ewm(span=200, adjust=False).mean()
                    
                    self.chart.plot(ema50.values, pen=pg.mkPen('#ffdf5d', width=1.5), name="EMA 50") # Yellow
                    self.chart.plot(ema200.values, pen=pg.mkPen('#d1d5da', width=1.5), name="EMA 200") # White
                
                # --- OVERLAYS: Bollinger Bands ---
                if hasattr(self, 'chk_bb') and self.chk_bb.isChecked():
                    sma20 = df['Close'].rolling(window=20).mean()
                    std20 = df['Close'].rolling(window=20).std()
                    upper = sma20 + (std20 * 2)
                    lower = sma20 - (std20 * 2)
                    
                    # Fill area (pseudo-fill by plotting lines)
                    self.chart.plot(upper.values, pen=pg.mkPen('#79c0ff', width=1))
                    self.chart.plot(lower.values, pen=pg.mkPen('#79c0ff', width=1))
                    
                # --- SUBPLOT: RSI ---
                if hasattr(self, 'chk_rsi') and self.chk_rsi.isChecked():
                    self.rsi_chart.setVisible(True)
                    self.rsi_chart.clear()
                    
                    # Draw levels
                    self.rsi_chart.addItem(pg.InfiniteLine(pos=70, angle=0, pen=pg.mkPen('#ff7b72', width=1, style=Qt.PenStyle.DashLine)))
                    self.rsi_chart.addItem(pg.InfiniteLine(pos=30, angle=0, pen=pg.mkPen('#7ee787', width=1, style=Qt.PenStyle.DashLine)))
                    
                    # Calc RSI
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    
                    self.rsi_chart.plot(rsi.values, pen=pg.mkPen('#a371f7', width=1.5))
                else:
                    self.rsi_chart.setVisible(False)
                

                
                # --- LIVE ANALYSIS & SIGNAL VISUALIZATION ---
                # Calculate simple analysis for the chart view
                last_close = df['Close'].iloc[-1]
                prev_close = df['Close'].iloc[-2]
                change_pct = ((last_close - prev_close) / prev_close) * 100
                
                # Indicators for Logic
                rsi_val = 50
                ema50_val = last_close
                
                if len(df) > 14:
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi_series = 100 - (100 / (1 + rs))
                    rsi_val = rsi_series.iloc[-1]
                
                if len(df) > 50:
                    ema50_series = df['Close'].ewm(span=50, adjust=False).mean()
                    ema50_val = ema50_series.iloc[-1]
                
                # Determine Signal
                signal_text = "NEUTRAL"
                signal_color = "#8b949e" # Grey
                
                # Trading Logic (Simplified for visualization)
                if last_close > ema50_val:
                    if rsi_val < 30: 
                        signal_text = "STRONG BUY (Oversold Dip)"
                        signal_color = "#3fb950" # Green
                    elif last_close > prev_close * 1.01:
                        signal_text = "BUY (Momentum)"
                        signal_color = "#3fb950"
                elif last_close < ema50_val:
                    if rsi_val > 70:
                        signal_text = "STRONG SELL (Overbought Top)"
                        signal_color = "#f85149" # Red
                    elif last_close < prev_close * 0.99:
                        signal_text = "SELL (Momentum)"
                        signal_color = "#f85149"
                
                # Calculate Levels (ATR-based or Percentage)
                volatility = df['High'].iloc[-5:].max() - df['Low'].iloc[-5:].min()
                if volatility == 0: volatility = last_close * 0.01
                
                if "BUY" in signal_text:
                    sl = last_close - (volatility * 0.5)
                    t1 = last_close + volatility
                    t2 = last_close + (volatility * 2)
                    
                    # Plot Targets (Green Dashed)
                    self.chart.addItem(pg.InfiniteLine(pos=t1, angle=0, pen=pg.mkPen('#3fb950', width=1, style=Qt.PenStyle.DashLine), label=f"T1: {t1:.2f}", labelOpts={'color': '#3fb950', 'position': 0.9}))
                    self.chart.addItem(pg.InfiniteLine(pos=t2, angle=0, pen=pg.mkPen('#3fb950', width=1, style=Qt.PenStyle.DashLine), label=f"T2: {t2:.2f}", labelOpts={'color': '#3fb950', 'position': 0.9}))
                    # Plot SL (Red Dashed)
                    self.chart.addItem(pg.InfiniteLine(pos=sl, angle=0, pen=pg.mkPen('#f85149', width=1, style=Qt.PenStyle.DashLine), label=f"SL: {sl:.2f}", labelOpts={'color': '#f85149', 'position': 0.9}))
                    
                elif "SELL" in signal_text:
                    sl = last_close + (volatility * 0.5)
                    t1 = last_close - volatility
                    t2 = last_close - (volatility * 2)
                    
                    self.chart.addItem(pg.InfiniteLine(pos=t1, angle=0, pen=pg.mkPen('#3fb950', width=1, style=Qt.PenStyle.DashLine), label=f"T1: {t1:.2f}", labelOpts={'color': '#3fb950', 'position': 0.9}))
                    self.chart.addItem(pg.InfiniteLine(pos=t2, angle=0, pen=pg.mkPen('#3fb950', width=1, style=Qt.PenStyle.DashLine), label=f"T2: {t2:.2f}", labelOpts={'color': '#3fb950', 'position': 0.9}))
                    self.chart.addItem(pg.InfiniteLine(pos=sl, angle=0, pen=pg.mkPen('#f85149', width=1, style=Qt.PenStyle.DashLine), label=f"SL: {sl:.2f}", labelOpts={'color': '#f85149', 'position': 0.9}))

                # Display Signal Label on Chart
                text_item = pg.TextItem(html=f'<div style="text-align: left; color: {signal_color};"><span style="font-size: 18pt; font-weight: bold;">{signal_text}</span><br><span style="font-size: 10pt; color: #c9d1d9;">LTP: {last_close:.2f} | RSI: {rsi_val:.1f}</span></div>', anchor=(0, 0))
                self.chart.addItem(text_item)
                # Position text top-left (using view coordinates)
                # We need to set position after view is updated, but for now we place it at start of visible range
                # Better approach: mapToView or setPos relative to view range. 
                # Simplest for pyqtgraph: setPos to a coordinate.
                # Let's put it at the top left of the visible data.
                view_box = self.chart.getViewBox()
                # view_range = view_box.viewRange()
                # x_min = view_range[0][0]
                # y_max = view_range[1][1]
                # text_item.setPos(x_min, y_max) 
                # Since interacting with viewbox ranges inside update might be tricky due to auto-ranging, let's just place it near the last candle for visibility or use 0, max_y
                
                start_x = df.index[0] if isinstance(df.index, (int, float)) else 0 # It's reset index so 0 to N
                # Actually our x-axis is 0..N-1
                text_item.setPos(0, df['High'].max())

                # Update LTP label
                self.lbl_ltp.setText(f"LTP: ₹{current_price:,.2f}")
                
        except Exception as e:
            pass
    
    def _scan_market(self):
        """Launch FULL market scan with live log."""
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("⏳ SCANNING...")
        self.scan_progress.setVisible(True)
        self.scan_progress.setValue(0)
        self.signals_table.setRowCount(0)
        self.txt_scan_log.clear()
        self._log("🚀 Starting full market scan...")
        
        self._market_scanner = MarketScanWorker()
        self._market_scanner.scan_started.connect(self._on_scan_started)
        self._market_scanner.scan_progress.connect(self._on_scan_progress)
        self._market_scanner.stock_scanned.connect(self._on_stock_scanned)
        self._market_scanner.scan_complete.connect(self._on_scan_complete)
        self._market_scanner.scan_error.connect(self._on_scan_error)
        self._market_scanner.start()
    
    def _log(self, message: str):
        """Add message to scan log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_scan_log.append(f"[{timestamp}] {message}")
        self.txt_scan_log.moveCursor(QTextCursor.MoveOperation.End)
    
    def _on_scan_started(self, total: int):
        self._log(f"📊 Scanning {total} NSE stocks...")
        self.lbl_scan_status.setText(f"Scanning {total} stocks...")
        self.scan_progress.setMaximum(total)
    
    def _on_scan_progress(self, scanned: int, total: int):
        self.scan_progress.setValue(scanned)
        self.lbl_scan_status.setText(f"Scanned {scanned}/{total} ({scanned*100//total}%)")
    
    def _on_stock_scanned(self, symbol: str, status: str, ltp: float):
        """Live log of each stock scanned."""
        if ltp > 0:
            self._log(f"{symbol}: {status} (₹{ltp:.2f})")
        else:
            self._log(f"{symbol}: {status}")
    
    def _on_scan_complete(self, results: List[ScanResult]):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("🚀 SCAN ALL NSE STOCKS")
        self.scan_progress.setVisible(False)
        
        self._last_scan_results = results
        actionable = [r for r in results if r.signal != "NEUTRAL"]
        
        self._log(f"✅ Scan complete! Found {len(actionable)} signals from {len(results)} stocks")
        self.lbl_scan_status.setText(f"Found {len(actionable)} signals from {len(results)} stocks")
        self.lbl_results_count.setText(f"{len(actionable)} signals found")
        
        self._display_results(actionable)
    
    def _on_scan_error(self, error: str):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("🚀 SCAN ALL NSE STOCKS")
        self.scan_progress.setVisible(False)
        self._log(f"❌ Error: {error}")
        self.lbl_scan_status.setText(f"Error: {error}")
        self.lbl_scan_status.setStyleSheet("color: #f85149;")
    
    def _display_results(self, results: List[ScanResult]):
        """Display scan results with Stop Loss, Target 1, Target 2, Risk-Reward."""
        self.signals_table.setSortingEnabled(False)
        self.signals_table.setRowCount(0)
        
        for r in results[:150]:  # Top 150
            row = self.signals_table.rowCount()
            self.signals_table.insertRow(row)
            
            # Symbol
            self.signals_table.setItem(row, 0, QTableWidgetItem(r.symbol))
            
            # Signal with color
            sig_item = QTableWidgetItem(r.signal)
            if "BUY" in r.signal:
                sig_item.setForeground(QColor("#3fb950"))
            elif "SELL" in r.signal:
                sig_item.setForeground(QColor("#f85149"))
            self.signals_table.setItem(row, 1, sig_item)
            
            # Confidence
            self.signals_table.setItem(row, 2, QTableWidgetItem(f"{r.confidence:.0f}%"))
            
            # LTP
            self.signals_table.setItem(row, 3, QTableWidgetItem(f"₹{r.ltp:,.2f}"))
            
            # Change %
            chg_item = QTableWidgetItem(f"{r.change_pct:+.2f}%")
            chg_item.setForeground(QColor("#3fb950") if r.change_pct >= 0 else QColor("#f85149"))
            self.signals_table.setItem(row, 4, chg_item)
            
            # Stop Loss (RED color)
            sl_item = QTableWidgetItem(f"₹{r.stop_loss:,.2f}")
            sl_item.setForeground(QColor("#f85149"))
            self.signals_table.setItem(row, 5, sl_item)
            
            # Target 1 (GREEN color)
            t1_item = QTableWidgetItem(f"₹{r.target1:,.2f}")
            t1_item.setForeground(QColor("#3fb950"))
            self.signals_table.setItem(row, 6, t1_item)
            
            # Target 2 (BRIGHT GREEN color)
            t2_item = QTableWidgetItem(f"₹{r.target2:,.2f}")
            t2_item.setForeground(QColor("#56d364"))
            self.signals_table.setItem(row, 7, t2_item)
            
            # Risk-Reward Ratio
            rr_item = QTableWidgetItem(f"{r.risk_reward_ratio:.1f}:1")
            rr_item.setForeground(QColor("#58a6ff"))
            self.signals_table.setItem(row, 8, rr_item)
            
            # Trade button
            btn = QPushButton("TRADE")
            btn.setStyleSheet("background-color: #1f6feb; color: white; padding: 5px;")
            btn.clicked.connect(lambda ch, sym=r.symbol, side=r.signal.replace("STRONG ", "").replace("WEAK ", ""): self._do_execute(sym, side, 10))
            self.signals_table.setCellWidget(row, 9, btn)
        
        self.signals_table.setSortingEnabled(True)
    
    def _apply_filter(self, filter_text: str):
        """Apply filter to results."""
        if not self._last_scan_results:
            return
        
        if filter_text == "All Signals":
            filtered = [r for r in self._last_scan_results if r.signal != "NEUTRAL"]
        elif filter_text == "BUY Only":
            filtered = [r for r in self._last_scan_results if "BUY" in r.signal]
        elif filter_text == "SELL Only":
            filtered = [r for r in self._last_scan_results if "SELL" in r.signal]
        elif filter_text == "Strong Only":
            filtered = [r for r in self._last_scan_results if "STRONG" in r.signal]
        else:
            filtered = self._last_scan_results
        
        self._display_results(filtered)
        self.lbl_results_count.setText(f"{len(filtered)} signals shown")
    
    def _execute_trade(self, side: str):
        symbol = self._selected_symbol
        qty = self.spin_qty.value()
        self._do_execute(symbol, side, qty)
    
    def _do_execute(self, symbol: str, side: str, qty: int):
        ltp = self._snapshot_store.get_ltp(symbol)
        if ltp <= 0:
            ltp = self.engine.data_fetcher.get_current_price(symbol)
        
        if ltp <= 0:
            self.lbl_msg.setText("❌ Error: Invalid price")
            self.lbl_msg.setStyleSheet("color: #f85149; background: #2d1b1b; padding: 10px; border-radius: 4px;")
            return
        
        pos_type = PositionType.LONG if "BUY" in side else PositionType.SHORT
        stop_loss = ltp * 0.98 if pos_type == PositionType.LONG else ltp * 1.02
        target = ltp * 1.04 if pos_type == PositionType.LONG else ltp * 0.96
        
        if self.engine.portfolio.add_position(symbol, pos_type, qty, ltp, stop_loss, target):
            self.lbl_msg.setText(f"✅ {side} {qty} {symbol} @ ₹{ltp:,.2f}")
            self.lbl_msg.setStyleSheet("color: #3fb950; background: #1b2d1b; padding: 10px; border-radius: 4px;")
            
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            self.history_table.setItem(row, 0, QTableWidgetItem(datetime.now().strftime("%H:%M:%S")))
            self.history_table.setItem(row, 1, QTableWidgetItem(symbol))
            self.history_table.setItem(row, 2, QTableWidgetItem(side))
            self.history_table.setItem(row, 3, QTableWidgetItem(str(qty)))
            self.history_table.setItem(row, 4, QTableWidgetItem(f"₹{ltp:,.2f}"))
        else:
            self.lbl_msg.setText("❌ Failed: Check capital or existing position")
            self.lbl_msg.setStyleSheet("color: #f85149; background: #2d1b1b; padding: 10px; border-radius: 4px;")
    
    def _close_position(self, symbol: str):
        """Close an open position."""
        ltp = self._snapshot_store.get_ltp(symbol)
        if ltp <= 0:
            ltp = self.engine.data_fetcher.get_current_price(symbol)
        
        result = self.engine.portfolio.close_position(symbol, ltp, "Manual close")
        if result:
            self.lbl_msg.setText(f"✅ Closed {symbol} @ ₹{ltp:,.2f}")
            self.lbl_msg.setStyleSheet("color: #3fb950; background: #1b2d1b; padding: 10px; border-radius: 4px;")
    
    def closeEvent(self, event):
        """Clean shutdown."""
        if self._price_worker:
            self._price_worker.stop()
            self._price_worker.wait()
        if self._market_scanner:
            self._market_scanner.stop()
            self._market_scanner.wait()
        event.accept()
