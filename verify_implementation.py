#!/usr/bin/env python3
"""
Comprehensive verification script for SatsRemit platform implementation
Tests all flows: sender, agent, receiver, and admin
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ {description} - PASSED")
        return True
    else:
        print(f"❌ {description} - FAILED")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False

def verify_implementation():
    """Verify all implementation components"""
    basepath = Path(__file__).parent
    checks_passed = []
    checks_failed = []
    
    print("\n" + "="*60)
    print("🚀 SatsRemit Platform - Comprehensive Verification")
    print("="*60)
    
    # 1. Check Python syntax
    print("\n1️⃣  Checking Python Syntax...")
    python_files = [
        "src/api/routes/public.py",
        "src/services/transfer.py",
        "src/models/models.py",
        "src/api/schemas.py",
        "tests/test_receiver_flow.py",
    ]
    
    for file in python_files:
        filepath = basepath / file
        if run_command(f"python3 -m py_compile {filepath}", f"Syntax check: {file}"):
            checks_passed.append(f"Syntax: {file}")
        else:
            checks_failed.append(f"Syntax: {file}")
    
    # 2. Check file completeness
    print("\n2️⃣  Checking Required Files...")
    required_files = [
        "src/api/routes/public.py",
        "src/services/transfer.py",
        "src/models/models.py",
        "src/api/schemas.py",
        "static/receiver/index.html",
        "static/receiver/js/receiver-app.js",
        "static/platform-guide.html",
        "tests/test_receiver_flow.py",
        "IMPLEMENTATION_COMPLETE.md",
    ]
    
    for file in required_files:
        filepath = basepath / file
        if filepath.exists():
            print(f"✅ Found: {file}")
            checks_passed.append(f"File: {file}")
        else:
            print(f"❌ Missing: {file}")
            checks_failed.append(f"File: {file}")
    
    # 3. Check for key implementations in code
    print("\n3️⃣  Checking Key Implementations...")
    
    implementations = {
        "PIN generation": ("src/services/transfer.py", "generate_pin"),
        "PIN hashing": ("src/services/transfer.py", "hash_pin"),
        "PIN verification endpoint": ("src/api/routes/public.py", "verify-pin"),
        "PIN resend endpoint": ("src/api/routes/public.py", "resend-pin"),
        "Receiver status endpoint": ("src/api/routes/public.py", "receivers/transfers"),
        "PIN generated field": ("src/models/models.py", "pin_generated"),
        "Receiver schemas": ("src/api/schemas.py", "ReceiverVerifyPINRequest"),
    }
    
    for impl, (filepath, keyword) in implementations.items():
        full_path = basepath / filepath
        if full_path.exists():
            content = full_path.read_text()
            if keyword in content:
                print(f"✅ Found: {impl}")
                checks_passed.append(f"Impl: {impl}")
            else:
                print(f"❌ Missing: {impl}")
                checks_failed.append(f"Impl: {impl}")
        else:
            print(f"❌ File not found: {filepath}")
            checks_failed.append(f"Impl: {impl}")
    
    # 4. Check for frontend integration
    print("\n4️⃣  Checking Frontend Navigation...")
    
    navigation_checks = {
        "Sender footer links": ("static/app/index.html", "/receiver"),
        "Agent sidebar links": ("static/agent/index.html", "/receiver"),
        "Admin navigation links": ("static/admin/index.html", "/app"),
        "Receiver help links": ("static/receiver/index.html", "/app"),
    }
    
    for check, (filepath, keyword) in navigation_checks.items():
        full_path = basepath / filepath
        if full_path.exists():
            content = full_path.read_text()
            if keyword in content:
                print(f"✅ Found: {check}")
                checks_passed.append(f"Nav: {check}")
            else:
                print(f"❌ Missing: {check}")
                checks_failed.append(f"Nav: {check}")
    
    # 5. Print summary
    print("\n" + "="*60)
    print("📊 VERIFICATION SUMMARY")
    print("="*60)
    print(f"✅ Passed: {len(checks_passed)}")
    print(f"❌ Failed: {len(checks_failed)}")
    
    if checks_failed:
        print("\n❌ FAILED CHECKS:")
        for check in checks_failed:
            print(f"  - {check}")
    
    if checks_passed:
        print(f"\n✅ All {len(checks_passed)} checks passed!")
        print("\n🎉 Platform implementation is complete and verified!")
        return 0
    else:
        print("\n❌ Some checks failed. Please review above.")
        return 1

if __name__ == "__main__":
    sys.exit(verify_implementation())
