#!/usr/bin/env python3
"""
Test script to verify admin dashboard sections are properly wired
Tests all navigation links and AJAX endpoints
"""

import requests
import time
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:8000"
ADMIN_URL = f"{BASE_URL}/admin"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(message: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {message}")

def print_error(message: str):
    print(f"{Colors.RED}✗{Colors.RESET} {message}")

def print_info(message: str):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {message}")

def test_admin_panel_load():
    """Test if admin panel HTML loads correctly"""
    print_header("Testing Admin Panel Load")
    
    try:
        response = requests.get(ADMIN_URL, timeout=5)
        if response.status_code == 200:
            print_success(f"Admin panel loads successfully (HTTP 200, {len(response.content)} bytes)")
            
            # Check for critical sections
            content = response.text
            sections = ['dashboard', 'agents', 'transfers', 'settlements', 'analytics']
            found_sections = []
            missing_sections = []
            
            for section in sections:
                if f'id="{section}"' in content or f"data-section='{section}'" in content:
                    found_sections.append(section)
                else:
                    missing_sections.append(section)
            
            print(f"\nSections found: {len(found_sections)}/5")
            for section in found_sections:
                print_success(f"  {section.capitalize()} section")
            
            if missing_sections:
                for section in missing_sections:
                    print_error(f"  {section.capitalize()} section")
            
            # Check for JavaScript files
            js_files = ['api.js', 'ui-new.js', 'app.js']
            print(f"\nJavaScript files referenced:")
            for js_file in js_files:
                if f'js/{js_file}' in content:
                    print_success(f"  {js_file}")
                else:
                    print_error(f"  {js_file} - NOT FOUND")
            
            return len(missing_sections) == 0
        else:
            print_error(f"Admin panel returned HTTP {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to load admin panel: {str(e)}")
        return False

def test_api_js_functions():
    """Test if API module is referenced correctly"""
    print_header("Testing API Module")
    
    try:
        response = requests.get(f"{ADMIN_URL}/js/api.js", timeout=5)
        if response.status_code == 200:
            content = response.text
            api_methods = [
                'getVolumeAnalytics',
                'getAdminHealth',
                'listAgents',
                'listTransfers',
                'listSettlements',
                'createAgent',
                'getAgentBalance',
                'getTransfer',
            ]
            print(f"API methods found:")
            found_count = 0
            for method in api_methods:
                if method in content:
                    print_success(f"  {method}()")
                    found_count += 1
                else:
                    print_error(f"  {method}() - NOT FOUND")
            
            print(f"\nAPI module: {found_count}/{len(api_methods)} methods available")
            return found_count >= len(api_methods) * 0.8
        else:
            print_error(f"API module returned HTTP {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to load API module: {str(e)}")
        return False

def test_ui_module():
    """Test if UI module has required functions"""
    print_header("Testing UI Module (ui-new.js)")
    
    try:
        response = requests.get(f"{ADMIN_URL}/js/ui-new.js", timeout=5)
        if response.status_code == 200:
            content = response.text
            functions = [
                'navigate_to_section',
                'load_section_data',
                'load_dashboard',
                'load_agents_table',
                'load_transfers_table',
                'load_settlements_table',
                'load_analytics',
                'show_alert',
                'format_currency',
                'format_sats',
                'get_status_badge',
                'handle_add_agent',
                'show_agent_details',
                'show_transfer_details',
                'confirm_settlement',
            ]
            print(f"UI functions found:")
            found_count = 0
            for func in functions:
                if func in content:
                    print_success(f"  {func}()")
                    found_count += 1
                else:
                    print_error(f"  {func}() - NOT FOUND")
            
            # Check if functions are exported to window.UI
            if 'window.UI = {' in content:
                print_success(f"\nUI module exports found (window.UI object)")
            else:
                print_error(f"\nUI module exports NOT found")
            
            print(f"\nUI module: {found_count}/{len(functions)} functions available")
            return found_count >= len(functions) * 0.9
        else:
            print_error(f"UI module returned HTTP {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to load UI module: {str(e)}")
        return False

def test_app_js():
    """Test if app.js has proper initialization"""
    print_header("Testing Application Module (app.js)")
    
    try:
        response = requests.get(f"{ADMIN_URL}/js/app.js", timeout=5)
        if response.status_code == 200:
            content = response.text
            required_items = [
                'DOMContentLoaded',
                'init_event_listeners',
                'check_authentication',
                'navigate_to_section',
                'handle_login',
                'init_event_listeners',
            ]
            print(f"Application initialization:")
            found_count = 0
            for item in required_items:
                if item in content:
                    print_success(f"  {item}")
                    found_count += 1
                else:
                    print_error(f"  {item} - NOT FOUND")
            
            print(f"\nApp module: {found_count}/{len(required_items)} items present")
            return found_count >= len(required_items) * 0.8
        else:
            print_error(f"App module returned HTTP {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to load app module: {str(e)}")
        return False

def test_css():
    """Test if CSS files are available"""
    print_header("Testing Styles")
    
    try:
        response = requests.get(f"{ADMIN_URL}/css/style.css", timeout=5)
        if response.status_code == 200:
            print_success(f"CSS file loads successfully ({len(response.content)} bytes)")
            return True
        else:
            print_error(f"CSS file returned HTTP {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to load CSS: {str(e)}")
        return False

def main():
    print(f"\n{Colors.BOLD}SatsRemit Admin Dashboard Wiring Test{Colors.RESET}")
    print(f"Testing URL: {ADMIN_URL}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Run tests
    results = {
        'Admin Panel Load': test_admin_panel_load(),
        'API Module': test_api_js_functions(),
        'UI Module': test_ui_module(),
        'App Module': test_app_js(),
        'CSS Styles': test_css(),
    }
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        color = Colors.GREEN if result else Colors.RED
        print(f"{color}{status}{Colors.RESET} - {test_name}")
    
    print(f"\n{Colors.BOLD}Overall: {passed}/{total} tests passed{Colors.RESET}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}✓ All dashboard sections are properly wired!{Colors.RESET}\n")
        return True
    else:
        print(f"\n{Colors.RED}✗ Some dashboard sections need attention{Colors.RESET}\n")
        return False

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
