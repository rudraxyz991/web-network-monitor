# Web & Network Monitoring Platform

A lightweight web application built in Python and Streamlit to monitor website availability, inspect HTTP responses, perform DNS lookups, verify TCP port reachability, and track historical uptime metrics.

---

## 1. Project Title
**Web & Network Monitoring Platform**

---

## 2. Project Overview
This project is an interactive monitoring and network diagnostics tool. It allows a user to provide any web URL or API endpoint and inspect its operational status in real time. The platform gathers essential telemetry (HTTP status codes, latency, redirects, DNS records, TCP reachability, and SSL/TLS certificate validity) and stores each check in an embedded SQLite database to calculate uptime percentages and plot response time trends.

---

## 3. Problem Statement
When an online service or website encounters issues, determining whether the problem originates from DNS failure, server downtime, closed network ports, SSL certificate expiry, or HTTP application errors often requires running multiple disparate command-line tools (`ping`, `curl`, `dig`, `nc`, `openssl`). 

This project solves that friction by unifying basic HTTP checks and network-layer diagnostics into a simple, single-click web dashboard that stores historical results for quick trend analysis.

---

## 4. Why the Project Was Built
This project was designed and built to demonstrate practical software engineering, web protocols, networking fundamentals, SQL database handling, and basic cloud deployment concepts in Python.

Specifically:
- To understand how the HTTP request-response cycle operates in practice.
- To demonstrate how DNS resolution, TCP sockets, and SSL/TLS handshakes work under the hood.
- To use SQLite for persistent data logging and SQL aggregations (uptime percentage, latency averages).
- To practice cloud deployment using an AWS EC2 Ubuntu virtual machine.
- To build a defensible software project for technical interviews without unnecessary architectural complexity.

### Why Streamlit Was Selected
Streamlit was selected because it allows the application to provide an interactive web interface while keeping the main implementation in Python. This allowed the project to focus on monitoring, networking and backend functionality rather than requiring a separate frontend framework.

---

## 5. Features
- **URL Validation and Normalization**: Verifies URL format, handles missing protocols by defaulting to HTTPS, and guards against malformed input without application crashes.
- **HTTP / HTTPS Health Checks**: Measures round-trip response time in milliseconds, captures HTTP status codes, extracts key response headers (`Server`, `Content-Type`, `Date`), and tracks redirect chains.
- **Status Code Categorization**: Clearly categorizes responses into 2xx Success, 3xx Redirection, 4xx Client Error, and 5xx Server Error.
- **DNS Resolution Diagnostics**: Resolves hostnames into IPv4 addresses using Python standard library sockets and measures DNS query latency.
- **TCP Port Diagnostics**: Tests TCP 3-way handshake reachability for standard ports (80 HTTP, 443 HTTPS) and user-specified custom ports.
- **SSL / TLS Certificate Inspection**: Inspects TLS protocol versions, cipher suites, certificate issuer, common name, and validity expiration dates.
- **Target Watchlist & Bulk Checks**: Allows saving a collection of URLs to a watchlist and running diagnostic checks across all targets sequentially.
- **Historical Telemetry & Metrics**: Calculates uptime percentage, total checks, failure counts, average latency, and minimum/maximum response times.
- **Interactive Visualizations**: Renders response time trend charts and HTTP status code distribution charts using Plotly.
- **Failure Logging**: Displays a dedicated table of recent failures with detailed error messages.
- **Standalone Network Lab**: Offers quick standalone DNS resolution and port checking tools for debugging.

---

## 6. Architecture

```text
                    USER
                      |
                      v
               Streamlit UI
                      |
                      v
              Python Application
                /           \
               /             \
              v               v
       HTTP/API Checks    Network Checks
              |               |
              v               v
          Requests       DNS / Socket / SSL
               \             /
                \           /
                 v         v
                  SQLite
                     |
                     v
              Historical Data
```

The application runs as a modular single-service Python application:
1. **User Interface (`app.py`)**: Manages the Streamlit UI components, state, input fields, and Plotly charts.
2. **Monitoring Engine (`src/monitor.py`)**: Coordinates HTTP requests, integrates network checks, categorizes health, and structures results.
3. **Network Diagnostics (`src/network.py`)**: Uses Python standard library modules (`socket`, `ssl`) to execute DNS queries, TCP connections, and TLS certificate inspection.
4. **Validation Utilities (`src/utils.py`)**: Normalizes URLs, validates format, extracts hostnames, and classifies status codes.
5. **Database Manager (`src/database.py`)**: Manages SQLite tables, inserts check records, computes summary metrics via SQL queries, and handles watchlist targets.

---

## 7. Technology Stack
- **Language**: Python 3.11+
- **Web Interface**: Streamlit
- **HTTP Client**: Requests
- **Networking**: Python standard library (`socket`, `ssl`, `urllib.parse`)
- **Database**: SQLite3 (embedded relational database)
- **Data Analysis**: Pandas
- **Data Visualization**: Plotly
- **Automated Testing**: Pytest
- **Version Control**: Git and GitHub
- **Cloud Infrastructure**: AWS EC2 (Ubuntu 24.04 LTS)

