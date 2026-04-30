"""
SQLite database manager for healthcare multiples data.
Handles schema creation, upserts, and queries.
"""

import sqlite3
import json
from datetime import date, datetime
from pathlib import Path


class DBManager:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_schema(self):
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS company_snapshots (
                    ticker TEXT NOT NULL,
                    snapshot_date TEXT NOT NULL,
                    name TEXT,
                    segment TEXT,
                    sub_segment TEXT,
                    current_price REAL,
                    market_cap REAL,
                    enterprise_value REAL,
                    total_debt REAL,
                    total_cash REAL,
                    shares_outstanding REAL,
                    fifty_two_week_high REAL,
                    currency TEXT,
                    fy_end_month INTEGER,
                    ltm_revenue REAL,
                    ltm_gross_profit REAL,
                    ltm_ebitda REAL,
                    gross_margin REAL,
                    ebitda_margin REAL,
                    current_fy_rev_est REAL,
                    next_fy_rev_est REAL,
                    current_fy_ebitda_est REAL,
                    next_fy_ebitda_est REAL,
                    current_fy_rev_growth REAL,
                    next_fy_rev_growth REAL,
                    five_year_growth_rate REAL,
                    ntm_revenue REAL,
                    ntm_ebitda REAL,
                    ntm_revenue_growth REAL,
                    pct_52wk_high REAL,
                    ntm_tev_rev REAL,
                    ntm_tev_gp REAL,
                    ntm_tev_ebitda REAL,
                    ltm_tev_rev REAL,
                    ltm_tev_gp REAL,
                    ltm_tev_ebitda REAL,
                    growth_adj_rev REAL,
                    growth_adj_gp REAL,
                    n3y_revenue_cagr REAL,
                    price_change_2w REAL,
                    price_change_2m REAL,
                    data_source TEXT DEFAULT 'yfinance',
                    fetch_timestamp TEXT,
                    PRIMARY KEY (ticker, snapshot_date)
                );

                CREATE TABLE IF NOT EXISTS daily_multiples (
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    segment TEXT,
                    ntm_tev_rev REAL,
                    ntm_tev_ebitda REAL,
                    enterprise_value REAL,
                    ntm_revenue REAL,
                    PRIMARY KEY (ticker, date)
                );

                CREATE TABLE IF NOT EXISTS fetch_log (
                    fetch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fetch_date TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    total_tickers INTEGER,
                    success_count INTEGER,
                    error_count INTEGER,
                    errors_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_segment
                    ON company_snapshots(segment, snapshot_date);
                CREATE INDEX IF NOT EXISTS idx_snapshots_date
                    ON company_snapshots(snapshot_date);
                CREATE INDEX IF NOT EXISTS idx_daily_mult_date
                    ON daily_multiples(date, segment);
            """)

            # --- Migrations for existing databases ---
            # Add new columns if they don't already exist (ALTER TABLE is idempotent with try/except)
            new_cols = [
                ("company_snapshots", "current_fy_ebitda_est", "REAL"),
                ("company_snapshots", "next_fy_ebitda_est", "REAL"),
                ("company_snapshots", "ntm_ebitda", "REAL"),
                ("daily_multiples", "ntm_ebitda", "REAL"),
                ("daily_multiples", "ntm_revenue_growth", "REAL"),
                ("daily_multiples", "gross_margin", "REAL"),
                ("daily_multiples", "ebitda_margin", "REAL"),
            ]
            for table, col, col_type in new_cols:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            conn.commit()
        finally:
            conn.close()

    def upsert_snapshot(self, ticker, snapshot_date, metrics):
        """Insert or replace a company snapshot."""
        conn = self._connect()
        try:
            cols = ["ticker", "snapshot_date"] + list(metrics.keys())
            vals = [ticker, str(snapshot_date)] + list(metrics.values())
            placeholders = ",".join(["?"] * len(vals))
            col_names = ",".join(cols)
            conn.execute(
                f"INSERT OR REPLACE INTO company_snapshots ({col_names}) VALUES ({placeholders})",
                vals,
            )
            conn.commit()
        finally:
            conn.close()

    def upsert_daily_multiple(self, ticker, dt, segment, ntm_tev_rev, ev, ntm_rev,
                              ntm_tev_ebitda=None, ntm_ebitda=None,
                              ntm_revenue_growth=None, gross_margin=None,
                              ebitda_margin=None):
        """Insert or replace a daily multiple record."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO daily_multiples
                   (ticker, date, segment, ntm_tev_rev, ntm_tev_ebitda,
                    enterprise_value, ntm_revenue, ntm_ebitda,
                    ntm_revenue_growth, gross_margin, ebitda_margin)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ticker, str(dt), segment, ntm_tev_rev, ntm_tev_ebitda,
                 ev, ntm_rev, ntm_ebitda,
                 ntm_revenue_growth, gross_margin, ebitda_margin),
            )
            conn.commit()
        finally:
            conn.close()

    def bulk_upsert_daily_multiples(self, rows):
        """Batch-insert historical daily multiples from Excel history sheets.

        Uses INSERT OR REPLACE so corrected Excel values always overwrite stale
        historical rows.  Live-fetcher rows (written by upsert_daily_multiple)
        are also overwritten if the Excel history covers the same date — this is
        intentional: the Excel data is the source of truth for history.

        Args:
            rows: list of dicts with keys: ticker, date, segment,
                  ntm_tev_rev, ntm_tev_ebitda, enterprise_value,
                  ntm_revenue_growth, gross_margin, ebitda_margin
                  (all optional except ticker + date).
        """
        if not rows:
            return
        conn = self._connect()
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO daily_multiples
                   (ticker, date, segment, ntm_tev_rev, ntm_tev_ebitda,
                    enterprise_value, ntm_revenue_growth, gross_margin, ebitda_margin)
                   VALUES (:ticker, :date, :segment,
                           :ntm_tev_rev, :ntm_tev_ebitda, :enterprise_value,
                           :ntm_revenue_growth, :gross_margin, :ebitda_margin)""",
                [
                    {
                        "ticker":             r.get("ticker"),
                        "date":               r.get("date"),
                        "segment":            r.get("segment"),
                        "ntm_tev_rev":        r.get("ntm_tev_rev"),
                        "ntm_tev_ebitda":     r.get("ntm_tev_ebitda"),
                        "enterprise_value":   r.get("enterprise_value"),
                        "ntm_revenue_growth": r.get("ntm_revenue_growth"),
                        "gross_margin":       r.get("gross_margin"),
                        "ebitda_margin":      r.get("ebitda_margin"),
                    }
                    for r in rows
                    if r.get("ticker") and r.get("date")
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def log_fetch(self, total, success, errors_count, errors_list):
        """Log a fetch run."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO fetch_log
                   (fetch_date, start_time, end_time, total_tickers,
                    success_count, error_count, errors_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(date.today()),
                    None,
                    datetime.now().isoformat(),
                    total,
                    success,
                    errors_count,
                    json.dumps(errors_list) if errors_list else "[]",
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_latest_snapshots(self, segment=None):
        """Get the most recent snapshot for each company, optionally filtered by segment."""
        conn = self._connect()
        try:
            if segment:
                rows = conn.execute(
                    """SELECT * FROM company_snapshots
                       WHERE segment = ? AND snapshot_date = (
                           SELECT MAX(snapshot_date) FROM company_snapshots WHERE segment = ?
                       )
                       ORDER BY enterprise_value DESC""",
                    (segment, segment),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM company_snapshots
                       WHERE snapshot_date = (
                           SELECT MAX(snapshot_date) FROM company_snapshots
                       )
                       ORDER BY enterprise_value DESC""",
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_daily_multiples(self, days_back=9999):
        """Get daily multiples for time-series chart."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT ticker, date, segment, ntm_tev_rev, ntm_tev_ebitda,
                          enterprise_value, ntm_revenue,
                          ntm_revenue_growth, gross_margin, ebitda_margin
                   FROM daily_multiples
                   WHERE date >= date('now', ?)
                   ORDER BY date, segment""",
                (f"-{days_back} days",),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_last_fetch_time(self):
        """Get the timestamp of the last successful fetch."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT end_time FROM fetch_log ORDER BY fetch_id DESC LIMIT 1"
            ).fetchone()
            return dict(row)["end_time"] if row else None
        finally:
            conn.close()

    def get_latest_snapshots_for_ticker(self, ticker):
        """Get the most recent snapshot(s) for a specific ticker."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT * FROM company_snapshots
                   WHERE ticker = ?
                   ORDER BY snapshot_date DESC
                   LIMIT 1""",
                (ticker,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_all_latest_snapshots(self):
        """Get the most recent snapshot for ALL companies (across all segments).

        Uses per-segment MAX(snapshot_date) so segments fetched on different
        days are all included.
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT cs.* FROM company_snapshots cs
                   INNER JOIN (
                       SELECT segment, MAX(snapshot_date) AS max_date
                       FROM company_snapshots
                       GROUP BY segment
                   ) seg_max
                   ON cs.segment = seg_max.segment
                      AND cs.snapshot_date = seg_max.max_date
                   ORDER BY cs.enterprise_value DESC""",
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_historical_snapshots(self, days_back=180):
        """Get all snapshots for the last N days for historical analytics.

        Returns one row per (ticker, snapshot_date) for time-series analysis
        such as breadth-over-time charts and repeat-movers detection.
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT snapshot_date, ticker, name, segment,
                          price_change_2w, price_change_2m,
                          ntm_tev_rev, ntm_tev_ebitda, ntm_revenue_growth,
                          ebitda_margin, enterprise_value, gross_margin,
                          ntm_revenue, current_price
                   FROM company_snapshots
                   WHERE snapshot_date >= date('now', ?)
                   ORDER BY snapshot_date, enterprise_value DESC""",
                (f"-{days_back} days",),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_distinct_snapshot_dates(self, days_back=180):
        """Return distinct snapshot dates in the last N days, newest first."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """SELECT DISTINCT snapshot_date
                   FROM company_snapshots
                   WHERE snapshot_date >= date('now', ?)
                   ORDER BY snapshot_date DESC""",
                (f"-{days_back} days",),
            ).fetchall()
            return [r["snapshot_date"] for r in rows]
        finally:
            conn.close()
