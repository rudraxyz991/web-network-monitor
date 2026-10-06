"""Streamlit Web Application for Web and Network Monitoring Platform."""

import time
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px

from src.utils import normalize_url, validate_url, categorize_status_code
from src.network import resolve_dns, check_tcp_port, check_standard_ports, check_ssl_tls
from src.monitor import WebMonitor
from src.database import DatabaseManager


# Configure page layout and title
st.set_page_config(
    page_title="Web & Network Monitoring Platform",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database manager
db = DatabaseManager()
monitor = WebMonitor(timeout=5.0)


def render_sidebar():
    """Render sidebar with platform information and operational controls."""
    with st.sidebar:
        st.title("🌐 Network Monitor")
        st.markdown(
            "A lightweight diagnostic platform to monitor website availability, "
            "inspect HTTP headers, test DNS resolution, verify TCP ports, and track uptime."
        )
        st.markdown("---")
        
        st.subheader("System Status")
        urls = db.get_monitored_urls()
        metrics = db.get_metrics()
        
        st.metric("Watchlist Targets", len(urls))
        st.metric("Total Historical Checks", metrics["total_checks"])
        st.metric("Overall Availability", f"{metrics['uptime_percentage']}%")
        
        st.markdown("---")
        st.subheader("Quick Reference")
        st.caption("• **2xx**: Successful HTTP response")
        st.caption("• **3xx**: URL redirection")
        st.caption("• **4xx**: Client error (e.g. 404, 403)")
        st.caption("• **5xx**: Server error (e.g. 500, 502)")
        st.caption("• **Port 80**: Standard HTTP (Plain)")
        st.caption("• **Port 443**: Standard HTTPS (TLS)")
        
        st.markdown("---")
        st.caption("Developed with Python, Streamlit, and SQLite.")


def render_quick_diagnostic_tab():
    """Render single URL quick diagnostic check interface."""
    st.header("⚡ Single URL Diagnostic Check")
    st.markdown("Enter any website or API endpoint to perform immediate HTTP and network diagnostics.")

    col_input, col_port = st.columns([3, 1])
    with col_input:
        raw_url = st.text_input(
            "Target URL",
            value="https://example.com",
            help="Enter a complete URL or domain name (e.g. https://example.com or github.com)"
        )
    with col_port:
        custom_port_str = st.text_input(
            "Custom TCP Port (Optional)",
            value="",
            help="Optional port number to test (e.g. 8080 or 22)"
        )

    col_opt1, col_opt2, col_btn = st.columns([1.5, 1.5, 1.5])
    with col_opt1:
        follow_redirects = st.checkbox("Follow HTTP Redirects", value=True)
    with col_opt2:
        save_result = st.checkbox("Save Result to History", value=True)
    with col_btn:
        check_button = st.button("🚀 Run Diagnostic Check", type="primary", use_container_width=True)

    if check_button:
        # Validate custom port if provided
        custom_ports = []
        if custom_port_str.strip():
            try:
                cp = int(custom_port_str.strip())
                if 1 <= cp <= 65535:
                    custom_ports.append(cp)
                else:
                    st.warning("Custom port must be between 1 and 65535. Ignoring custom port.")
            except ValueError:
                st.warning("Custom port must be a valid number. Ignoring custom port.")

        with st.spinner(f"Running diagnostics for {raw_url}..."):
            result = monitor.check_url(
                raw_url,
                custom_ports=custom_ports,
                follow_redirects=follow_redirects
            )

        # Handle invalid URL
        if not result["is_valid"]:
            st.error(f"❌ Invalid URL: {result['error_message']}")
            return

        # Save to database if requested
        if save_result:
            db.record_check(
                url=result["url"],
                status=result["status"],
                status_code=result["status_code"],
                response_time_ms=result["response_time_ms"],
                resolved_ip=result["resolved_ip"],
                error_message=result["error_message"]
            )

        st.markdown("---")

        # Top-level KPI cards
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        
        status_value = result["status"]
        status_color = "🟢" if status_value == "UP" else ("🟡" if status_value == "WARNING" else "🔴")
        kpi1.metric("Site Status", f"{status_color} {status_value}")

        status_code = result["status_code"]
        kpi2.metric("HTTP Status", str(status_code) if status_code else "N/A")

        lat = result["response_time_ms"]
        kpi3.metric("Response Time", f"{lat} ms" if lat is not None else "N/A")

        ip = result["resolved_ip"]
        kpi4.metric("Resolved IP", ip if ip else "Not Resolved")

        is_sec = result["is_https"]
        kpi5.metric("Protocol", "HTTPS (Secure)" if is_sec else "HTTP (Plain)")

        # Status explanation banner
        if status_value == "UP":
            st.success(f"Endpoint is reachable. Returned HTTP {status_code} in {lat} ms.")
        elif status_value == "WARNING":
            st.warning(f"Endpoint reached with client-side notice: HTTP {status_code}. {result['error_message']}")
        else:
            st.error(f"Endpoint check failed or returned server error. {result['error_message']}")

        # Diagnostic Details in Tabs
        tab_http, tab_dns, tab_ports, tab_ssl = st.tabs([
            "📡 HTTP Details", "🌍 DNS Diagnostics", "🔌 Port Diagnostics", "🔒 SSL / TLS Info"
        ])

        with tab_http:
            http_data = result["http"]
            if http_data:
                col_h1, col_h2 = st.columns(2)
                with col_h1:
                    st.write("**Request URL:**", result["url"])
                    st.write("**Final URL:**", http_data["final_url"])
                    st.write("**Status Category:**", http_data["status_category"])
                    st.write("**Description:**", http_data["status_description"])
                    st.write("**Redirects Encountered:**", http_data["redirect_count"])
                    
                    if http_data["redirect_chain"]:
                        st.write("**Redirect Path:**")
                        for idx, hop in enumerate(http_data["redirect_chain"], 1):
                            st.caption(f"{idx}. HTTP {hop['status_code']} -> {hop['url']}")
                with col_h2:
                    st.write("**Response Headers:**")
                    if http_data["headers"]:
                        st.json(http_data["headers"])
                    else:
                        st.info("No key headers were received.")
            else:
                st.info("HTTP request was not completed due to network error.")

        with tab_dns:
            dns_data = result["dns"]
            if dns_data:
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.write("**Target Hostname:**", dns_data["hostname"])
                    st.write("**DNS Resolution:**", "Success" if dns_data["is_resolved"] else "Failed")
                    st.write("**Resolution Time:**", f"{dns_data['resolution_time_ms']} ms")
                    if dns_data["error_message"]:
                        st.error(dns_data["error_message"])
                with col_d2:
                    st.write("**Resolved IPv4 Addresses:**")
                    if dns_data["ip_addresses"]:
                        for ip_item in dns_data["ip_addresses"]:
                            st.code(ip_item, language="text")
                    else:
                        st.caption("No IP addresses found.")
            st.caption("DNS translates domain names into IP addresses for routing internet packets.")

        with tab_ports:
            ports = result["ports"]
            if ports:
                port_rows = []
                for p in ports:
                    port_rows.append({
                        "Port": p["port"],
                        "Service": p["service"],
                        "Reachability": "Reachable" if p["is_reachable"] else "Not Reachable",
                        "Latency (ms)": f"{p['response_time_ms']} ms" if p["is_reachable"] else "N/A",
                        "Notes": p["error_message"] if p["error_message"] else "Handshake succeeded"
                    })
                st.table(pd.DataFrame(port_rows))
            st.caption("TCP connection tests verify whether target ports accept incoming connections.")

        with tab_ssl:
            ssl_info = result["ssl"]
            if ssl_info:
                if ssl_info["is_tls_available"]:
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.write("**TLS Status:**", ssl_info["status_label"])
                        st.write("**TLS Protocol Version:**", ssl_info["tls_version"])
                        st.write("**Negotiated Cipher Suite:**", ssl_info["cipher_name"])
                        st.write("**Handshake Latency:**", f"{ssl_info['handshake_time_ms']} ms")
                    with col_s2:
                        st.write("**Certificate Common Name:**", ssl_info["common_name"])
                        st.write("**Certificate Issuer:**", ssl_info["issuer"])
                        st.write("**Valid Until:**", ssl_info["valid_until"])
                        rem = ssl_info["days_remaining"]
                        if rem is not None:
                            st.write("**Days Remaining:**", f"{rem} days")
                else:
                    st.warning(f"SSL/TLS check failed: {ssl_info['error_message']}")
            else:
                st.info("SSL/TLS inspection is only performed for HTTPS connections.")


def render_watchlist_tab():
    """Render watchlist management and bulk monitoring checks."""
    st.header("📋 Monitored Targets Watchlist")
    st.markdown("Maintain a list of critical URLs and check their operational status simultaneously.")

    # Add URL Section
    with st.expander("➕ Add New Target to Watchlist", expanded=False):
        col_url, col_lbl, col_add = st.columns([3, 2, 1])
        with col_url:
            new_url = st.text_input("Website or API URL", placeholder="https://api.github.com", key="watch_new_url")
        with col_lbl:
            new_label = st.text_input("Friendly Label", placeholder="GitHub API", key="watch_new_label")
        with col_add:
            st.write("")
            st.write("")
            add_clicked = st.button("Add Target", type="primary")

        if add_clicked:
            if not new_url.strip():
                st.error("URL cannot be empty.")
            else:
                norm_url = normalize_url(new_url)
                valid, msg = validate_url(norm_url)
                if not valid:
                    st.error(f"Invalid URL: {msg}")
                else:
                    success = db.add_monitored_url(norm_url, new_label.strip())
                    if success:
                        st.success(f"Added '{norm_url}' to watchlist.")
                        st.rerun()
                    else:
                        st.warning("This URL is already present in your watchlist.")

    # Show existing watchlist
    targets = db.get_monitored_urls()
    if not targets:
        st.info("No targets in watchlist yet. Add one above to start monitoring.")
        return

    st.subheader(f"Current Watchlist ({len(targets)} targets)")
    
    col_run_all, col_empty = st.columns([2, 4])
    with col_run_all:
        run_all_btn = st.button("🔄 Check All Targets Now", type="primary", use_container_width=True)

    if run_all_btn:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, target in enumerate(targets):
            url_to_check = target["url"]
            status_text.text(f"Checking {url_to_check} ({idx + 1}/{len(targets)})...")
            res = monitor.check_url(url_to_check)
            db.record_check(
                url=res["url"],
                status=res["status"],
                status_code=res["status_code"],
                response_time_ms=res["response_time_ms"],
                resolved_ip=res["resolved_ip"],
                error_message=res["error_message"]
            )
            progress_bar.progress((idx + 1) / len(targets))
            time.sleep(0.1)
            
        status_text.text("All checks completed.")
        st.success("Watchlist checked and historical database updated.")
        time.sleep(0.5)
        st.rerun()

    # Table of targets with delete option
    target_data = []
    for item in targets:
        # Get latest metrics for this URL
        url_metrics = db.get_metrics(item["url"])
        history_df = db.get_history(item["url"], limit=1)
        latest_status = history_df.iloc[0]["status"] if not history_df.empty else "No Data"
        latest_code = history_df.iloc[0]["status_code"] if not history_df.empty else None
        
        target_data.append({
            "Label": item["label"] or "Untitled",
            "URL": item["url"],
            "Latest Status": latest_status,
            "Latest Code": str(latest_code) if latest_code is not None else "N/A",
            "Uptime %": f"{url_metrics['uptime_percentage']}%",
            "Avg Latency": f"{url_metrics['avg_response_time_ms']} ms" if url_metrics['avg_response_time_ms'] else "N/A",
            "Total Checks": url_metrics["total_checks"]
        })

    st.dataframe(pd.DataFrame(target_data), use_container_width=True)

    # Remove target controls
    with st.expander("🗑️ Remove Target from Watchlist"):
        url_options = [t["url"] for t in targets]
        selected_to_remove = st.selectbox("Select Target to Remove", options=url_options)
        if st.button("Delete Target", type="secondary"):
            if db.remove_monitored_url(selected_to_remove):
                st.success(f"Removed '{selected_to_remove}' from watchlist.")
                st.rerun()


def render_analytics_tab():
    """Render monitoring history and graphical performance analytics."""
    st.header("📊 Monitoring Analytics & History")
    st.markdown("Inspect historical availability metrics, response times, and failure logs.")

    targets = db.get_monitored_urls()
    url_choices = ["All Monitored Targets"] + [t["url"] for t in targets]
    
    col_sel, col_lim = st.columns([3, 1])
    with col_sel:
        selected_url_filter = st.selectbox("Filter by Endpoint", options=url_choices)
    with col_lim:
        record_limit = st.selectbox("Record Limit", options=[50, 100, 250, 500], index=1)

    target_filter = None if selected_url_filter == "All Monitored Targets" else selected_url_filter

    metrics = db.get_metrics(url=target_filter)
    history_df = db.get_history(url=target_filter, limit=record_limit)

    if metrics["total_checks"] == 0:
        st.info("No historical check records found. Run a diagnostic check to generate telemetry.")
        return

    # Metrics Summary Row
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Uptime", f"{metrics['uptime_percentage']}%")
    m2.metric("Total Checks", metrics["total_checks"])
    m3.metric("Successful (UP)", metrics["successful_checks"])
    m4.metric("Failures", metrics["failed_checks"])
    m5.metric("Avg Latency", f"{metrics['avg_response_time_ms']} ms" if metrics['avg_response_time_ms'] else "N/A")
    m6.metric("Min / Max Latency", f"{metrics['min_response_time_ms'] or 0} / {metrics['max_response_time_ms'] or 0} ms")

    st.markdown("---")

    # Visualizations
    col_chart1, col_chart2 = st.columns([3, 2])

    with col_chart1:
        st.subheader("📈 Response Time History")
        if not history_df.empty and "checked_at" in history_df.columns:
            chart_df = history_df.dropna(subset=["response_time_ms"]).sort_values("checked_at")
            if not chart_df.empty:
                fig = px.line(
                    chart_df,
                    x="checked_at",
                    y="response_time_ms",
                    color="url" if target_filter is None else None,
                    markers=True,
                    labels={"checked_at": "Timestamp", "response_time_ms": "Latency (ms)", "url": "Target"},
                    title="Response Latency (ms) Over Time"
                )
                fig.update_layout(xaxis_title="Time", yaxis_title="Milliseconds", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("No valid response times to plot.")

    with col_chart2:
        st.subheader("🥧 HTTP Status Distribution")
        dist_data = metrics.get("status_distribution", {})
        if dist_data:
            dist_df = pd.DataFrame(list(dist_data.items()), columns=["Status Code", "Count"])
            fig_pie = px.pie(
                dist_df,
                names="Status Code",
                values="Count",
                title="Response Status Breakdown",
                hole=0.4
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.caption("No status codes recorded.")

    # Recent Failures Section
    st.subheader("⚠️ Recent Failures & Alerts")
    failures = db.get_recent_failures(url=target_filter, limit=5)
    if failures:
        fail_df = pd.DataFrame(failures)[["checked_at", "url", "status", "status_code", "error_message"]]
        st.dataframe(fail_df, use_container_width=True)
    else:
        st.success("No recent failures recorded for this filter.")

    # Full History Logs Table
    st.subheader("📋 Raw Check History Log")
    st.dataframe(history_df, use_container_width=True)

    # Clear History action
    with st.expander("🧹 History Maintenance"):
        st.warning("Clearing history permanently deletes stored logs from the database.")
        if st.button("Clear History Records", type="secondary"):
            deleted = db.clear_history(url=target_filter)
            st.success(f"Cleared {deleted} records from database.")
            st.rerun()


def render_network_tools_tab():
    """Render standalone DNS and TCP port diagnostic lab tools."""
    st.header("🛠️ Standalone Network Diagnostics Lab")
    st.markdown("Direct diagnostic tools for debugging low-level networking without HTTP requests.")

    tool_dns, tool_port = st.columns(2)

    with tool_dns:
        st.subheader("🔍 Standalone DNS Resolver")
        dns_host = st.text_input("Domain Name", value="example.com", key="tools_dns_host")
        if st.button("Resolve DNS", key="tools_dns_btn"):
            if not dns_host.strip():
                st.error("Please enter a domain name.")
            else:
                with st.spinner("Resolving DNS records..."):
                    dns_res = resolve_dns(dns_host.strip())
                if dns_res["is_resolved"]:
                    st.success(f"Resolved in {dns_res['resolution_time_ms']} ms")
                    st.write("**Primary IP:**", dns_res["primary_ip"])
                    st.write("**All Addresses:**")
                    for ip_entry in dns_res["ip_addresses"]:
                        st.code(ip_entry, language="text")
                else:
                    st.error(f"Resolution Failed: {dns_res['error_message']}")

    with tool_port:
        st.subheader("🔌 Standalone TCP Port Tester")
        col_phost, col_pport = st.columns([2, 1])
        with col_phost:
            port_host = st.text_input("Host / IP", value="example.com", key="tools_port_host")
        with col_pport:
            port_num = st.number_input("TCP Port", min_value=1, max_value=65535, value=443, key="tools_port_num")

        if st.button("Check TCP Connection", key="tools_port_btn"):
            if not port_host.strip():
                st.error("Please enter a host.")
            else:
                with st.spinner("Attempting TCP handshake..."):
                    p_res = check_tcp_port(port_host.strip(), int(port_num))
                if p_res["is_reachable"]:
                    st.success(f"Port {port_num} ({p_res['service']}) is REACHABLE ({p_res['response_time_ms']} ms).")
                else:
                    st.error(f"Port {port_num} ({p_res['service']}) is NOT REACHABLE. {p_res['error_message']}")


def main():
    """Main application entrypoint."""
    render_sidebar()
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "⚡ Quick Diagnostic",
        "📋 Target Watchlist",
        "📊 Historical Analytics",
        "🛠️ Network Lab"
    ])

    with tab1:
        render_quick_diagnostic_tab()
    with tab2:
        render_watchlist_tab()
    with tab3:
        render_analytics_tab()
    with tab4:
        render_network_tools_tab()


if __name__ == "__main__":
    main()
