#!/usr/bin/env python3
"""
Startup script for Satsremit that loads environment variables from .env file
and starts Uvicorn server.
"""
import subprocess
import sys
import os
from pathlib import Path

# Change to project directory
project_dir = Path(__file__).parent
os.chdir(project_dir)

# Load environment variables from .env file
env_file = project_dir / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)
    print(f"✓ Loaded environment from {env_file}")
else:
    print(f"⚠ Warning: .env file not found at {env_file}")

# Prepare environment with merged values
env = os.environ.copy()

# Start Uvicorn with the loaded environment
cmd = [
    sys.executable, "-m", "uvicorn",
    "src.main:app",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--workers", "2",
    "--log-level", "info"
]

print(f"Starting Uvicorn from {project_dir}: {' '.join(cmd)}")
subprocess.run(cmd, env=env, cwd=project_dir)
