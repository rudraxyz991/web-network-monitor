"""Network diagnostic utilities including DNS, TCP port, and SSL/TLS checks."""

import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


def resolve_dns(hostname: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Perform DNS resolution for a given hostname.
    
    DNS (Domain Name System) translates human-readable domain names
    into IP addresses used for network routing and communication.
    
    Args:
        hostname: Domain name to resolve (e.g. 'example.com').
        timeout: Socket operation timeout in seconds.
        
    Returns:
        Dictionary containing DNS resolution status, IP addresses, and timing.
    """
    start_time = time.perf_counter()
    ip_addresses: List[str] = []
    
    # Store original default timeout to restore later
    original_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
        for item in addr_info:
            ip = item[4][0]
            if ip not in ip_addresses:
                ip_addresses.append(ip)
                
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        
        if ip_addresses:
            return {
                "hostname": hostname,
                "is_resolved": True,
                "ip_addresses": ip_addresses,
                "primary_ip": ip_addresses[0],
                "resolution_time_ms": elapsed_ms,
                "error_message": ""
            }
        else:
            return {
                "hostname": hostname,
                "is_resolved": False,
                "ip_addresses": [],
                "primary_ip": None,
                "resolution_time_ms": elapsed_ms,
                "error_message": "DNS returned no records for this host."
            }
    except socket.gaierror as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "hostname": hostname,
            "is_resolved": False,
            "ip_addresses": [],
            "primary_ip": None,
            "resolution_time_ms": elapsed_ms,
            "error_message": f"DNS resolution failed: {exc.strerror or str(exc)}"
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "hostname": hostname,
            "is_resolved": False,
            "ip_addresses": [],
            "primary_ip": None,
            "resolution_time_ms": elapsed_ms,
            "error_message": f"DNS resolution error: {str(exc)}"
        }
    finally:
        socket.setdefaulttimeout(original_timeout)


def check_tcp_port(host: str, port: int, timeout: float = 3.0) -> Dict[str, Any]:
    """Test TCP 3-way handshake reachability for a specific port.
    
    A failed TCP connection to a particular port indicates that the
    specific port is closed or blocked, but does not necessarily mean
    the server itself is offline.
    
    Args:
        host: Hostname or IP address.
        port: TCP port number (1 to 65535).
        timeout: Connection timeout in seconds.
        
    Returns:
        Dictionary with reachability status, response time, and details.
    """
    service_names = {
        80: "HTTP (Web)",
        443: "HTTPS (Secure Web)",
        22: "SSH (Secure Shell)",
        21: "FTP (File Transfer)",
        25: "SMTP (Mail)",
        53: "DNS",
        3306: "MySQL Database",
        5432: "PostgreSQL Database",
        8080: "HTTP-Alt / Web Proxy",
        8443: "HTTPS-Alt",
        8501: "Streamlit Default Port"
    }
    
    start_time = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "port": port,
                "service": service_names.get(port, f"Port {port}"),
                "is_reachable": True,
                "response_time_ms": elapsed_ms,
                "status_label": "Reachable",
                "error_message": ""
            }
    except socket.timeout:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "port": port,
            "service": service_names.get(port, f"Port {port}"),
            "is_reachable": False,
            "response_time_ms": elapsed_ms,
            "status_label": "Not Reachable",
            "error_message": f"Connection timed out after {timeout} seconds."
        }
    except ConnectionRefusedError:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "port": port,
            "service": service_names.get(port, f"Port {port}"),
            "is_reachable": False,
            "response_time_ms": elapsed_ms,
            "status_label": "Not Reachable",
            "error_message": "Connection refused by target host."
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "port": port,
            "service": service_names.get(port, f"Port {port}"),
            "is_reachable": False,
            "response_time_ms": elapsed_ms,
            "status_label": "Not Reachable",
            "error_message": f"TCP check error: {str(exc)}"
        }


def check_standard_ports(host: str, custom_ports: Optional[List[int]] = None, timeout: float = 2.5) -> List[Dict[str, Any]]:
    """Check standard web ports (80, 443) and any optional user-specified ports.
    
    Args:
        host: Hostname or IP address.
        custom_ports: Optional list of additional ports to check.
        timeout: Socket timeout per port.
        
    Returns:
        List of TCP check result dictionaries.
    """
    ports_to_check = [80, 443]
    if custom_ports:
        for p in custom_ports:
            if isinstance(p, int) and 1 <= p <= 65535 and p not in ports_to_check:
                ports_to_check.append(p)
                
    results = []
    for port in ports_to_check:
        results.append(check_tcp_port(host, port, timeout=timeout))
    return results


def check_ssl_tls(hostname: str, port: int = 443, timeout: float = 3.5) -> Dict[str, Any]:
    """Inspect SSL/TLS handshake and extract basic certificate metadata.
    
    This diagnostic checks TLS connectivity and certificate validity dates.
    It does not perform comprehensive vulnerability or compliance scanning.
    
    Args:
        hostname: Target domain name.
        port: TLS port (default 443).
        timeout: Handshake timeout in seconds.
        
    Returns:
        Dictionary containing TLS handshake status and certificate details.
    """
    context = ssl.create_default_context()
    start_time = time.perf_counter()
    
    try:
        with socket.create_connection((hostname, port), timeout=timeout) as raw_sock:
            with context.wrap_socket(raw_sock, server_hostname=hostname) as tls_sock:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                tls_version = tls_sock.version()
                cipher_info = tls_sock.cipher()
                cert = tls_sock.getpeercert()
                
                # Parse expiration and common name
                valid_to_str = cert.get("notAfter", "")
                days_remaining = None
                is_expired = False
                
                if valid_to_str:
                    try:
                        # Format example: 'May 15 12:00:00 2027 GMT'
                        expire_date = datetime.strptime(valid_to_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                        now_utc = datetime.now(timezone.utc)
                        delta = expire_date - now_utc
                        days_remaining = delta.days
                        if days_remaining < 0:
                            is_expired = True
                    except Exception:
                        days_remaining = None

                # Extract subject and issuer
                subject_parts = {}
                for rdn in cert.get("subject", ()):
                    for key, val in rdn:
                        subject_parts[key] = val
                        
                issuer_parts = {}
                for rdn in cert.get("issuer", ()):
                    for key, val in rdn:
                        issuer_parts[key] = val
                        
                common_name = subject_parts.get("commonName", hostname)
                issuer_name = issuer_parts.get("organizationName") or issuer_parts.get("commonName", "Unknown Issuer")

                return {
                    "is_tls_available": True,
                    "handshake_time_ms": elapsed_ms,
                    "tls_version": tls_version or "Unknown",
                    "cipher_name": cipher_info[0] if cipher_info else "Unknown",
                    "common_name": common_name,
                    "issuer": issuer_name,
                    "valid_until": valid_to_str,
                    "days_remaining": days_remaining,
                    "is_expired": is_expired,
                    "status_label": "Certificate Valid" if not is_expired else "Certificate Expired",
                    "error_message": ""
                }
    except ssl.SSLCertVerificationError as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "is_tls_available": False,
            "handshake_time_ms": elapsed_ms,
            "tls_version": None,
            "cipher_name": None,
            "common_name": None,
            "issuer": None,
            "valid_until": None,
            "days_remaining": None,
            "is_expired": True,
            "status_label": "TLS Verification Failed",
            "error_message": f"Certificate verification failed: {exc.verify_message}"
        }
    except ssl.SSLError as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "is_tls_available": False,
            "handshake_time_ms": elapsed_ms,
            "tls_version": None,
            "cipher_name": None,
            "common_name": None,
            "issuer": None,
            "valid_until": None,
            "days_remaining": None,
            "is_expired": False,
            "status_label": "TLS Handshake Error",
            "error_message": f"SSL error: {str(exc)}"
        }
    except (socket.timeout, TimeoutError):
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "is_tls_available": False,
            "handshake_time_ms": elapsed_ms,
            "tls_version": None,
            "cipher_name": None,
            "common_name": None,
            "issuer": None,
            "valid_until": None,
            "days_remaining": None,
            "is_expired": False,
            "status_label": "Timeout",
            "error_message": f"TLS handshake timed out after {timeout} seconds."
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "is_tls_available": False,
            "handshake_time_ms": elapsed_ms,
            "tls_version": None,
            "cipher_name": None,
            "common_name": None,
            "issuer": None,
            "valid_until": None,
            "days_remaining": None,
            "is_expired": False,
            "status_label": "Connection Error",
            "error_message": f"Could not establish TLS connection: {str(exc)}"
        }
