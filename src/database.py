"""Database persistence layer using SQLite for storing monitoring records and watchlist targets."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Generator
import pandas as pd


DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "monitoring.db")


class DatabaseManager:
    """Manages SQLite database connections, schema migrations, and queries."""
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """Initialize the database manager with target SQLite file path.
        
        Args:
            db_path: Filesystem path to the SQLite database file.
        """
        self.db_path = db_path
        self._ensure_directory()
        self.init_db()

    def _ensure_directory(self) -> None:
        """Create parent directory for database file if it does not exist."""
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Create and yield a SQLite connection, automatically closing it on exit.
        
        Yields:
            sqlite3.Connection with row_factory set to sqlite3.Row.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """Initialize database schema by creating required tables and indexes."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Table for recording historical check results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monitoring_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    checked_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    status_code INTEGER,
                    response_time_ms REAL,
                    resolved_ip TEXT,
                    error_message TEXT
                );
            """)
            
            # Indexes for efficient filtering and sorting
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_url ON monitoring_history(url);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_checked_at ON monitoring_history(checked_at DESC);
            """)

            # Table for storing user-monitored URLs watchlist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monitored_urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    label TEXT,
                    created_at TEXT NOT NULL
                );
            """)
            conn.commit()

    def record_check(
        self,
        url: str,
        status: str,
        status_code: Optional[int],
        response_time_ms: Optional[float],
        resolved_ip: Optional[str] = None,
        error_message: Optional[str] = None,
        checked_at: Optional[str] = None
    ) -> int:
        """Record a single monitoring check outcome into SQLite.
        
        Args:
            url: Target URL that was tested.
            status: Overall status ("UP", "DOWN", or "WARNING").
            status_code: Numeric HTTP status code (e.g. 200, 500, or None).
            response_time_ms: Measured latency in milliseconds.
            resolved_ip: Resolved IP address if available.
            error_message: Error description if check failed.
            checked_at: ISO8601 timestamp string. If None, current UTC time is used.
            
        Returns:
            The primary key integer ID of the newly inserted row.
        """
        if not checked_at:
            checked_at = datetime.now(timezone.utc).isoformat()
            
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO monitoring_history (
                    url, checked_at, status, status_code,
                    response_time_ms, resolved_ip, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                url,
                checked_at,
                status,
                status_code,
                response_time_ms,
                resolved_ip,
                error_message or ""
            ))
            conn.commit()
            return cursor.lastrowid

    def get_history(self, url: Optional[str] = None, limit: int = 200) -> pd.DataFrame:
        """Fetch monitoring check history as a pandas DataFrame.
        
        Args:
            url: Optional URL to filter by. If None, fetches history for all URLs.
            limit: Maximum number of rows to return.
            
        Returns:
            pandas DataFrame containing historical check records.
        """
        query = "SELECT id, url, checked_at, status, status_code, response_time_ms, resolved_ip, error_message FROM monitoring_history"
        params: List[Any] = []
        
        if url:
            query += " WHERE url = ?"
            params.append(url)
            
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
            
        if not df.empty and "checked_at" in df.columns:
            df["checked_at"] = pd.to_datetime(df["checked_at"])
            
        return df

    def get_metrics(self, url: Optional[str] = None) -> Dict[str, Any]:
        """Compute summary availability and latency metrics.
        
        Args:
            url: Optional URL to filter by.
            
        Returns:
            Dictionary containing total checks, uptime percentage, and latency stats.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            where_clause = " WHERE url = ?" if url else ""
            params = [url] if url else []
            
            # Aggregate counts and latency
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_checks,
                    SUM(CASE WHEN status = 'UP' THEN 1 ELSE 0 END) as successful_checks,
                    SUM(CASE WHEN status != 'UP' THEN 1 ELSE 0 END) as failed_checks,
                    AVG(response_time_ms) as avg_latency,
                    MIN(response_time_ms) as min_latency,
                    MAX(response_time_ms) as max_latency
                FROM monitoring_history
                {where_clause}
            """, params)
            
            row = cursor.fetchone()
            total = row["total_checks"] or 0
            successful = row["successful_checks"] or 0
            failed = row["failed_checks"] or 0
            avg_lat = round(row["avg_latency"], 2) if row["avg_latency"] is not None else None
            min_lat = round(row["min_latency"], 2) if row["min_latency"] is not None else None
            max_lat = round(row["max_latency"], 2) if row["max_latency"] is not None else None
            
            uptime_pct = round((successful / total * 100), 2) if total > 0 else 0.0

            # HTTP Status distribution
            cursor.execute(f"""
                SELECT status_code, COUNT(*) as count
                FROM monitoring_history
                {where_clause}
                GROUP BY status_code
                ORDER BY count DESC
            """, params)
            
            status_dist = {}
            for item in cursor.fetchall():
                code = item["status_code"]
                label = str(code) if code is not None else "Error (No Code)"
                status_dist[label] = item["count"]

            return {
                "total_checks": total,
                "successful_checks": successful,
                "failed_checks": failed,
                "uptime_percentage": uptime_pct,
                "avg_response_time_ms": avg_lat,
                "min_response_time_ms": min_lat,
                "max_response_time_ms": max_lat,
                "status_distribution": status_dist
            }

    def get_recent_failures(self, url: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve recent failed monitoring checks.
        
        Args:
            url: Optional URL to filter by.
            limit: Maximum count of recent failure records to return.
            
        Returns:
            List of dictionaries representing failure events.
        """
        where_clause = "WHERE status != 'UP'"
        params: List[Any] = []
        if url:
            where_clause += " AND url = ?"
            params.append(url)
            
        params.append(limit)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT id, url, checked_at, status, status_code, response_time_ms, resolved_ip, error_message
                FROM monitoring_history
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
            """, params)
            
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def add_monitored_url(self, url: str, label: Optional[str] = None) -> bool:
        """Add a URL to the watchlist of monitored endpoints.
        
        Args:
            url: Target URL to monitor.
            label: Friendly descriptive label (e.g. 'Production Website').
            
        Returns:
            True if inserted, False if URL already exists.
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO monitored_urls (url, label, created_at)
                    VALUES (?, ?, ?)
                """, (url, label or "", now))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def remove_monitored_url(self, url: str) -> bool:
        """Remove a URL from the monitored targets watchlist.
        
        Args:
            url: Target URL to remove.
            
        Returns:
            True if row was deleted, False otherwise.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM monitored_urls WHERE url = ?", (url,))
            conn.commit()
            return cursor.rowcount > 0

    def get_monitored_urls(self) -> List[Dict[str, Any]]:
        """Fetch all monitored targets in the watchlist.
        
        Returns:
            List of dictionaries with id, url, label, and created_at.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, url, label, created_at FROM monitored_urls ORDER BY id ASC")
            return [dict(r) for r in cursor.fetchall()]

    def clear_history(self, url: Optional[str] = None) -> int:
        """Clear historical check records.
        
        Args:
            url: Optional URL to filter deletion. If None, clears all history.
            
        Returns:
            Number of rows deleted.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if url:
                cursor.execute("DELETE FROM monitoring_history WHERE url = ?", (url,))
            else:
                cursor.execute("DELETE FROM monitoring_history")
            conn.commit()
            return cursor.rowcount
