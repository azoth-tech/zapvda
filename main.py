"""
Main UI Application for ZapOrion VDA Analyzer
"""
DISPLAY_LIMIT = 5000
import sys
import os
import traceback
import logging

log_dir = os.path.expanduser('~/.zaporion/vda')
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'app.log'))
    ]
)
logger = logging.getLogger(__name__)

from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QDateEdit, QLineEdit, QComboBox,
    QTableView, QProgressBar, QTextEdit, QGroupBox,
    QHeaderView, QMessageBox, QFileDialog, QSpinBox, QDoubleSpinBox,
    QTabWidget, QGridLayout, QStatusBar, QToolBar, QToolButton, QCompleter
)
from PySide6.QtCore import Qt, QThread, Signal, QDate, QAbstractTableModel
from PySide6.QtGui import QFont, QIcon, QAction, QPixmap
import pandas as pd
import matplotlib
import warnings
warnings.filterwarnings('ignore')
matplotlib.use('Agg')
import matplotlib
matplotlib.rcParams['font.family'] = 'sans-serif'
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from database import BhavcopyDB
from downloader import NSEDownloader


class PandasTableModel(QAbstractTableModel):
    """Table model for displaying pandas DataFrames."""

    def __init__(self, data=None):
        super().__init__()
        self._data = data if data is not None else pd.DataFrame()

    def set_data(self, data):
        self.beginResetModel()
        self._data = data
        self.endResetModel()

    def get_data(self):
        return self._data

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._data.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        value = self._data.iloc[index.row(), index.column()]

        if role == Qt.DisplayRole:
            if pd.isna(value):
                return ""
            if isinstance(value, float):
                return f"{value:.4f}"
            return str(value)

        if role == Qt.TextAlignmentRole:
            if isinstance(value, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._data.columns[section])
            if orientation == Qt.Vertical:
                return str(section + 1)
        return None


