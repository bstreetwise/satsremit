#!/usr/bin/env python3
"""Fix JWT RS256 support"""
import os
os.chdir('/home/satsinaction')

with open('satsremit/src/core/security. py', 'r') as f:
    content = f.read()

# The exact search pattern - find jwt. decode in decode_ token
# Let's look for the exact structure in the file 
if "jwt.decode(" in content:
    # Find location
    idx = content.find("payload = jwt.decode(")
    print(f"Found at {idx}")
    print(repr(content[idx:idx+100]))