Every dependency in `requirements.txt` has a direct, justified purpose. No unused frameworks or third-party wrappers were introduced.

---

## 8. How the Monitoring Process Works
When a user clicks "Run Diagnostic Check" for a target URL:
1. **Validation**: The URL string is normalized (e.g. adding `https://` if no protocol is given) and validated with `urllib.parse`.
2. **Hostname & Port Extraction**: The domain name and port (default 443 for HTTPS, 80 for HTTP) are extracted.
3. **DNS Lookup**: `socket.getaddrinfo` is invoked to resolve the domain into IPv4 addresses and measure DNS lookup latency.
4. **Port Reachability**: Non-blocking TCP socket connections are attempted on ports 80, 443, and any optional port specified by the user.
5. **SSL/TLS Handshake**: If the URL uses HTTPS, a secure TLS handshake is initiated using `ssl.create_default_context()`. Certificate metadata (`notAfter`, issuer, cipher) is extracted.
6. **HTTP Request**: An HTTP GET request is dispatched using `requests.get()` with a 5-second timeout. The elapsed time is measured with high-resolution timers (`time.perf_counter()`).
7. **Classification**: The HTTP status code is evaluated:
   - 2xx or 3xx: Marked as **UP**.
   - 4xx: Marked as **WARNING** (server responded, but client request error).
   - 5xx, timeout, or network failure: Marked as **DOWN**.
8. **Storage**: The result (timestamp, URL, status, status code, latency, resolved IP, error message) is inserted into SQLite.
9. **Dashboard Render**: The UI updates with metric cards, diagnostic tables, and updated historical charts.

---

## 9. HTTP Explanation
HTTP (Hypertext Transfer Protocol) is an application-layer request-response protocol running over TCP.
- **Client Request**: The client sends an HTTP method (such as GET or POST), headers (e.g. User-Agent, Accept), and optional body.
- **Server Response**: The server returns an HTTP status code, response headers (e.g. Content-Type, Content-Length, Server, Date), and response body.
- **Status Code Ranges**:
  - `2xx (Success)`: The request was successfully received, understood, and accepted (e.g. 200 OK).
  - `3xx (Redirection)`: Further action needs to be taken by the user agent to fulfill the request (e.g. 301 Moved Permanently, 302 Found).
  - `4xx (Client Error)`: The request contains bad syntax or cannot be fulfilled (e.g. 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found).
  - `5xx (Server Error)`: The server failed to fulfill an apparently valid request (e.g. 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout).

A 4xx response means the remote server is active and responding, but the requested page does not exist or requires authentication. In contrast, a 5xx response indicates an application crash or upstream infrastructure failure.

---

## 10. DNS Explanation
DNS (Domain Name System) translates human-readable domain names into IP addresses used for network communication.

For example, when a user enters `example.com`, the computer cannot route packets using domain strings. The operating system queries DNS resolvers to translate `example.com` into an IP address such as `93.184.215.14`.

In this application, DNS resolution is handled via Python's standard `socket.getaddrinfo()`. If DNS resolution fails, the application records a DNS lookup error, indicating that the domain does not exist or the DNS server is unreachable.

---

## 11. TCP and Port Explanation
TCP (Transmission Control Protocol) is a connection-oriented transport layer protocol that provides reliable, ordered, and error-checked delivery of packets between applications.

Before any HTTP data can be sent, a client and server establish a connection using the TCP 3-way handshake:
1. **SYN**: Client sends a synchronize packet to the server's port.
2. **SYN-ACK**: Server acknowledges and responds with a synchronize-acknowledgment packet.
3. **ACK**: Client acknowledges the response, and the connection is established.

A port is a 16-bit number (0 to 65535) that directs network traffic to a specific service running on an operating system:
- **Port 80**: Standard unencrypted HTTP web traffic.
- **Port 443**: Standard encrypted HTTPS traffic.

A failed TCP connection to a particular port does not necessarily mean that the entire website or server is down. A server may intentionally close port 80 and only listen on port 443, or a firewall may block specific ports while allowing web traffic.

---

## 12. SSL/TLS Explanation
SSL (Secure Sockets Layer) and its successor TLS (Transport Layer Security) are cryptographic protocols that provide communications security over a computer network. HTTPS is HTTP layered on top of TLS.

During a TLS handshake:
1. The client and server agree on a TLS version and cryptographic cipher suite.
2. The server presents an X.509 digital certificate to authenticate its identity.
3. The client verifies that the certificate was issued by a trusted Certificate Authority (CA) and matches the domain name.
4. Asymmetric encryption is used to securely exchange symmetric keys, which encrypt the rest of the HTTP traffic.

