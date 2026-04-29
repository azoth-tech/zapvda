# vda

vda is a lightweight desktop application to download, store, and analyze NSE (National Stock Exchange of India) Bhavcopy data.

## Features

- **Download Data**: Automatically downloads ZIP files from NSE archives for a date range
- **Local CSV Support**: Load existing bhavcopy CSV files
- **Data Storage**: Uses DuckDB (embedded, no server needed) for fast analytical queries
- **Filtering**: Filter by symbol, series, date range, price range, and volume
- **Aggregation**: Group data by symbol/series/date with SUM/AVG/MAX/MIN/COUNT functions
- **Export**: Save filtered or aggregated data to CSV files
- **Fast Performance**: Handles millions of records efficiently
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Quick Start (Easiest)

### Windows
```bash
run.bat
```

### macOS / Linux
```bash
./run.sh
```

The startup scripts will **automatically**:
1. Create a virtual environment (`venv/`)
2. Install all dependencies into it
3. Launch the application

No manual setup needed!

---

## Manual Installation

If you prefer to set up manually, follow these steps:

### Prerequisites
- Python 3.10 or higher
- pip

### Step 1: Create Virtual Environment

This avoids the `externally-managed-environment` error on macOS and keeps dependencies isolated.

#### Windows
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

#### macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Step 2: Run the Application

After the virtual environment is activated:
```bash
python main.py
```

To run again later, just activate the venv and run:
```bash
# Windows
venv\Scripts\activate
python main.py

# macOS / Linux
source venv/bin/activate
python main.py
```

---

## Usage Guide

### Downloading Data from NSE

1. Set **From Date** and **To Date** in the Download section
2. Click **"Download from NSE"**
3. The app will download ZIP files for each trading day, extract CSVs, and store in DuckDB
4. Progress is shown in the log area

### Loading Local CSV Files

1. Click **"Load Local CSV"**
2. Select a bhavcopy CSV file (e.g., `sec_bhavdata_full_29042026.csv`)
3. The app will detect the date from filename and import into database

### Filtering Data

Use the Filter panel to narrow down results:
- **Symbol**: Partial match (e.g., "RELI" matches RELIANCE)
- **Series**: EQ, BE, BZ, etc.
- **Date Range**: From/To dates
- **Price Range**: Min/Max close price
- **Volume**: Minimum traded quantity

Click **"Apply Filters"** to update the table.

### Aggregation

Switch to the **"Aggregated Data"** tab:
1. Select **Group By** field (symbol, series, or timestamp)
2. Select **Aggregation** function (sum, avg, max, min, count)
3. Click **"Apply Aggregation"**

### Exporting Data

- **Toolbar**: Use "Export Raw CSV" or "Export Aggregated CSV" from the toolbar
- **Tab Buttons**: Each tab has its own "Export to CSV" button
- Exports use the current filter/aggregation settings
- Files are saved with timestamps: `nse_raw_export_YYYYMMDD_HHMMSS.csv`

### Clearing Database

Click **"Clear Database"** in the toolbar to remove all data. This requires confirmation.

---

## Project Structure

```
nse_bhavcopy_app/
├── main.py                   # Main UI application
├── database.py               # DuckDB database operations
├── downloader.py             # NSE download logic
├── requirements.txt          # Python dependencies
├── run.bat                   # Windows startup script (auto-venv)
├── run.sh                    # macOS/Linux startup script (auto-venv)
├── vda.spec                  # PyInstaller spec for EXE build
├── BUILD_EXE.md              # Instructions to build standalone EXE
├── README.md                 # This file
├── .gitignore                # Git ignore rules
├── venv/                     # Virtual environment (auto-created)
├── bhavcopy.db               # Local database (auto-created)
└── downloads/                # Downloaded CSV files (auto-created)
```

---

## URL Format

The app downloads from NSE using this URL pattern:
```
https://www.nseindia.com/api/zipem?fileURLs=["https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv"]&type=Daily
```

Where `DDMMYYYY` is replaced with the actual date.

---

## Building Standalone EXE (Windows)

See `BUILD_EXE.md` for detailed instructions.

Quick build:
```bash
# Windows
venv\Scripts\activate
pip install pyinstaller
pyinstaller NSE_Bhavcopy_Viewer.spec --clean

# Output: dist/NSE_Bhavcopy_Viewer.exe
```

---

## Notes

- NSE data is only available for trading days (Mon-Fri, excluding holidays)
- The app automatically skips weekends
- Weekend dates will show "Weekend - skipped" in the log
- Downloaded CSVs are saved in the `downloads/` folder for reference
- Database is stored in `bhavcopy.db` (portable, single file)
- Virtual environment (`venv/`) keeps dependencies isolated from system Python

---

## Troubleshooting

### "externally-managed-environment" error (macOS/Linux)

This happens on newer Python versions. **Solution**: Use the provided `run.sh` script, or create a virtual environment manually:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### "HTTP 403" or "Network error"
- NSE may block automated requests. Try:
  - Using a VPN
  - Waiting a few minutes between requests
  - Loading local CSV files instead

### "No CSV found in ZIP"
- The NSE API format may have changed
- Try loading the CSV directly using "Load Local CSV"

### Application won't start
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (need 3.10+)
- Make sure virtual environment is activated

### macOS Security Warning
If you see "cannot be opened because the developer cannot be verified":
1. Go to **System Preferences → Security & Privacy → General**
2. Click **"Open Anyway"**
3. Or right-click the app and select **"Open"**

---

## Tech Stack

- **UI**: PySide6 (Qt6) - Native desktop widgets
- **Database**: DuckDB - Embedded analytical database
- **CSV Parsing**: Polars - Fast DataFrame library
- **HTTP**: Requests - With session cookies for NSE

## License

MIT License - Free to use and modify.
