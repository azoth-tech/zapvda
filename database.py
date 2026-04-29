"""
Database module using DuckDB for ZapOrion VDA Analyzer data storage and queries.
"""
import duckdb
import os
from datetime import datetime
import polars as pl

class BhavcopyDB:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.expanduser("~/.zaporion/vda/vda.db")
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.db_path = db_path
        import glob
        for lock_file in glob.glob(f"{db_path}*"):
            if 'lock' in lock_file or 'wal' in lock_file or 'shm' in lock_file:
                try:
                    os.remove(lock_file)
                except:
                    pass
        self.conn = duckdb.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        """Initialize database tables."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bhavcopy_data (
                timestamp DATE,
                symbol VARCHAR,
                series VARCHAR,
                open DECIMAL(15,4),
                high DECIMAL(15,4),
                low DECIMAL(15,4),
                close DECIMAL(15,4),
                ttl_trd_qnty BIGINT,
                deliv_qty BIGINT,
                deliv_per DECIMAL(8,4)
            )
        """)

        # Create indexes for faster filtering
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON bhavcopy_data(symbol)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON bhavcopy_data(timestamp)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_series ON bhavcopy_data(series)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_date ON bhavcopy_data(symbol, timestamp)")

    def insert_data(self, df: pl.DataFrame, date_str: str):
        """Insert CSV data into database - only equities (SERIES=EQ)."""
        if df.is_empty():
            return 0

        # Filter for only equities (SERIES=EQ)
        df = df.filter(pl.col('SERIES') == 'EQ')

        if df.is_empty():
            return 0

        # Convert polars DataFrame to DuckDB
        date_obj = datetime.strptime(date_str, "%d%m%Y").date()

        # Add date column and rename columns to match schema
        df = df.with_columns([
            pl.lit(date_obj).alias("timestamp")
        ])

        # Rename columns to match schema (only keep required fields)
        column_mapping = {
            "SYMBOL": "symbol",
            "SERIES": "series",
            "OPEN_PRICE": "open",
            "HIGH_PRICE": "high",
            "LOW_PRICE": "low",
            "CLOSE_PRICE": "close",
            "TTL_TRD_QNTY": "ttl_trd_qnty",
            "DELIV_QTY": "deliv_qty",
            "DELIV_PER": "deliv_per"
        }

        # Rename columns that exist
        for old, new in column_mapping.items():
            if old in df.columns:
                df = df.rename({old: new})

        # Register temp table and insert
        self.conn.register("temp_df", df.to_pandas())

        # Check if data for this date already exists
        existing = self.conn.execute(
            "SELECT COUNT(*) FROM bhavcopy_data WHERE timestamp = ?", [date_obj]
        ).fetchone()[0]

        if existing > 0:
            # Delete existing data for this date
            self.conn.execute("DELETE FROM bhavcopy_data WHERE timestamp = ?", [date_obj])

        # Insert only required fields
        self.conn.execute("""
            INSERT INTO bhavcopy_data 
            (timestamp, symbol, series, open, high, low, close, ttl_trd_qnty, deliv_qty, deliv_per)
            SELECT timestamp, symbol, series, open, high, low, close, ttl_trd_qnty, deliv_qty, deliv_per
            FROM temp_df
        """)

        self.conn.unregister("temp_df")
        return len(df)

    def get_data(self, filters=None, order_by=None, limit=None):
        """Query data with filters."""
        query = "SELECT * FROM bhavcopy_data WHERE 1=1"
        params = []

        if filters:
            if 'symbol' in filters and filters['symbol']:
                query += " AND symbol LIKE ?"
                params.append(f"%{filters['symbol']}%")
            if 'from_date' in filters and filters['from_date']:
                query += " AND timestamp >= ?"
                params.append(filters['from_date'])
            if 'to_date' in filters and filters['to_date']:
                query += " AND timestamp <= ?"
                params.append(filters['to_date'])
            if 'min_price' in filters and filters['min_price']:
                query += " AND close >= ?"
                params.append(float(filters['min_price']))
            if 'max_price' in filters and filters['max_price']:
                query += " AND close <= ?"
                params.append(float(filters['max_price']))
            if 'min_volume' in filters and filters['min_volume']:
                query += " AND ttl_trd_qnty >= ?"
                params.append(int(filters['min_volume']))
            if 'deliv_per_gt' in filters and filters['deliv_per_gt']:
                query += " AND deliv_per >= ?"
                params.append(float(filters['deliv_per_gt']))
            if 'deliv_per_lt' in filters and filters['deliv_per_lt']:
                query += " AND deliv_per <= ?"
                params.append(float(filters['deliv_per_lt']))
            if 'ttl_trd_qnty_gt' in filters and filters['ttl_trd_qnty_gt']:
                query += " AND ttl_trd_qnty >= ?"
                params.append(int(filters['ttl_trd_qnty_gt']))
            if 'ttl_trd_qnty_lt' in filters and filters['ttl_trd_qnty_lt']:
                query += " AND ttl_trd_qnty <= ?"
                params.append(int(filters['ttl_trd_qnty_lt']))

        if order_by:
            query += f" ORDER BY {order_by}"
        else:
            query += " ORDER BY timestamp DESC, symbol"

        if limit:
            query += f" LIMIT {limit}"

        result = self.conn.execute(query, params).fetchdf()
        return result

    def get_data_count(self, filters=None):
        """Get count of filtered records."""
        query = "SELECT COUNT(*) as cnt FROM bhavcopy_data WHERE 1=1"
        params = []

        if filters:
            if 'symbol' in filters and filters['symbol']:
                query += " AND symbol LIKE ?"
                params.append(f"%{filters['symbol']}%")
            if 'from_date' in filters and filters['from_date']:
                query += " AND timestamp >= ?"
                params.append(filters['from_date'])
            if 'to_date' in filters and filters['to_date']:
                query += " AND timestamp <= ?"
                params.append(filters['to_date'])
            if 'min_price' in filters and filters['min_price']:
                query += " AND close >= ?"
                params.append(float(filters['min_price']))
            if 'max_price' in filters and filters['max_price']:
                query += " AND close <= ?"
                params.append(float(filters['max_price']))
            if 'min_volume' in filters and filters['min_volume']:
                query += " AND ttl_trd_qnty >= ?"
                params.append(int(filters['min_volume']))
            if 'deliv_per_gt' in filters and filters['deliv_per_gt']:
                query += " AND deliv_per >= ?"
                params.append(float(filters['deliv_per_gt']))
            if 'deliv_per_lt' in filters and filters['deliv_per_lt']:
                query += " AND deliv_per <= ?"
                params.append(float(filters['deliv_per_lt']))
            if 'ttl_trd_qnty_gt' in filters and filters['ttl_trd_qnty_gt']:
                query += " AND ttl_trd_qnty >= ?"
                params.append(int(filters['ttl_trd_qnty_gt']))
            if 'ttl_trd_qnty_lt' in filters and filters['ttl_trd_qnty_lt']:
                query += " AND ttl_trd_qnty <= ?"
                params.append(int(filters['ttl_trd_qnty_lt']))

        result = self.conn.execute(query, params).fetchone()
        return result[0]

    def get_aggregated_data(self, group_by='symbol', agg_type='sum', filters=None):
        """Get aggregated data."""
        agg_funcs = {
            'sum': 'SUM',
            'avg': 'AVG',
            'max': 'MAX',
            'min': 'MIN',
            'count': 'COUNT'
        }

        func = agg_funcs.get(agg_type, 'SUM')

        query = f"""
            SELECT 
                {group_by},
                {func}(close) as agg_close,
                {func}(ttl_trd_qnty) as agg_volume,
                COUNT(*) as record_count,
                MIN(timestamp) as from_date,
                MAX(timestamp) as to_date
            FROM bhavcopy_data 
            WHERE 1=1
        """
        params = []

        if filters:
            if 'symbol' in filters and filters['symbol']:
                query += " AND symbol LIKE ?"
                params.append(f"%{filters['symbol']}%")
            if 'series' in filters and filters['series']:
                query += " AND series = ?"
                params.append(filters['series'])
            if 'from_date' in filters and filters['from_date']:
                query += " AND timestamp >= ?"
                params.append(filters['from_date'])
            if 'to_date' in filters and filters['to_date']:
                query += " AND timestamp <= ?"
                params.append(filters['to_date'])

        query += f" GROUP BY {group_by}"
        query += f" ORDER BY agg_volume DESC"

        result = self.conn.execute(query, params).fetchdf()
        return result

    def get_date_range(self):
        """Get min and max dates in database."""
        result = self.conn.execute("""
            SELECT MIN(timestamp) as min_date, MAX(timestamp) as max_date,
                   COUNT(DISTINCT timestamp) as total_days,
                   COUNT(*) as total_records
            FROM bhavcopy_data
        """).fetchone()
        return result

    def get_symbols(self):
        """Get distinct symbols."""
        result = self.conn.execute("""
            SELECT DISTINCT symbol FROM bhavcopy_data ORDER BY symbol
        """).fetchdf()
        return result['symbol'].tolist()

    def get_series(self):
        """Get distinct series."""
        result = self.conn.execute("""
            SELECT DISTINCT series FROM bhavcopy_data ORDER BY series
        """).fetchdf()
        return result['series'].tolist()

    def get_chart_data(self, symbols, y_field, from_date, to_date):
        """Get data for charting - returns time-series for each symbol."""
        if not symbols:
            return pd.DataFrame()

        symbol_list = "', '".join(symbols)
        query = f"""
            SELECT timestamp, symbol, {y_field}
            FROM bhavcopy_data
            WHERE symbol IN ('{symbol_list}')
              AND timestamp >= ?
              AND timestamp <= ?
            ORDER BY timestamp, symbol
        """

        result = self.conn.execute(query, [from_date, to_date]).fetchdf()
        return result

    def close(self):
        self.conn.close()

    def __del__(self):
        try:
            self.conn.close()
        except:
            pass