This application inspects the TLS connection to retrieve:
- Negotiated TLS protocol version (e.g. TLSv1.3 or TLSv1.2)
- Negotiated cipher suite
- Certificate Common Name and Issuer
- Certificate expiration date and remaining days before expiry

This feature serves as a diagnostic tool to alert users to impending certificate expirations or invalid certificates. It is not a vulnerability scanner.

---

## 13. Database Design
The platform uses SQLite, an embedded relational database engine that stores data in a local file (`data/monitoring.db`). SQLite requires zero server configuration and is created automatically on first run.

### Table: `monitoring_history`
Stores the result of every executed health check.

| Column | Data Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Unique record identifier |
| `url` | TEXT NOT NULL | Target URL that was monitored |
| `checked_at` | TEXT NOT NULL | ISO8601 UTC timestamp of check |
| `status` | TEXT NOT NULL | Status outcome: "UP", "DOWN", or "WARNING" |
| `status_code` | INTEGER | HTTP status code (e.g. 200, 404, or NULL) |
| `response_time_ms` | REAL | Total response latency in milliseconds |
| `resolved_ip` | TEXT | Primary resolved IPv4 address |
| `error_message` | TEXT | Error description if check failed |

Indexes are created on `url` and `checked_at DESC` to optimize query performance when loading historical trends.

### Table: `monitored_urls`
Stores targets saved to the watchlist.

| Column | Data Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Unique target identifier |
| `url` | TEXT UNIQUE NOT NULL | Target URL |
| `label` | TEXT | Friendly name/label |
| `created_at` | TEXT NOT NULL | Timestamp when target was added |

---

## 14. Project Structure

```text
web-network-monitor/
├── app.py                     # Main Streamlit web application
├── requirements.txt           # Python dependencies
├── README.md                  # Comprehensive project documentation
├── INTERVIEW_PREP.md          # 40+ technical interview questions and answers
├── INTERVIEW_RISKS.md         # Interview scope boundaries and risk analysis
├── .gitignore                 # Files excluded from version control
|
├── src/                       # Application source code
│   ├── __init__.py            # Package initializer
│   ├── utils.py               # URL validation, parsing, and status categorization
│   ├── network.py             # DNS lookup, TCP socket test, and TLS inspection
│   ├── monitor.py             # HTTP monitoring engine coordinating checks
│   └── database.py            # SQLite database connection and query manager
|
├── tests/                     # Automated test suite
│   ├── __init__.py            # Test package initializer
│   ├── test_utils.py          # Tests for URL parsing and helpers
│   ├── test_network.py        # Tests for DNS, TCP, and TLS diagnostics (mocked)
│   ├── test_monitor.py        # Tests for HTTP monitoring engine (mocked)
│   └── test_database.py       # Tests for SQLite database operations
|
└── data/                      # Local database directory
    └── .gitkeep               # Ensures data folder exists in Git repository
```

---


## 20. Security Considerations
- **No Hardcoded Secrets**: The codebase contains zero API keys, passwords, or cloud credentials.
- **Restricted Ports**: Inbound network access on AWS is limited to port 22 and port 8501. SSH access is restricted to the administrator's IP address.
- **Request Timeouts**: All HTTP requests and raw socket calls enforce explicit timeouts (3 to 5 seconds) to prevent thread exhaustion or denial-of-service hangs.
- **Input Validation**: URLs and ports are strictly validated before execution to prevent malformed queries.
- **No Shell Execution**: The application avoids invoking shell commands (`os.system` or `subprocess`) with user inputs, eliminating command injection risks.
- **SQL Injection Prevention**: All SQLite queries use parameterized queries (`?` placeholders) rather than raw string interpolation.

---

## 21. Limitations
- **Single-Host Database**: SQLite is a file-based database designed for single-node environments. It is not suitable for distributed clusters without a database server like PostgreSQL.
- **Synchronous Checks**: Health checks run synchronously per request. Checking very large lists of URLs sequentially will take time proportional to the number of endpoints.
- **Limited Port Diagnostic Scope**: Only tests standard web ports (80, 443) and individual custom ports. It is not an asynchronous port scanner like Nmap.
- **Non-Continuous Polling**: In its basic form, checks are triggered through user interaction or bulk run buttons rather than a background cron daemon.

---

## 22. Future Improvements
- **Background Cron / Celery Worker**: Add a scheduled background task runner to poll monitored URLs at automated intervals (e.g. every 5 minutes).
- **Alert Notifications**: Integrate webhook or email alerts (e.g. AWS SES or Slack webhooks) when an endpoint transitions to DOWN.
- **Nginx Reverse Proxy & SSL (Production Deployment)**: Put Nginx in front of Streamlit on port 80/443 with Let's Encrypt SSL certificates for secure HTTPS access.
- **PostgreSQL Migration**: Support switching from SQLite to PostgreSQL for concurrent multi-worker environments.