class DownloadThread(QThread):
    """Background thread for downloading data."""
    progress = Signal(str)
    finished_download = Signal(list)

    def __init__(self, from_date, to_date, db):
        super().__init__()
        self.from_date = from_date
        self.to_date = to_date
        self.db = db
        self.downloader = NSEDownloader()

    def run(self):
        try:
            results = self.downloader.download_range(
                self.from_date, 
                self.to_date,
                progress_callback=lambda r: self.progress.emit(
                    f"{r['date']}: {r['message']}"
                )
            )

            # Insert successful downloads into DB
            for result in results:
                if result['success'] and result['df'] is not None:
                    date_obj = datetime.strptime(result['date'], '%d-%m-%Y')
                    date_str = date_obj.strftime('%d%m%Y')
                    count = self.db.insert_data(result['df'], date_str)
                    self.progress.emit(f"  -> Inserted {count} records into DB")

            self.finished_download.emit(results)
        except Exception as e:
            import traceback
            error_msg = f"Download thread crashed: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.progress.emit(error_msg)
            self.finished_download.emit([])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("MainWindow init start")
        self.setWindowTitle("ZapOrion VDA Analyzer")
        self.setGeometry(100, 100, 1500, 950)

        logger.info("Initializing database...")
        self.db = BhavcopyDB()
        logger.info("Database initialized")

        # Current data
        self.current_data = pd.DataFrame()
        self.current_filters = {}
        self.aggregated_data = pd.DataFrame()

        self._setup_toolbar()
        self._setup_ui()
        self._setup_symbol_completer()
        self._load_initial_data()

    def _setup_symbol_completer(self):
        """Setup autocomplete for symbol fields."""
        symbols = self.db.get_symbols()
        self.symbol_completer = QCompleter(symbols, self.symbol_filter)
        self.symbol_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.symbol_completer.setFilterMode(Qt.MatchContains)
        self.symbol_completer.setMaxVisibleItems(20)
        self.symbol_filter.setCompleter(self.symbol_completer)
        
        self.chart_completer = QCompleter(symbols, self.chart_symbols)
        self.chart_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.chart_completer.setFilterMode(Qt.MatchContains)
        self.chart_completer.setMaxVisibleItems(20)
        self.chart_symbols.setCompleter(self.chart_completer)
        
        self.chart_symbols.textChanged.connect(self._on_chart_text_changed)

    def _on_chart_text_changed(self, text):
        """Handle chart symbol text changes for comma-separated autocomplete."""
        if ',' in text:
            last_part = text.split(',')[-1].strip()
            if last_part:
                self.chart_completer.setCompletionPrefix(last_part)
            else:
                self.chart_completer.setCompletionPrefix('')
        else:
            self.chart_completer.setCompletionPrefix(text)

    def _refresh_symbol_completer(self):
        """Refresh autocomplete list with updated symbols."""
        symbols = self.db.get_symbols()
        self.symbol_completer.model().setStringList(symbols)
        self.chart_completer.model().setStringList(symbols)
        self._on_chart_text_changed(self.chart_symbols.text())

    def _setup_toolbar(self):
        """Setup toolbar with quick actions."""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Export Raw Data action
        export_raw_action = QAction("Export Raw CSV", self)
        export_raw_action.triggered.connect(lambda: self.export_data("raw"))
        toolbar.addAction(export_raw_action)

        # Export Aggregated Data action
        export_agg_action = QAction("Export Aggregated CSV", self)
        export_agg_action.triggered.connect(lambda: self.export_data("aggregated"))
        toolbar.addAction(export_agg_action)

        toolbar.addSeparator()

        # Refresh action
        refresh_action = QAction("Refresh Data", self)
        refresh_action.triggered.connect(self.apply_filters)
        toolbar.addAction(refresh_action)

        # Clear DB action
        clear_db_action = QAction("Clear Database", self)
        clear_db_action.triggered.connect(self.clear_database)
        toolbar.addAction(clear_db_action)

    def _setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # === COLLAPSIBLE DOWNLOAD SECTION ===
        download_collapse_layout = QHBoxLayout()
        download_collapse_layout.setSpacing(2)
        
        self.download_arrow = QLabel("▶")
        self.download_arrow.setStyleSheet("font-size: 11pt; color: #555; padding: 0; margin: 0;")
        self.download_arrow.setFixedWidth(15)
        
        self.download_toggle = QToolButton()
        self.download_toggle.setCheckable(True)
        self.download_toggle.setChecked(True)
        self.download_toggle.setText("Download Data")
        self.download_toggle.setStyleSheet("""
            QToolButton {
                font-weight: bold;
                font-size: 10pt;
                padding: 5px 12px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QToolButton:checked {
                background-color: #1976D2;
            }
            QToolButton::menu-indicator { none; }
        """)
        self.download_toggle.clicked.connect(self.toggle_download)
        
        download_collapse_layout.addWidget(self.download_arrow)
        download_collapse_layout.addWidget(self.download_toggle)
        download_collapse_layout.addStretch()

        self.download_container = QWidget()
        self.download_container.setStyleSheet("border: 2px solid #2196F3; border-radius: 8px;")
        download_inner_layout = QVBoxLayout(self.download_container)
        download_inner_layout.setContentsMargins(10, 15, 10, 10)

        # === DOWNLOAD SECTION ===
        download_group = QGroupBox()
        download_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: none;
                margin-top: 0;
                padding-top: 0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 0px;
                padding: 0;
            }
        """)
        download_layout = QGridLayout(download_group)

        # From Date
        download_layout.addWidget(QLabel("From Date:"), 0, 0)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addDays(-7))
        self.from_date.setDisplayFormat("dd-MM-yyyy")
        download_layout.addWidget(self.from_date, 0, 1)

        # To Date
        download_layout.addWidget(QLabel("To Date:"), 0, 2)
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        self.to_date.setDisplayFormat("dd-MM-yyyy")
        download_layout.addWidget(self.to_date, 0, 3)

        # Download Button
        self.download_btn = QPushButton("Download from NSE")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 6px 15px;
                font-weight: bold;
                font-size: 10pt;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #BDBDBD; }
        """)
        self.download_btn.setFixedWidth(150)
        self.download_btn.clicked.connect(self.start_download)
        download_layout.addWidget(self.download_btn, 0, 4)

        # Load Local CSV Button
        self.load_csv_btn = QPushButton("Load Local CSV")
        self.load_csv_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 6px 15px;
                font-weight: bold;
                font-size: 10pt;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.load_csv_btn.setFixedWidth(130)
        self.load_csv_btn.clicked.connect(self.load_local_csv)
        download_layout.addWidget(self.load_csv_btn, 0, 5)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        download_layout.addWidget(self.progress_bar, 1, 0, 1, 5)

        # Log
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setPlaceholderText("Download log...")
        download_layout.addWidget(self.log_text, 2, 0, 1, 6)

        download_inner_layout.addWidget(download_group)
        main_layout.addWidget(self.download_toggle)
        main_layout.addWidget(self.download_container)

        # === COLLAPSIBLE FILTER SECTION ===
        self.filter_toggle = QToolButton()
        self.filter_toggle.setText("Filters")
        self.filter_toggle.setCheckable(True)
        self.filter_toggle.setChecked(True)
        self.filter_toggle.setStyleSheet("""
            QToolButton {
                font-weight: bold;
                font-size: 10pt;
                padding: 5px 12px;
                background-color: #607D8B;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QToolButton:checked {
                background-color: #455A64;
            }
            QToolButton::menu-indicator { none; }
        """)
        self.filter_toggle.clicked.connect(self.toggle_filters)

        self.filter_container = QWidget()
        self.filter_container.setStyleSheet("border: 2px solid #607D8B; border-radius: 8px;")
        filter_layout = QVBoxLayout(self.filter_container)
        filter_layout.setContentsMargins(10, 15, 10, 10)

        # === FILTER SECTION ===
        filter_group = QGroupBox()
        filter_group.setStyleSheet("""
            QGroupBox {
                border: none;
            }
            QLineEdit, QDateEdit, QDoubleSpinBox, QSpinBox {
                min-height: 28px;
                font-size: 11pt;
            }
        """)
        filter_inner_layout = QGridLayout(filter_group)
        filter_inner_layout.setSpacing(10)

        # Row 0: Symbol, From Date, To Date
        lbl_symbol = QLabel("Symbol:")
        lbl_symbol.setFixedWidth(70)
        lbl_symbol.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_symbol, 0, 0)
        self.symbol_filter = QLineEdit()
        self.symbol_filter.setPlaceholderText("e.g., RELIANCE")
        self.symbol_filter.setFixedWidth(120)
        filter_inner_layout.addWidget(self.symbol_filter, 0, 1)

        lbl_from = QLabel("From:")
        lbl_from.setFixedWidth(50)
        lbl_from.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_from, 0, 2)
        self.filter_from_date = QDateEdit()
        self.filter_from_date.setCalendarPopup(True)
        self.filter_from_date.setDate(QDate(2000, 1, 1))
        self.filter_from_date.setDisplayFormat("dd-MM-yyyy")
        filter_inner_layout.addWidget(self.filter_from_date, 0, 3)

        lbl_to = QLabel("To:")
        lbl_to.setFixedWidth(30)
        lbl_to.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_to, 0, 4)
        self.filter_to_date = QDateEdit()
        self.filter_to_date.setCalendarPopup(True)
        self.filter_to_date.setDate(QDate.currentDate())
        self.filter_to_date.setDisplayFormat("dd-MM-yyyy")
        filter_inner_layout.addWidget(self.filter_to_date, 0, 5)

        # Row 1: Price filters
        lbl_min_price = QLabel("Min Price:")
        lbl_min_price.setFixedWidth(70)
        lbl_min_price.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_min_price, 1, 0)
        self.min_price = QDoubleSpinBox()
        self.min_price.setRange(0, 999999)
        self.min_price.setDecimals(2)
        filter_inner_layout.addWidget(self.min_price, 1, 1)

        lbl_max_price = QLabel("Max Price:")
        lbl_max_price.setFixedWidth(75)
        lbl_max_price.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_max_price, 1, 2)
        self.max_price = QDoubleSpinBox()
        self.max_price.setRange(0, 999999)
        self.max_price.setDecimals(2)
        self.max_price.setValue(999999)
        filter_inner_layout.addWidget(self.max_price, 1, 3)

        lbl_min_vol = QLabel("Min Vol:")
        lbl_min_vol.setFixedWidth(55)
        lbl_min_vol.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_min_vol, 1, 4)
        self.min_volume = QSpinBox()
        self.min_volume.setRange(0, 999999999)
        self.min_volume.setValue(0)
        filter_inner_layout.addWidget(self.min_volume, 1, 5)

        # Row 2: Delivery % and Trade Qty filters
        lbl_deliv_gt = QLabel("Deliv % >")
        lbl_deliv_gt.setFixedWidth(70)
        lbl_deliv_gt.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_deliv_gt, 2, 0)
        self.deliv_per_gt = QDoubleSpinBox()
        self.deliv_per_gt.setRange(0, 100)
        self.deliv_per_gt.setDecimals(2)
        self.deliv_per_gt.setSuffix(" %")
        filter_inner_layout.addWidget(self.deliv_per_gt, 2, 1)

        lbl_deliv_lt = QLabel("Deliv % <")
        lbl_deliv_lt.setFixedWidth(70)
        lbl_deliv_lt.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_deliv_lt, 2, 2)
        self.deliv_per_lt = QDoubleSpinBox()
        self.deliv_per_lt.setRange(0, 100)
        self.deliv_per_lt.setDecimals(2)
        self.deliv_per_lt.setValue(100)
        self.deliv_per_lt.setSuffix(" %")
        filter_inner_layout.addWidget(self.deliv_per_lt, 2, 3)

        lbl_qty_gt = QLabel("Trd Qty >")
        lbl_qty_gt.setFixedWidth(70)
        lbl_qty_gt.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_qty_gt, 2, 4)
        self.ttl_trd_qnty_gt = QSpinBox()
        self.ttl_trd_qnty_gt.setRange(0, 999999999)
        self.ttl_trd_qnty_gt.setValue(0)
        filter_inner_layout.addWidget(self.ttl_trd_qnty_gt, 2, 5)

        lbl_qty_lt = QLabel("Trd Qty <")
        lbl_qty_lt.setFixedWidth(70)
        lbl_qty_lt.setStyleSheet("font-weight: bold;")
        filter_inner_layout.addWidget(lbl_qty_lt, 2, 6)
        self.ttl_trd_qnty_lt = QSpinBox()
        self.ttl_trd_qnty_lt.setRange(0, 999999999)
        self.ttl_trd_qnty_lt.setValue(999999999)
        filter_inner_layout.addWidget(self.ttl_trd_qnty_lt, 2, 7)

        # Row 3: Buttons (centered, spans all columns)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.apply_filter_btn = QPushButton("Apply Filters")
        self.apply_filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 6px 30px;
                font-weight: bold;
                font-size: 10pt;
                border-radius: 4px;
                min-width: 140px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.apply_filter_btn.clicked.connect(self.apply_filters)
        btn_layout.addWidget(self.apply_filter_btn)

        self.clear_filter_btn = QPushButton("Clear Filters")
        self.clear_filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                padding: 6px 30px;
                font-weight: bold;
                font-size: 10pt;
                border-radius: 4px;
                min-width: 140px;
            }
            QPushButton:hover { background-color: #455A64; }
        """)
        self.clear_filter_btn.clicked.connect(self.clear_filters)
        btn_layout.addWidget(self.clear_filter_btn)

        btn_layout.addStretch()
        filter_inner_layout.addLayout(btn_layout, 3, 0, 1, 8)

        # Set column stretch
        filter_inner_layout.setColumnStretch(0, 0)
        filter_inner_layout.setColumnStretch(1, 1)
        filter_inner_layout.setColumnStretch(2, 0)
        filter_inner_layout.setColumnStretch(3, 1)
        filter_inner_layout.setColumnStretch(4, 0)
        filter_inner_layout.setColumnStretch(5, 1)
        filter_inner_layout.setColumnStretch(6, 0)
        filter_inner_layout.setColumnStretch(7, 1)

        filter_layout.addWidget(filter_group)
        main_layout.addWidget(self.filter_toggle)
        main_layout.addWidget(self.filter_container)

        # === TABS: Data View & Aggregation ===
        self.tabs = QTabWidget()

        # Tab 1: Raw Data
        raw_tab = QWidget()
        raw_layout = QVBoxLayout(raw_tab)

        raw_toolbar = QHBoxLayout()
        raw_toolbar.addStretch()

        self.export_raw_btn = QPushButton("Export to CSV")
        self.export_raw_btn.setStyleSheet("background-color: #607D8B; color: white; padding: 5px 15px;")
        self.export_raw_btn.clicked.connect(lambda: self.export_data("raw"))
        raw_toolbar.addWidget(self.export_raw_btn)

        raw_layout.addLayout(raw_toolbar)

        self.data_table = QTableView()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_model = PandasTableModel()
        self.data_table.setModel(self.data_model)
        raw_layout.addWidget(self.data_table)

        self.tabs.addTab(raw_tab, "Raw Data")

        # Tab 2: Aggregated Data
        agg_tab = QWidget()
        agg_layout = QVBoxLayout(agg_tab)

        agg_controls = QHBoxLayout()
        agg_controls.addWidget(QLabel("Group By:"))
        self.agg_groupby = QComboBox()
        self.agg_groupby.addItems(["symbol", "series", "timestamp"])
        agg_controls.addWidget(self.agg_groupby)

        agg_controls.addWidget(QLabel("Aggregation:"))
        self.agg_function = QComboBox()
        self.agg_function.addItems(["sum", "avg", "max", "min", "count"])
        agg_controls.addWidget(self.agg_function)

        self.agg_apply_btn = QPushButton("Apply Aggregation")
        self.agg_apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                padding: 6px 15px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #7B1FA2; }
        """)
        self.agg_apply_btn.clicked.connect(self.apply_aggregation)
        agg_controls.addWidget(self.agg_apply_btn)

        agg_controls.addStretch()

        self.export_agg_btn = QPushButton("Export to CSV")
        self.export_agg_btn.setStyleSheet("background-color: #607D8B; color: white; padding: 5px 15px;")
        self.export_agg_btn.clicked.connect(lambda: self.export_data("aggregated"))
        agg_controls.addWidget(self.export_agg_btn)

        agg_layout.addLayout(agg_controls)

        self.agg_table = QTableView()
        self.agg_table.setAlternatingRowColors(True)
        self.agg_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.agg_model = PandasTableModel()
        self.agg_table.setModel(self.agg_model)
        agg_layout.addWidget(self.agg_table)

        self.tabs.addTab(agg_tab, "Aggregated Data")

        # Tab 3: Chart
        chart_tab = QWidget()
        chart_layout = QVBoxLayout(chart_tab)

        chart_controls = QHBoxLayout()

        chart_controls.addWidget(QLabel("Symbols:"))
        self.chart_symbols = QLineEdit()
        self.chart_symbols.setPlaceholderText("e.g., RELIANCE,INFY,TCS")
        self.chart_symbols.setFixedWidth(250)
        chart_controls.addWidget(self.chart_symbols)

        chart_controls.addWidget(QLabel("Y-Axis:"))
        self.chart_y_field = QComboBox()
        self.chart_y_field.addItems(["close", "open", "high", "low", "ttl_trd_qnty", "deliv_qty", "deliv_per"])
        chart_controls.addWidget(self.chart_y_field)

        self.chart_plot_btn = QPushButton("Plot Chart")
        self.chart_plot_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 6px 20px;
                font-weight: bold;
                font-size: 10pt;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.chart_plot_btn.clicked.connect(self.plot_chart)
        chart_controls.addWidget(self.chart_plot_btn)

        chart_controls.addStretch()

        chart_layout.addLayout(chart_controls)

        self.chart_canvas = None
        self.chart_figure = Figure(figsize=(10, 6))
        self.chart_canvas = FigureCanvasQTAgg(self.chart_figure)
        chart_layout.addWidget(self.chart_canvas)

        self.tabs.addTab(chart_tab, "Charts")

        main_layout.addWidget(self.tabs, stretch=1)

        # === STATUS BAR ===
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Stats label
        self.stats_label = QLabel("No data loaded")
        self.stats_label.setStyleSheet("padding: 5px; color: #666; font-weight: bold;")
        main_layout.addWidget(self.stats_label)

    def _load_initial_data(self):
        """Load existing data from database on startup."""
        self.apply_filters()
        self._update_stats()

    def _update_stats(self):
        """Update database statistics."""
        stats = self.db.get_date_range()
        if stats[0]:
            self.stats_label.setText(
                f"Database: {stats[2]} days | {stats[3]:,} records | "
                f"Range: {stats[0]} to {stats[1]}"
            )
        else:
            self.stats_label.setText("Database is empty. Download data to get started.")

    def start_download(self):
        """Start downloading data in background thread."""
        from_dt = self.from_date.date().toPython()
        to_dt = self.to_date.date().toPython()

        if from_dt > to_dt:
            QMessageBox.warning(self, "Invalid Date", "From date must be before To date")
            return

        days = (to_dt - from_dt).days + 1
        self.progress_bar.setMaximum(days)
        self.progress_bar.setValue(0)
        self.download_btn.setEnabled(False)
        self.log_text.clear()
        self.log_text.append(f"Starting download for {days} days...")

        self.download_thread = DownloadThread(from_dt, to_dt, self.db)
        self.download_thread.progress.connect(self._on_download_progress)
        self.download_thread.finished_download.connect(self._on_download_finished)
        self.download_thread.start()

    def _on_download_progress(self, message):
        """Handle download progress updates."""
        self.log_text.append(message)
        current = self.progress_bar.value() + 1
        self.progress_bar.setValue(min(current, self.progress_bar.maximum()))

    def _on_download_finished(self, results):
        """Handle download completion."""
        self.download_btn.setEnabled(True)
        successful = sum(1 for r in results if r['success'])
        total_records = sum(r['records'] for r in results if r['success'])

        self.log_text.append(f"\nComplete! {successful}/{len(results)} days downloaded. {total_records:,} total records.")
        QMessageBox.information(
            self, "Download Complete",
            f"Downloaded {successful} files\nTotal records: {total_records:,}"
        )

        self._update_stats()
        self.apply_filters()
        self._refresh_symbol_completer()

    def load_local_csv(self):
        """Load a local CSV file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Bhavcopy CSV", "", "CSV Files (*.csv)"
        )
        if not filepath:
            return

        # Try to extract date from filename
        filename = os.path.basename(filepath)
        date_str = None

        # Try pattern: sec_bhavdata_full_29042026.csv or bhavcopy_29042026.csv
        import re
        match = re.search(r'(\d{8})', filename)
        if match:
            date_str = match.group(1)
        else:
            # Use current date as fallback
            date_str = datetime.now().strftime('%d%m%Y')

        downloader = NSEDownloader()
        result = downloader.load_local_csv(filepath, date_str)

        if result['success']:
            count = self.db.insert_data(result['df'], date_str)
            QMessageBox.information(
                self, "Success",
                f"Loaded {count} records from {filename}"
            )
            self._update_stats()
            self.apply_filters()
        else:
            QMessageBox.warning(self, "Error", result['message'])

    def toggle_download(self):
        """Toggle download section visibility."""
        if self.download_toggle.isChecked():
            self.download_container.show()
        else:
            self.download_container.hide()

    def toggle_filters(self):
        """Toggle filter section visibility."""
        if self.filter_toggle.isChecked():
            self.filter_container.show()
        else:
            self.filter_container.hide()

    def apply_filters(self):
        """Apply filters and display data."""
        filters = {
            'symbol': self.symbol_filter.text().upper().strip(),
            'from_date': self.filter_from_date.date().toPython(),
            'to_date': self.filter_to_date.date().toPython(),
            'min_price': self.min_price.value() if self.min_price.value() > 0 else None,
            'max_price': self.max_price.value() if self.max_price.value() < 999999 else None,
            'min_volume': self.min_volume.value() if self.min_volume.value() > 0 else None,
            'deliv_per_gt': self.deliv_per_gt.value() if self.deliv_per_gt.value() > 0 else None,
            'deliv_per_lt': self.deliv_per_lt.value() if self.deliv_per_lt.value() < 100 else None,
            'ttl_trd_qnty_gt': self.ttl_trd_qnty_gt.value() if self.ttl_trd_qnty_gt.value() > 0 else None,
            'ttl_trd_qnty_lt': self.ttl_trd_qnty_lt.value() if self.ttl_trd_qnty_lt.value() < 999999999 else None,
        }

        # Remove empty filters
        filters = {k: v for k, v in filters.items() if v}

        try:
            total_count = self.db.get_data_count(filters=filters)
            df = self.db.get_data(filters=filters, limit=DISPLAY_LIMIT)
            self.current_data = df
            self.current_filters = filters
            self.data_model.set_data(df)

            # Auto-resize columns
            self.data_table.resizeColumnsToContents()

            if total_count > DISPLAY_LIMIT:
                self.status_bar.showMessage(f"Showing {len(df):,} of {total_count:,} records (export to get all)")
            else:
                self.status_bar.showMessage(f"Showing {len(df):,} records")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")

    def clear_filters(self):
        """Clear all filters."""
        self.symbol_filter.clear()
        self.filter_from_date.setDate(QDate(2000, 1, 1))
        self.filter_to_date.setDate(QDate.currentDate())
        self.min_price.setValue(0)
        self.max_price.setValue(999999)
        self.min_volume.setValue(0)
        self.deliv_per_gt.setValue(0)
        self.deliv_per_lt.setValue(100)
        self.ttl_trd_qnty_gt.setValue(0)
        self.ttl_trd_qnty_lt.setValue(999999999)
        self.apply_filters()

    def apply_aggregation(self):
        """Apply aggregation and display results."""
        group_by = self.agg_groupby.currentText()
        agg_type = self.agg_function.currentText()

        filters = {
            'symbol': self.symbol_filter.text().upper().strip(),
            'from_date': self.filter_from_date.date().toPython(),
            'to_date': self.filter_to_date.date().toPython()
        }
        filters = {k: v for k, v in filters.items() if v}

        try:
            df = self.db.get_aggregated_data(group_by=group_by, agg_type=agg_type, filters=filters)
            self.aggregated_data = df
            self.agg_model.set_data(df)
            self.agg_table.resizeColumnsToContents()

            self.status_bar.showMessage(f"Aggregation: {len(df):,} groups")
            self.tabs.setCurrentIndex(1)  # Switch to aggregation tab
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Aggregation failed: {str(e)}")

    def export_data(self, data_type):
        """Export current data to CSV file."""
        if data_type == "raw":
            default_name = f"nse_raw_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df = self.db.get_data(filters=self.current_filters)
        else:
            df = self.agg_model.get_data()
            default_name = f"nse_aggregated_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        if df.empty:
            QMessageBox.warning(self, "No Data", "No data to export. Apply filters or aggregation first.")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV", default_name, "CSV Files (*.csv)"
        )

        if not filepath:
            return

        try:
            df.to_csv(filepath, index=False)
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {len(df):,} rows to {filepath}"
            )
            self.status_bar.showMessage(f"Exported to {os.path.basename(filepath)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")

    def clear_database(self):
        """Clear all data from database."""
        reply = QMessageBox.question(
            self, "Confirm Clear",
            "Are you sure you want to delete ALL data from the database?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.db.conn.execute("DELETE FROM bhavcopy_data")
                self._update_stats()
                self.apply_filters()
                self.agg_model.set_data(pd.DataFrame())
                QMessageBox.information(self, "Cleared", "Database has been cleared.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear database: {str(e)}")

    def plot_chart(self):
        """Plot time-series chart for selected symbols."""
        symbols_text = self.chart_symbols.text().strip().upper()
        if not symbols_text:
            QMessageBox.warning(self, "No Symbols", "Please enter at least one symbol")
            return

        symbols = [s.strip() for s in symbols_text.split(',') if s.strip()]
        if not symbols:
            QMessageBox.warning(self, "No Symbols", "Please enter valid symbols")
            return

        if len(symbols) > 10:
            QMessageBox.warning(self, "Too Many Symbols", "Maximum 10 symbols allowed")
            return

        y_field = self.chart_y_field.currentText()

        from_date = self.filter_from_date.date().toPython()
        to_date = self.filter_to_date.date().toPython()

        try:
            df = self.db.get_chart_data(symbols, y_field, from_date, to_date)

            if df.empty:
                QMessageBox.warning(self, "No Data", "No data found for the selected symbols and date range")
                return

            self.chart_figure.clear()

            ax = self.chart_figure.add_subplot(111)

            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                      '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

            for idx, symbol in enumerate(symbols):
                symbol_data = df[df['symbol'] == symbol]
                if not symbol_data.empty:
                    ax.plot(
                        symbol_data['timestamp'],
                        symbol_data[y_field],
                        label=symbol,
                        color=colors[idx % len(colors)],
                        linewidth=1.5,
                        marker='o',
                        markersize=2
                    )

            ax.set_xlabel('Date', fontsize=11)
            ax.set_ylabel(y_field.replace('_', ' ').title(), fontsize=11)
            ax.set_title(f'{y_field.replace("_", " ").title()} vs Date', fontsize=13, fontweight='bold')
            ax.legend(loc='best', framealpha=0.9)
            ax.grid(True, alpha=0.3)

            ax.tick_params(axis='x', rotation=45)

            self.chart_figure.tight_layout()
            self.chart_figure.canvas.draw()

            self.status_bar.showMessage(f"Chart: {len(symbols)} symbols, {len(df)} data points")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot chart: {str(e)}")

    def closeEvent(self, event):
        """Clean up on close."""
        self.db.close()
        event.accept()


def main():
    logger.info("Starting application...")
    app = QApplication(sys.argv)
    logger.info("QApplication created")
    app.setStyle('Fusion')

    if hasattr(sys, 'frozen'):
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
        if sys.platform == 'darwin':
            cert_path = os.path.join(os.path.dirname(sys.executable), '..', 'Resources', 'certifi', 'cacert.pem')
        else:
            cert_path = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
        os.environ['SSL_CERT_FILE'] = os.path.normpath(cert_path)
        logger.info(f"SSL_CERT_FILE set to {os.environ['SSL_CERT_FILE']}")

    # Show splash screen
    if hasattr(sys, 'frozen'):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    splash_path = os.path.join(base_dir, 'splash.jpeg')
    splash = None
    if os.path.exists(splash_path):
        pixmap = QPixmap(splash_path)
        from PySide6.QtWidgets import QSplashScreen
        splash = QSplashScreen(pixmap)
        splash.show()
        app.processEvents()

    font = QFont("Helvetica Neue", 11)
    app.setFont(font)

    logger.info("Creating MainWindow...")
    window = MainWindow()
    logger.info("MainWindow created")
    window.show()

    if splash:
        splash.finish(window)

    logger.info("Window shown, entering event loop...")
    sys.exit(app.exec())


if __name__ == "__main__":
    import traceback
    import os
    log_dir = os.path.expanduser("~/.zaporion/vda")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "error.log")

    try:
        main()
    except Exception as e:
        with open(log_file, "w") as f:
            f.write(f"Error: {e}\n\n{traceback.format_exc()}")
        print(f"Error: {e}\nCheck log: {log_file}")
