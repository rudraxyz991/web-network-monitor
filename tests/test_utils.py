"""Unit tests for URL validation and utility helpers."""

import unittest
from src.utils import normalize_url, validate_url, extract_host_and_port, categorize_status_code


class TestUtils(unittest.TestCase):
    """Test cases for utility and validation functions."""

    def test_normalize_url(self):
        """Verify URL normalization prepends https:// when missing."""
        self.assertEqual(normalize_url("example.com"), "https://example.com")
        self.assertEqual(normalize_url("http://example.com"), "http://example.com")
        self.assertEqual(normalize_url("https://api.test.org/v1"), "https://api.test.org/v1")
        self.assertEqual(normalize_url(""), "")

    def test_validate_url_valid(self):
        """Verify that standard valid URLs pass validation."""
        valid_urls = [
            "https://example.com",
            "http://example.com",
            "https://sub.domain.co.uk/path?query=1",
            "example.com",
            "https://example.com:8443/status"
        ]
        for url in valid_urls:
            is_valid, msg = validate_url(url)
            self.assertTrue(is_valid, f"Expected '{url}' to be valid, but got: {msg}")
            self.assertEqual(msg, "")

    def test_validate_url_invalid(self):
        """Verify that malformed or unsupported URLs fail validation."""
        invalid_cases = [
            ("", "empty"),
            ("   ", "empty"),
            ("ftp://ftp.example.com", "Unsupported protocol"),
            ("https://", "valid domain"),
            ("http://example.com:99999", "range")
        ]
        for url, reason in invalid_cases:
            is_valid, msg = validate_url(url)
            self.assertFalse(is_valid, f"Expected '{url}' to fail validation.")
            self.assertTrue(len(msg) > 0)

    def test_extract_host_and_port(self):
        """Verify hostname and port extraction for default and explicit ports."""
        host, port = extract_host_and_port("https://example.com")
        self.assertEqual(host, "example.com")
        self.assertEqual(port, 443)

        host, port = extract_host_and_port("http://myhost.org")
        self.assertEqual(host, "myhost.org")
        self.assertEqual(port, 80)

        host, port = extract_host_and_port("http://api.service.com:8080/test")
        self.assertEqual(host, "api.service.com")
        self.assertEqual(port, 8080)

    def test_categorize_status_code(self):
        """Verify status code classification and health indicators."""
        ok_info = categorize_status_code(200)
        self.assertTrue(ok_info["is_healthy"])
        self.assertEqual(ok_info["category"], "2xx Success")

        redirect_info = categorize_status_code(301)
        self.assertTrue(redirect_info["is_healthy"])
        self.assertEqual(redirect_info["category"], "3xx Redirection")

        client_err = categorize_status_code(404)
        self.assertFalse(client_err["is_healthy"])
        self.assertEqual(client_err["category"], "4xx Client Error")

        server_err = categorize_status_code(503)
        self.assertFalse(server_err["is_healthy"])
        self.assertEqual(server_err["category"], "5xx Server Error")

        none_err = categorize_status_code(None)
        self.assertFalse(none_err["is_healthy"])
        self.assertEqual(none_err["category"], "Unknown")


if __name__ == "__main__":
    unittest.main()
