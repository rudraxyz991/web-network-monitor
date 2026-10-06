"""Unit tests for WebMonitor HTTP and health checking engine."""

import unittest
from unittest.mock import patch, MagicMock
import requests

from src.monitor import WebMonitor


class TestWebMonitor(unittest.TestCase):
    """Test suite for WebMonitor class using isolated mocks."""

    def setUp(self):
        """Initialize monitor instance before each test."""
        self.monitor = WebMonitor(timeout=3.0)

    def test_check_url_invalid(self):
        """Verify invalid URL is rejected gracefully without crashing."""
        result = self.monitor.check_url("ftp://invalid-url-protocol")
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["status"], "DOWN")
        self.assertIn("Unsupported protocol", result["error_message"])

    @patch("src.monitor.check_ssl_tls")
    @patch("src.monitor.check_standard_ports")
    @patch("src.monitor.resolve_dns")
    @patch("requests.get")
    def test_check_url_success_200(self, mock_requests_get, mock_dns, mock_ports, mock_ssl):
        """Verify successful HTTP 200 response results in UP status."""
        mock_dns.return_value = {
            "hostname": "example.com",
            "is_resolved": True,
            "ip_addresses": ["93.184.215.14"],
            "primary_ip": "93.184.215.14",
            "resolution_time_ms": 15.0,
            "error_message": ""
        }
        mock_ports.return_value = [
            {"port": 80, "is_reachable": True, "status_label": "Reachable"},
            {"port": 443, "is_reachable": True, "status_label": "Reachable"}
        ]
        mock_ssl.return_value = {
            "is_tls_available": True,
            "tls_version": "TLSv1.3",
            "is_expired": False,
            "status_label": "Certificate Valid"
        }
        
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com"
        mock_resp.history = []
        mock_resp.headers = {"Content-Type": "text/html; charset=UTF-8", "Server": "ECS"}
        mock_requests_get.return_value = mock_resp

        result = self.monitor.check_url("https://example.com")
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["status"], "UP")
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["resolved_ip"], "93.184.215.14")
        self.assertTrue(result["http"]["success"])
        self.assertEqual(result["http"]["headers"]["Server"], "ECS")

    @patch("src.monitor.check_ssl_tls")
    @patch("src.monitor.check_standard_ports")
    @patch("src.monitor.resolve_dns")
    @patch("requests.get")
    def test_check_url_client_error_404(self, mock_requests_get, mock_dns, mock_ports, mock_ssl):
        """Verify 404 client error results in WARNING status."""
        mock_dns.return_value = {"primary_ip": "93.184.215.14", "is_resolved": True}
        mock_ports.return_value = []
        mock_ssl.return_value = None

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 404
        mock_resp.url = "https://example.com/notfound"
        mock_resp.history = []
        mock_resp.headers = {}
        mock_requests_get.return_value = mock_resp

        result = self.monitor.check_url("https://example.com/notfound")
        self.assertEqual(result["status"], "WARNING")
        self.assertEqual(result["status_code"], 404)
        self.assertIn("404", result["error_message"])

    @patch("src.monitor.check_ssl_tls")
    @patch("src.monitor.check_standard_ports")
    @patch("src.monitor.resolve_dns")
    @patch("requests.get")
    def test_check_url_server_error_500(self, mock_requests_get, mock_dns, mock_ports, mock_ssl):
        """Verify 500 server error results in DOWN status."""
        mock_dns.return_value = {"primary_ip": "93.184.215.14", "is_resolved": True}
        mock_ports.return_value = []
        mock_ssl.return_value = None

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.url = "https://example.com/api"
        mock_resp.history = []
        mock_resp.headers = {}
        mock_requests_get.return_value = mock_resp

        result = self.monitor.check_url("https://example.com/api")
        self.assertEqual(result["status"], "DOWN")
        self.assertEqual(result["status_code"], 500)
        self.assertIn("500", result["error_message"])

    @patch("src.monitor.check_ssl_tls")
    @patch("src.monitor.check_standard_ports")
    @patch("src.monitor.resolve_dns")
    @patch("requests.get")
    def test_check_url_timeout(self, mock_requests_get, mock_dns, mock_ports, mock_ssl):
        """Verify request timeout is caught and handled."""
        mock_dns.return_value = {"primary_ip": "1.1.1.1", "is_resolved": True}
        mock_ports.return_value = []
        mock_ssl.return_value = None
        mock_requests_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        result = self.monitor.check_url("https://example.com/slow")
        self.assertEqual(result["status"], "DOWN")
        self.assertIsNone(result["status_code"])
        self.assertIn("timed out", result["error_message"].lower())

    @patch("src.monitor.check_ssl_tls")
    @patch("src.monitor.check_standard_ports")
    @patch("src.monitor.resolve_dns")
    @patch("requests.get")
    def test_check_url_connection_error(self, mock_requests_get, mock_dns, mock_ports, mock_ssl):
        """Verify connection error is caught gracefully."""
        mock_dns.return_value = {"primary_ip": None, "is_resolved": False}
        mock_ports.return_value = []
        mock_ssl.return_value = None
        mock_requests_get.side_effect = requests.exceptions.ConnectionError("Failed to establish a new connection")

        result = self.monitor.check_url("https://unreachable-domain-xyz.com")
        self.assertEqual(result["status"], "DOWN")
        self.assertIsNone(result["status_code"])
        self.assertIn("failed", result["error_message"].lower())

    @patch("src.monitor.check_ssl_tls")
    @patch("src.monitor.check_standard_ports")
    @patch("src.monitor.resolve_dns")
    @patch("requests.get")
    def test_check_url_redirect_chain(self, mock_requests_get, mock_dns, mock_ports, mock_ssl):
        """Verify redirect history is captured."""
        mock_dns.return_value = {"primary_ip": "93.184.215.14", "is_resolved": True}
        mock_ports.return_value = []
        mock_ssl.return_value = None

        hop = MagicMock()
        hop.url = "http://example.com"
        hop.status_code = 301

        final_resp = MagicMock()
        final_resp.ok = True
        final_resp.status_code = 200
        final_resp.url = "https://example.com/"
        final_resp.history = [hop]
        final_resp.headers = {}
        mock_requests_get.return_value = final_resp

        result = self.monitor.check_url("http://example.com")
        self.assertEqual(result["status"], "UP")
        self.assertEqual(result["http"]["redirect_count"], 1)
        self.assertEqual(result["http"]["final_url"], "https://example.com/")


if __name__ == "__main__":
    unittest.main()
