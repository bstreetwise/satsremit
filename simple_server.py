#!/usr/bin/env python3
"""
Minimal HTTP server for testing SatsRemit dashboards
Serves static files without requiring the full FastAPI backend
"""

import os
import http.server
import socketserver
import threading
import time
import sys
from pathlib import Path

PORT = 8000
STATIC_DIR = Path(__file__).parent / "static"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler to serve dashboards from static directory"""
    
    def translate_path(self, path):
        """Translate URL path to file system path"""
        # Remove leading slash
        if path.startswith('/'):
            path = path[1:]
        
        # Map paths to static files
        if path == '':
            path = 'admin/index.html'  # Default to admin panel
        elif path in ['admin', 'agent', 'app', 'receiver']:
            path = f'{path}/index.html'
        
        # Build full path
        full_path = os.path.join(str(STATIC_DIR), path)
        
        # Prevent directory traversal
        full_path = os.path.normpath(full_path)
        if not full_path.startswith(str(STATIC_DIR)):
            return os.path.join(str(STATIC_DIR), '404.html')
        
        return full_path
    
    def log_message(self, format, *args):
        """Suppress verbose logging"""
        if '200' not in format and '301' not in format and '302' not in format:
            sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format%args))


def start_server():
    """Start the static file server"""
    os.chdir(STATIC_DIR)
    
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"\n{'='*60}")
        print(f"SatsRemit Dashboard Server".center(60))
        print(f"{'='*60}\n")
        print(f"Server running at: http://localhost:{PORT}")
        print(f"Serving from: {STATIC_DIR}")
        print(f"\nAvailable dashboards:")
        print(f"  • Admin:    http://localhost:{PORT}/admin")
        print(f"  • Agent:    http://localhost:{PORT}/agent")
        print(f"  • User App: http://localhost:{PORT}/app")
        print(f"  • Receiver: http://localhost:{PORT}/receiver")
        print(f"\nPress Ctrl+C to stop...\n")
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")
            sys.exit(0)


if __name__ == "__main__":
    if not STATIC_DIR.exists():
        print(f"Error: Static directory not found at {STATIC_DIR}")
        sys.exit(1)
    
    start_server()
