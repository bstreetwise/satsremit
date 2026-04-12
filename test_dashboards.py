#!/usr/bin/env python3
"""
Test script to verify all SatsRemit dashboards are accessible
Tests connectivity to all frontend applications and key endpoints
"""

import requests
import time
import sys
from typing import Dict, List, Tuple
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
DASHBOARDS = {
    "Admin Panel": "/admin",
    "Agent Dashboard": "/agent",
    "User App (Send Money)": "/app",
    "Receiver Portal": "/receiver",
    "Platform Guide": "/platform-guide.html",
}

API_ENDPOINTS = {
    "Health Check": "/health",
    "API Root": "/",
    "API Docs": "/api/docs",
    "API ReDoc": "/api/redoc",
}

TIMEOUT = 5  # seconds


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.GREEN}✓{Colors.RESET} {message}")


def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.RED}✗{Colors.RESET} {message}")


def print_warning(message: str):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {message}")


def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {message}")


def test_connectivity(base_url: str, timeout: int = TIMEOUT) -> bool:
    """Test if the server is reachable"""
    try:
        response = requests.get(base_url, timeout=timeout)
        return response.status_code < 500
    except requests.exceptions.ConnectionError:
        return False
    except requests.exceptions.Timeout:
        return False
    except Exception:
        return False


def test_endpoint(name: str, url: str, expected_status: List[int] = None) -> Tuple[bool, int, str]:
    """
    Test an individual endpoint
    
    Args:
        name: Endpoint name for display
        url: Full URL to test
        expected_status: List of acceptable status codes (default: 200-299)
    
    Returns:
        Tuple of (success, status_code, response_info)
    """
    if expected_status is None:
        expected_status = [200, 201, 202, 203, 204, 205, 206]
    
    try:
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
        status_code = response.status_code
        content_length = len(response.content)
        
        is_success = status_code in expected_status
        
        # Additional checks for HTML pages
        is_html = 'text/html' in response.headers.get('content-type', '')
        has_content = content_length > 100
        
        if response.status_code == 404:
            return False, status_code, "Not found"
        elif response.status_code == 500:
            return False, status_code, "Server error"
        elif is_success and has_content:
            return True, status_code, f"{content_length} bytes"
        elif is_success:
            return True, status_code, f"{content_length} bytes (small)"
        else:
            return False, status_code, f"Unexpected status"
            
    except requests.exceptions.ConnectionError as e:
        return False, 0, "Connection refused"
    except requests.exceptions.Timeout:
        return False, 0, "Timeout"
    except requests.exceptions.RequestException as e:
        return False, 0, str(e)
    except Exception as e:
        return False, 0, str(e)


def test_dashboards() -> Dict[str, bool]:
    """Test all dashboard endpoints"""
    results = {}
    
    print_header("Testing Dashboards")
    
    for dashboard_name, endpoint in DASHBOARDS.items():
        url = f"{BASE_URL}{endpoint}"
        success, status_code, info = test_endpoint(dashboard_name, url)
        
        if success:
            print_success(f"{dashboard_name:<30} | {status_code} | {info}")
        else:
            print_error(f"{dashboard_name:<30} | {status_code} | {info}")
        
        results[dashboard_name] = success
    
    return results


def test_api_endpoints() -> Dict[str, bool]:
    """Test all API endpoints"""
    results = {}
    
    print_header("Testing API Endpoints")
    
    for endpoint_name, endpoint in API_ENDPOINTS.items():
        url = f"{BASE_URL}{endpoint}"
        success, status_code, info = test_endpoint(endpoint_name, url, expected_status=[200, 404])
        
        if success:
            print_success(f"{endpoint_name:<30} | {status_code} | {info}")
        elif status_code == 404:
            print_warning(f"{endpoint_name:<30} | {status_code} | Not available (may be disabled in production)")
        else:
            print_error(f"{endpoint_name:<30} | {status_code} | {info}")
        
        results[endpoint_name] = success or status_code == 404
    
    return results


def test_dashboard_internals() -> Dict[str, List[Tuple[str, bool]]]:
    """Test key resources within each dashboard"""
    results = {}
    
    print_header("Testing Dashboard Resources")
    
    dashboard_resources = {
        "Admin Panel": [
            "/admin/index.html",
            "/admin/css/",
            "/admin/js/",
        ],
        "Agent Dashboard": [
            "/agent/index.html",
            "/agent/js/",
        ],
        "User App": [
            "/app/index.html",
            "/app/css/",
            "/app/js/",
        ],
        "Receiver Portal": [
            "/receiver/index.html",
            "/receiver/js/",
        ],
    }
    
    for dashboard, resources in dashboard_resources.items():
        print(f"\n{Colors.BOLD}{dashboard}{Colors.RESET}")
        dashboard_results = []
        
        for resource in resources:
            url = f"{BASE_URL}{resource}"
            success, status_code, info = test_endpoint(resource, url, expected_status=[200, 301, 302])
            
            if success:
                print_success(f"  {resource:<40} | {status_code}")
            else:
                print_error(f"  {resource:<40} | {status_code}")
            
            dashboard_results.append((resource, success))
        
        results[dashboard] = dashboard_results
    
    return results


def generate_report(dashboard_results: Dict, api_results: Dict, resource_results: Dict) -> None:
    """Generate a summary report"""
    print_header("Test Summary Report")
    
    # Count successes
    dashboard_pass = sum(1 for v in dashboard_results.values() if v)
    dashboard_total = len(dashboard_results)
    
    api_pass = sum(1 for v in api_results.values() if v)
    api_total = len(api_results)
    
    resource_pass = 0
    resource_total = 0
    for resources in resource_results.values():
        for _, success in resources:
            if success:
                resource_pass += 1
            resource_total += 1
    
    # Print summary
    print(f"Dashboards:     {dashboard_pass}/{dashboard_total} passing", end="")
    if dashboard_pass == dashboard_total:
        print(f" {Colors.GREEN}✓ All working{Colors.RESET}")
    else:
        print(f" {Colors.RED}✗ Some failing{Colors.RESET}")
    
    print(f"API Endpoints:  {api_pass}/{api_total} passing", end="")
    if api_pass == api_total:
        print(f" {Colors.GREEN}✓ All working{Colors.RESET}")
    else:
        print(f" {Colors.YELLOW}⚠ Some unavailable (may be expected){Colors.RESET}")
    
    print(f"Resources:      {resource_pass}/{resource_total} passing", end="")
    if resource_pass == resource_total:
        print(f" {Colors.GREEN}✓ All working{Colors.RESET}")
    else:
        print(f" {Colors.RED}✗ Some missing{Colors.RESET}")
    
    # Overall status
    print_header("Overall Status")
    if dashboard_pass == dashboard_total and resource_pass == resource_total:
        print_success("All dashboards are working and reachable!")
        return True
    else:
        print_error("Some dashboards or resources are not accessible")
        return False


def main():
    """Main test function"""
    print(f"\n{Colors.BOLD}SatsRemit Dashboard Accessibility Test{Colors.RESET}")
    print(f"Testing URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Check if server is running
    print("Checking server connectivity...")
    if not test_connectivity(BASE_URL):
        print_error(f"Cannot connect to server at {BASE_URL}")
        print_info("Make sure the application is running with: make dev")
        sys.exit(1)
    else:
        print_success(f"Server is reachable at {BASE_URL}\n")
    
    # Run tests
    dashboard_results = test_dashboards()
    api_results = test_api_endpoints()
    resource_results = test_dashboard_internals()
    
    # Generate report
    all_pass = generate_report(dashboard_results, api_results, resource_results)
    
    # Return appropriate exit code
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
