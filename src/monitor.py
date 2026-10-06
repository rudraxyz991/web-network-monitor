"""HTTP and Web Service monitoring engine."""

import time
from typing import Dict, List, Optional, Any
import requests

from src.utils import normalize_url, validate_url, extract_host_and_port, categorize_status_code
from src.network import resolve_dns, check_standard_ports, check_ssl_tls


class WebMonitor:
    """Orchestrates comprehensive website and network health checks."""
    
    DEFAULT_USER_AGENT = "WebNetworkMonitor/1.0 (+https://github.com/rudraxyz991/web-network-monitor)"
    
    def __init__(self, timeout: float = 5.0, user_agent: Optional[str] = None):
        """Initialize the monitor with customizable timeout and user-agent.
        
        Args:
            timeout: HTTP request timeout in seconds.
            user_agent: Custom User-Agent header string.
        """
        self.timeout = timeout
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT

    def check_url(
        self,
        url_input: str,
        custom_ports: Optional[List[int]] = None,
        follow_redirects: bool = True
    ) -> Dict[str, Any]:
        """Perform a full diagnostic check on a URL.
        
        Runs URL validation, DNS resolution, HTTP request, TCP port connectivity,
        and SSL/TLS certificate inspection.
        
        Args:
            url_input: Raw URL entered by user.
            custom_ports: Optional list of additional TCP ports to check.
            follow_redirects: Whether HTTP client should follow 3xx redirects.
            
        Returns:
            Dictionary containing complete diagnostics and health status.
        """
        # Step 1: Validate URL syntax
        is_valid, validation_err = validate_url(url_input)
        if not is_valid:
            return {
                "url": url_input,
                "is_valid": False,
                "status": "DOWN",
                "status_code": None,
                "response_time_ms": None,
                "resolved_ip": None,
                "error_message": validation_err,
                "dns": None,
                "http": None,
                "ports": [],
                "ssl": None
            }
            
        target_url = normalize_url(url_input)
        hostname, default_port = extract_host_and_port(target_url)
        is_https = target_url.startswith("https://")

        # Step 2: DNS Diagnostics
        dns_result = resolve_dns(hostname)
        primary_ip = dns_result.get("primary_ip")

        # Step 3: TCP Port Diagnostics
        port_results = check_standard_ports(hostname, custom_ports=custom_ports)

        # Step 4: SSL/TLS Diagnostics (if HTTPS)
        ssl_result = None
        if is_https:
            ssl_result = check_ssl_tls(hostname, port=default_port)

        # Step 5: HTTP/HTTPS Request Execution
        http_result = self._execute_http_request(
            target_url,
            follow_redirects=follow_redirects
        )

        # Determine overall site status
        # UP: 2xx or 3xx HTTP response
        # WARNING: 4xx HTTP response (server reachable, but request or resource error)
        # DOWN: 5xx HTTP response, connection error, DNS failure, or timeout
        overall_status = "DOWN"
        status_code = http_result.get("status_code")
        error_message = http_result.get("error_message", "")
        response_time_ms = http_result.get("response_time_ms")

        if status_code is not None:
            if 200 <= status_code < 400:
                overall_status = "UP"
            elif 400 <= status_code < 500:
                overall_status = "WARNING"
                if not error_message:
                    error_message = f"Client error response HTTP {status_code}"
            else:
                overall_status = "DOWN"
                if not error_message:
                    error_message = f"Server error response HTTP {status_code}"
        else:
            overall_status = "DOWN"

        return {
            "url": target_url,
            "is_valid": True,
            "status": overall_status,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "resolved_ip": primary_ip,
            "error_message": error_message,
            "is_https": is_https,
            "hostname": hostname,
            "dns": dns_result,
            "http": http_result,
            "ports": port_results,
            "ssl": ssl_result
        }

    def _execute_http_request(
        self,
        target_url: str,
        follow_redirects: bool = True
    ) -> Dict[str, Any]:
        """Execute HTTP GET request and collect response telemetry.
        
        Args:
            target_url: Normalized target URL.
            follow_redirects: Whether to follow HTTP redirect responses.
            
        Returns:
            Dictionary containing HTTP telemetry and headers.
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*"
        }
        
        start_time = time.perf_counter()
        
        try:
            response = requests.get(
                target_url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=follow_redirects
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            
            # Extract key useful headers (avoid dumping irrelevant ones)
            key_headers = {}
            for header_name in ["Content-Type", "Server", "Date", "Content-Length", "Cache-Control"]:
                if header_name in response.headers:
                    key_headers[header_name] = response.headers[header_name]

            # Redirect chain capture
            redirect_chain = []
            for hop in response.history:
                redirect_chain.append({
                    "url": hop.url,
                    "status_code": hop.status_code
                })

            status_meta = categorize_status_code(response.status_code)

            return {
                "success": response.ok,
                "status_code": response.status_code,
                "status_category": status_meta["category"],
                "status_description": status_meta["label"],
                "response_time_ms": elapsed_ms,
                "final_url": response.url,
                "redirect_count": len(response.history),
                "redirect_chain": redirect_chain,
                "headers": key_headers,
                "error_message": ""
            }
            
        except requests.exceptions.SSLError as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "status_code": None,
                "status_category": "SSL/TLS Error",
                "status_description": "Failed to verify SSL certificate.",
                "response_time_ms": elapsed_ms,
                "final_url": target_url,
                "redirect_count": 0,
                "redirect_chain": [],
                "headers": {},
                "error_message": f"SSL/TLS Certificate verification failed: {str(exc)}"
            }
            
        except requests.exceptions.Timeout:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "status_code": None,
                "status_category": "Timeout",
                "status_description": f"Request exceeded timeout limit of {self.timeout}s.",
                "response_time_ms": elapsed_ms,
                "final_url": target_url,
                "redirect_count": 0,
                "redirect_chain": [],
                "headers": {},
                "error_message": f"Connection timed out after {self.timeout} seconds."
            }
            
        except requests.exceptions.ConnectionError as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "status_code": None,
                "status_category": "Connection Failure",
                "status_description": "Could not connect to host. Server may be down or hostname invalid.",
                "response_time_ms": elapsed_ms,
                "final_url": target_url,
                "redirect_count": 0,
                "redirect_chain": [],
                "headers": {},
                "error_message": f"Connection failed: {str(exc)}"
            }
            
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "success": False,
                "status_code": None,
                "status_category": "General Error",
                "status_description": "Unexpected error during HTTP request.",
                "response_time_ms": elapsed_ms,
                "final_url": target_url,
                "redirect_count": 0,
                "redirect_chain": [],
                "headers": {},
                "error_message": f"Request failed: {str(exc)}"
            }
