"""Utility functions for URL validation, parsing, and formatting."""

import re
from urllib.parse import urlparse
from typing import Dict, Optional, Tuple


def normalize_url(url_string: str) -> str:
    """Normalize a user-provided URL by adding https:// if scheme is missing.
    
    Args:
        url_string: Raw URL string entered by the user.
        
    Returns:
        Cleaned, normalized URL string.
    """
    if not url_string:
        return ""
    
    cleaned = url_string.strip()
    # Only add https:// if no protocol scheme separator (://) is present
    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"
    
    return cleaned


def validate_url(url_string: str) -> Tuple[bool, str]:
    """Validate whether the given string is a valid HTTP or HTTPS URL.
    
    Args:
        url_string: URL string to validate.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    if not url_string or not url_string.strip():
        return False, "URL cannot be empty."

    candidate = normalize_url(url_string)
    
    try:
        parsed = urlparse(candidate)
    except Exception as exc:
        return False, f"Malformed URL: {exc}"
    
    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported protocol '{parsed.scheme}'. Only http and https are supported."
    
    if not parsed.hostname:
        return False, "URL must include a valid domain name or IP address."
    
    hostname = parsed.hostname.strip()
    if len(hostname) > 253:
        return False, "Hostname exceeds maximum allowed length of 253 characters."
    
    # Check port if provided
    try:
        if parsed.port is not None:
            if not (1 <= parsed.port <= 65535):
                return False, f"Port {parsed.port} is outside valid range (1-65535)."
    except ValueError as exc:
        return False, f"Invalid port in URL: {exc}"
            
    # Basic check for valid hostname characters or IPv4/IPv6
    host_pattern = re.compile(
        r"^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])"
        r"(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9]))*$"
    )
    if not host_pattern.match(hostname):
        return False, f"Invalid hostname format: '{hostname}'."
        
    return True, ""


def extract_host_and_port(url_string: str) -> Tuple[str, int]:
    """Extract hostname and default or explicit port from a URL.
    
    Args:
        url_string: Target URL.
        
    Returns:
        Tuple of (hostname, port).
    """
    normalized = normalize_url(url_string)
    parsed = urlparse(normalized)
    
    hostname = parsed.hostname or ""
    
    if parsed.port:
        port = parsed.port
    elif parsed.scheme == "https":
        port = 443
    else:
        port = 80
        
    return hostname, port


def categorize_status_code(status_code: Optional[int]) -> Dict[str, str]:
    """Categorize HTTP status code and provide clear descriptive classification.
    
    Args:
        status_code: Numeric HTTP status code (e.g. 200, 404).
        
    Returns:
        Dictionary with classification category, label, and health status.
    """
    if status_code is None:
        return {
            "category": "Unknown",
            "label": "No Response / Network Error",
            "is_healthy": False,
            "badge_color": "gray"
        }
        
    if 200 <= status_code < 300:
        return {
            "category": "2xx Success",
            "label": "Success: The server accepted and fulfilled the request.",
            "is_healthy": True,
            "badge_color": "green"
        }
    elif 300 <= status_code < 400:
        return {
            "category": "3xx Redirection",
            "label": "Redirection: The requested resource resides under a different URI.",
            "is_healthy": True,
            "badge_color": "blue"
        }
    elif 400 <= status_code < 500:
        return {
            "category": "4xx Client Error",
            "label": "Client Error: The request contains bad syntax or resource not found.",
            "is_healthy": False,
            "badge_color": "orange"
        }
    elif 500 <= status_code < 600:
        return {
            "category": "5xx Server Error",
            "label": "Server Error: The server failed to fulfill an apparently valid request.",
            "is_healthy": False,
            "badge_color": "red"
        }
    else:
        return {
            "category": f"{status_code} Non-standard",
            "label": f"Non-standard HTTP status code {status_code}.",
            "is_healthy": False,
            "badge_color": "purple"
        }
