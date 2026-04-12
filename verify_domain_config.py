#!/usr/bin/env python3
"""
Verify that all dashboards are properly configured for satsremit.com domain
"""

import re
import sys
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")

def print_error(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")

def check_file_for_pattern(filepath, should_contain=None, should_not_contain=None):
    """Check if file contains or doesn't contain certain patterns"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        if should_contain:
            for pattern in should_contain:
                if pattern in content:
                    return True, f"Found: {pattern}"
                else:
                    return False, f"Missing: {pattern}"
        
        if should_not_contain:
            for pattern in should_not_contain:
                if pattern in content:
                    return False, f"Should not contain: {pattern}"
                else:
                    return True, f"Correctly excluded: {pattern}"
        
        return True, "File OK"
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    print(f"\n{Colors.BOLD}SatsRemit Domain Configuration Verification{Colors.RESET}")
    print(f"Verifying all dashboards are accessible from https://satsremit.com\n")
    
    base_path = Path('/home/satsinaction/satsremit')
    results = {}
    
    print_header("Checking Frontend Dashboard Links")
    
    # Check Admin Panel - should have correct links
    admin_file = base_path / 'static/admin/index.html'
    success, msg = check_file_for_pattern(
        admin_file,
        should_contain=['href="/app"', 'href="/agent"', 'href="/receiver"']
    )
    results['Admin Panel Links'] = success
    if success:
        print_success(f"Admin panel has correct external links")
    else:
        print_error(f"Admin panel: {msg}")
    
    # Check App Dashboard - should NOT have /api/admin
    app_file = base_path / 'static/app/index.html'
    success, msg = check_file_for_pattern(
        app_file,
        should_not_contain=['href="/api/admin"']
    )
    results['App Dashboard Fixed'] = success
    if success:
        print_success(f"App dashboard: /api/admin link removed")
    else:
        print_error(f"App dashboard: {msg}")
    
    # Check App Dashboard has /admin
    success, msg = check_file_for_pattern(
        app_file,
        should_contain=['href="/admin"']
    )
    results['App Dashboard Admin Link'] = success
    if success:
        print_success(f"App dashboard has correct /admin link")
    else:
        print_error(f"App dashboard: {msg}")
    
    # Check Agent Dashboard - should have correct links
    agent_file = base_path / 'static/agent/index.html'
    success, msg = check_file_for_pattern(
        agent_file,
        should_contain=['href="/app"', 'href="/admin"', 'href="/receiver"']
    )
    results['Agent Dashboard Links'] = success
    if success:
        print_success(f"Agent dashboard has correct external links")
    else:
        print_error(f"Agent dashboard: {msg}")
    
    # Check Receiver Portal - should NOT have /api/admin
    receiver_file = base_path / 'static/receiver/index.html'
    success, msg = check_file_for_pattern(
        receiver_file,
        should_not_contain=['href="/api/admin"']
    )
    results['Receiver Portal Fixed'] = success
    if success:
        print_success(f"Receiver portal: /api/admin link removed")
    else:
        print_error(f"Receiver portal: {msg}")
    
    # Check Receiver Portal has /admin
    success, msg = check_file_for_pattern(
        receiver_file,
        should_contain=['href="/admin"']
    )
    results['Receiver Portal Admin Link'] = success
    if success:
        print_success(f"Receiver portal has correct /admin link")
    else:
        print_error(f"Receiver portal: {msg}")
    
    print_header("Checking Backend Configuration")
    
    # Check main.py for CORS
    main_file = base_path / 'src/main.py'
    success, msg = check_file_for_pattern(
        main_file,
        should_contain=[
            '"https://agent.satsremit.com"',
            '"https://receiver.satsremit.com"'
        ]
    )
    results['CORS Configuration'] = success
    if success:
        print_success(f"CORS configured for agent and receiver subdomains")
    else:
        print_error(f"CORS missing agent/receiver subdomains")
    
    # Check main.py for Trusted Hosts
    success, msg = check_file_for_pattern(
        main_file,
        should_contain=['agent.satsremit.com', 'receiver.satsremit.com']
    )
    results['Trusted Hosts'] = success
    if success:
        print_success(f"Trusted hosts configured for agent and receiver subdomains")
    else:
        print_error(f"Trusted hosts: {msg}")
    
    # Check API modules use relative paths
    admin_api = base_path / 'static/admin/js/api.js'
    success, msg = check_file_for_pattern(
        admin_api,
        should_contain=["BASE_URL: '/api'"]
    )
    results['Admin API Relative Path'] = success
    if success:
        print_success(f"Admin API uses relative path")
    else:
        print_error(f"Admin API: {msg}")
    
    app_api = base_path / 'static/app/js/api.js'
    success, msg = check_file_for_pattern(
        app_api,
        should_contain=["BASE_URL: '/api'"]
    )
    results['App API Relative Path'] = success
    if success:
        print_success(f"App API uses relative path")
    else:
        print_error(f"App API: {msg}")
    
    agent_api = base_path / 'static/agent/js/api.js'
    success, msg = check_file_for_pattern(
        agent_api,
        should_contain=["BASE_URL: '/api/agent'"]
    )
    results['Agent API Relative Path'] = success
    if success:
        print_success(f"Agent API uses relative path")
    else:
        print_error(f"Agent API: {msg}")
    
    print_header("Configuration Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check_name, result in results.items():
        status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if result else f"{Colors.RED}✗ FAIL{Colors.RESET}"
        print(f"{status} - {check_name}")
    
    print(f"\n{Colors.BOLD}Score: {passed}/{total}{Colors.RESET}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}✓ All configurations are correct!{Colors.RESET}")
        print(f"\n{Colors.BOLD}Dashboards are now accessible from https://satsremit.com:{Colors.RESET}")
        print(f"  • https://satsremit.com/app")
        print(f"  • https://satsremit.com/admin")
        print(f"  • https://satsremit.com/agent")
        print(f"  • https://satsremit.com/receiver")
        return 0
    else:
        print(f"\n{Colors.RED}✗ Some configurations need attention{Colors.RESET}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
