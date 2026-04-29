"""
Downloader module for ZapOrion VDA Analyzer.
"""
import requests
import zipfile
import io
import os
from datetime import datetime, timedelta
import polars as pl
import time

class NSEDownloader:
    def __init__(self, download_dir="downloads"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

        # NSE requires specific headers to avoid blocking
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _get_url(self, date_obj: datetime) -> str:
        """Generate download URL for a given date."""
        date_str = date_obj.strftime("%d%m%Y")
        csv_url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{date_str}.csv"

        # The API endpoint that returns ZIP
        import urllib.parse
        file_urls = urllib.parse.quote(f'["{csv_url}"]')
        url = f"https://www.nseindia.com/api/zipem?fileURLs={file_urls}&type=Daily"
        return url, date_str

    def _is_trading_day(self, date_obj: datetime) -> bool:
        """Check if date is a weekday (Mon-Fri)."""
        return date_obj.weekday() < 5

    def download_date(self, date_obj: datetime, progress_callback=None) -> dict:
        """Download and extract CSV for a single date."""
        result = {
            'date': date_obj.strftime('%d-%m-%Y'),
            'success': False,
            'records': 0,
            'message': '',
            'df': None
        }

        if not self._is_trading_day(date_obj):
            result['message'] = 'Weekend - skipped'
            return result

        url, date_str = self._get_url(date_obj)

        try:
            # First, visit the main page to get cookies
            self.session.get("https://www.nseindia.com", timeout=10)
            time.sleep(0.5)

            # Download the ZIP file
            response = self.session.get(url, timeout=30, allow_redirects=True)

            if response.status_code != 200:
                result['message'] = f'HTTP {response.status_code}'
                return result

            # Check if response is actually a ZIP
            content_type = response.headers.get('Content-Type', '')

            # Try to handle as ZIP
            try:
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    # Find CSV file in ZIP
                    csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                    if not csv_files:
                        result['message'] = 'No CSV found in ZIP'
                        return result

                    # Read the first CSV file
                    with z.open(csv_files[0]) as csv_file:
                        df = pl.read_csv(csv_file)
                        df.columns = [c.strip() for c in df.columns]
                        df = df.with_columns([pl.col(pl.Utf8).str.strip_chars()])
                        df = df.with_columns(
                            pl.col('DELIV_QTY').str.replace('-', '0').str.replace('', '0').cast(pl.Int64),
                            pl.col('DELIV_PER').str.replace('-', '0').str.replace('', '0').cast(pl.Float64),
                            pl.col('TTL_TRD_QNTY').cast(pl.Int64),
                            pl.col('TURNOVER_LACS').cast(pl.Float64),
                            pl.col('NO_OF_TRADES').cast(pl.Int64),
                        )

                        # Save extracted CSV for reference
                        extract_path = os.path.join(self.download_dir, f"bhavcopy_{date_str}.csv")
                        df.write_csv(extract_path)

                        result['success'] = True
                        result['records'] = len(df)
                        result['message'] = f'Downloaded {len(df)} records'
                        result['df'] = df

            except zipfile.BadZipFile:
                # Sometimes NSE returns CSV directly instead of ZIP
                try:
                    df = pl.read_csv(io.BytesIO(response.content))
                    df.columns = [c.strip() for c in df.columns]
                    df = df.with_columns([pl.col(pl.Utf8).str.strip_chars()])
                    df = df.with_columns(
                        pl.col('DELIV_QTY').str.replace('-', '0').str.replace('', '0').cast(pl.Int64),
                        pl.col('DELIV_PER').str.replace('-', '0').str.replace('', '0').cast(pl.Float64),
                        pl.col('TTL_TRD_QNTY').cast(pl.Int64),
                        pl.col('TURNOVER_LACS').cast(pl.Float64),
                        pl.col('NO_OF_TRADES').cast(pl.Int64),
                    )
                    extract_path = os.path.join(self.download_dir, f"bhavcopy_{date_str}.csv")
                    df.write_csv(extract_path)

                    result['success'] = True
                    result['records'] = len(df)
                    result['message'] = f'Downloaded {len(df)} records (direct CSV)'
                    result['df'] = df
                except Exception as e:
                    result['message'] = f'Not a valid ZIP or CSV: {str(e)}'

        except requests.exceptions.RequestException as e:
            result['message'] = f'Network error: {str(e)}'
        except Exception as e:
            result['message'] = f'Error: {str(e)}'

        if progress_callback:
            progress_callback(result)

        return result

    def download_range(self, from_date: datetime, to_date: datetime, progress_callback=None):
        """Download data for a date range."""
        results = []
        current = from_date

        while current <= to_date:
            result = self.download_date(current, progress_callback)
            results.append(result)
            current += timedelta(days=1)
            time.sleep(0.3)  # Be nice to the server

        return results

    def load_local_csv(self, filepath: str, date_str: str) -> dict:
        """Load a local CSV file."""
        result = {
            'date': date_str,
            'success': False,
            'records': 0,
            'message': '',
            'df': None
        }

        try:
            df = pl.read_csv(filepath)
            result['success'] = True
            result['records'] = len(df)
            result['message'] = f'Loaded {len(df)} records'
            result['df'] = df
        except Exception as e:
            result['message'] = f'Error loading CSV: {str(e)}'

        return result
