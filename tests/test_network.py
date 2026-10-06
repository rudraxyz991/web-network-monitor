"""Unit tests for DNS, TCP port, and SSL/TLS network diagnostics."""

import unittest
from unittest.mock import patch, MagicMock
import socket
import ssl

from src.network import resolve_dns, check_tcp_port, check_standard_ports, check_ssl_tls


class TestNetworkDiagnostics(unittest.TestCase):
    """Test suite for network diagnostic functions with isolated mocks."""

    @patch("socket.getaddrinfo")
    def test_resolve_dns_success(self, mock_getaddrinfo):
        """Verify successful DNS resolution extracts IP addresses."""
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.15", 0))
        ]
        
        result = resolve_dns("example.com")
        self.assertTrue(result["is_resolved"])
        self.assertEqual(result["primary_ip"], "93.184.215.14")
        self.assertEqual(len(result["ip_addresses"]), 2)
        self.assertEqual(result["error_message"], "")

    @patch("socket.getaddrinfo")
    def test_resolve_dns_failure(self, mock_getaddrinfo):
        """Verify handling of DNS lookup failure (gaierror)."""
        mock_getaddrinfo.side_effect = socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        
        result = resolve_dns("nonexistent-domain-xyz123.com")
        self.assertFalse(result["is_resolved"])
        self.assertIsNone(result["primary_ip"])
        self.assertIn("failed", result["error_message"].lower())

    @patch("socket.create_connection")
    def test_check_tcp_port_reachable(self, mock_create_conn):
        """Verify reachable port returns success status."""
        mock_sock = MagicMock()
        mock_create_conn.return_value = mock_sock
        
        result = check_tcp_port("example.com", 80)
        self.assertTrue(result["is_reachable"])
        self.assertEqual(result["status_label"], "Reachable")
        self.assertEqual(result["error_message"], "")

    @patch("socket.create_connection")
    def test_check_tcp_port_timeout(self, mock_create_conn):
        """Verify timeout handling for closed/filtered port."""
        mock_create_conn.side_effect = socket.timeout()
        
        result = check_tcp_port("example.com", 8080, timeout=1.0)
        self.assertFalse(result["is_reachable"])
        self.assertEqual(result["status_label"], "Not Reachable")
        self.assertIn("timed out", result["error_message"])

    @patch("socket.create_connection")
    def test_check_tcp_port_refused(self, mock_create_conn):
        """Verify connection refused handling."""
        mock_create_conn.side_effect = ConnectionRefusedError()
        
        result = check_tcp_port("example.com", 22)
        self.assertFalse(result["is_reachable"])
        self.assertIn("refused", result["error_message"])

    @patch("src.network.check_tcp_port")
    def test_check_standard_ports(self, mock_check_port):
        """Verify check_standard_ports tests 80, 443, and custom ports."""
        mock_check_port.return_value = {
            "port": 80,
            "is_reachable": True,
            "status_label": "Reachable"
        }
        results = check_standard_ports("example.com", custom_ports=[8080])
        self.assertEqual(len(results), 3)
        calls = [call[0][1] for call in mock_check_port.call_args_list]
        self.assertEqual(calls, [80, 443, 8080])

    @patch("ssl.create_default_context")
    @patch("socket.create_connection")
    def test_check_ssl_tls_success(self, mock_create_conn, mock_ssl_context):
        """Verify successful TLS handshake and certificate parsing."""
        mock_raw_sock = MagicMock()
        mock_create_conn.return_value.__enter__.return_value = mock_raw_sock
        
        mock_tls_sock = MagicMock()
        mock_tls_sock.version.return_value = "TLSv1.3"
        mock_tls_sock.cipher.return_value = ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)
        mock_tls_sock.getpeercert.return_value = {
            "subject": ((("commonName", "example.com"),),),
            "issuer": ((("organizationName", "DigiCert Inc"),),),
            "notAfter": "May 15 12:00:00 2030 GMT"
        }
        
        mock_context_instance = MagicMock()
        mock_context_instance.wrap_socket.return_value.__enter__.return_value = mock_tls_sock
        mock_ssl_context.return_value = mock_context_instance
        
        result = check_ssl_tls("example.com")
        self.assertTrue(result["is_tls_available"])
        self.assertEqual(result["tls_version"], "TLSv1.3")
        self.assertEqual(result["common_name"], "example.com")
        self.assertEqual(result["issuer"], "DigiCert Inc")
        self.assertFalse(result["is_expired"])
        self.assertEqual(result["status_label"], "Certificate Valid")


if __name__ == "__main__":
    unittest.main()
