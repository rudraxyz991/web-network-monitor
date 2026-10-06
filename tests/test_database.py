"""Unit tests for SQLite database operations and metrics calculations."""

import os
import tempfile
import unittest

from src.database import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    """Test suite for DatabaseManager using an isolated temporary SQLite database."""

    def setUp(self):
        """Create a temporary SQLite database file for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_monitoring.db")
        self.db = DatabaseManager(db_path=self.db_path)

    def tearDown(self):
        """Clean up temporary files."""
        self.temp_dir.cleanup()

    def test_init_db_creates_tables(self):
        """Verify that required tables are created on initialization."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row["name"] for row in cursor.fetchall()]
            self.assertIn("monitoring_history", tables)
            self.assertIn("monitored_urls", tables)

    def test_record_check_and_get_history(self):
        """Verify recording checks and querying history as DataFrame."""
        row_id = self.db.record_check(
            url="https://example.com",
            status="UP",
            status_code=200,
            response_time_ms=120.5,
            resolved_ip="93.184.215.14",
            error_message=""
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)

        df = self.db.get_history(url="https://example.com")
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["status"], "UP")
        self.assertEqual(df.iloc[0]["status_code"], 200)
        self.assertAlmostEqual(df.iloc[0]["response_time_ms"], 120.5)

    def test_get_metrics(self):
        """Verify computation of uptime percentage and latency stats."""
        # Insert 3 successful checks and 1 failure
        self.db.record_check("https://service.org", "UP", 200, 100.0, "1.1.1.1")
        self.db.record_check("https://service.org", "UP", 200, 200.0, "1.1.1.1")
        self.db.record_check("https://service.org", "UP", 200, 300.0, "1.1.1.1")
        self.db.record_check("https://service.org", "DOWN", 500, 500.0, "1.1.1.1", error_message="Server Error")

        metrics = self.db.get_metrics("https://service.org")
        self.assertEqual(metrics["total_checks"], 4)
        self.assertEqual(metrics["successful_checks"], 3)
        self.assertEqual(metrics["failed_checks"], 1)
        self.assertEqual(metrics["uptime_percentage"], 75.0)
        self.assertAlmostEqual(metrics["avg_response_time_ms"], 275.0)
        self.assertEqual(metrics["min_response_time_ms"], 100.0)
        self.assertEqual(metrics["max_response_time_ms"], 500.0)
        self.assertEqual(metrics["status_distribution"].get("200"), 3)
        self.assertEqual(metrics["status_distribution"].get("500"), 1)

    def test_get_recent_failures(self):
        """Verify retrieval of recent failure events."""
        self.db.record_check("https://test.com", "UP", 200, 50.0)
        self.db.record_check("https://test.com", "DOWN", 503, 900.0, error_message="Service Unavailable")

        failures = self.db.get_recent_failures("https://test.com")
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["status_code"], 503)
        self.assertEqual(failures[0]["error_message"], "Service Unavailable")

    def test_watchlist_crud(self):
        """Verify adding, listing, and removing monitored URLs."""
        # Add URL
        added = self.db.add_monitored_url("https://example.com", "Example Portal")
        self.assertTrue(added)

        # Duplicate addition should return False
        duplicate = self.db.add_monitored_url("https://example.com", "Duplicate")
        self.assertFalse(duplicate)

        # List URLs
        urls = self.db.get_monitored_urls()
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0]["url"], "https://example.com")
        self.assertEqual(urls[0]["label"], "Example Portal")

        # Remove URL
        removed = self.db.remove_monitored_url("https://example.com")
        self.assertTrue(removed)

        urls_after = self.db.get_monitored_urls()
        self.assertEqual(len(urls_after), 0)

    def test_clear_history(self):
        """Verify clearing history rows."""
        self.db.record_check("https://test.com", "UP", 200, 50.0)
        self.db.record_check("https://other.com", "UP", 200, 60.0)

        # Clear specific URL
        deleted_count = self.db.clear_history("https://test.com")
        self.assertEqual(deleted_count, 1)
        self.assertEqual(len(self.db.get_history("https://test.com")), 0)
        self.assertEqual(len(self.db.get_history("https://other.com")), 1)

        # Clear all
        deleted_all = self.db.clear_history()
        self.assertEqual(deleted_all, 1)
        self.assertEqual(len(self.db.get_history()), 0)


if __name__ == "__main__":
    unittest.main()
