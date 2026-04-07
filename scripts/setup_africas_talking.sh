#!/bin/bash
# Quick Setup: Africa's Talking SMS Configuration

echo "🚀 SatsRemit Africa's Talking Setup"
echo "===================================="
echo ""
echo "Step 1: Get API Credentials"
echo "  1. Visit: https://africastalking.com"
echo "  2. Sign up (Free $10 credits)"
echo "  3. Go to: https://app.africastalking.com/settings/api"
echo "  4. Copy API Key and Username"
echo ""
echo "Step 2: Update .env File"
echo "  Edit .env and add:"
echo "  AFRICAS_TALKING_API_KEY=<your_api_key>"
echo "  AFRICAS_TALKING_USERNAME=<your_username>"
echo "  AFRICAS_TALKING_SHORTCODE=<optional>"
echo ""
echo "Step 3: Test Connection"
python3 << 'EOF'
import os
import sys
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("AFRICAS_TALKING_API_KEY")
username = os.getenv("AFRICAS_TALKING_USERNAME")

if api_key and username:
    print("✓ API credentials configured")
    print(f"  Username: {username}")
    print(f"  API Key: {api_key[:10]}...")
else:
    print("✗ Missing credentials in .env")
    sys.exit(1)
EOF
echo ""
echo "Step 4: Ready to Use!"
echo "  from src.services.notification import get_notification_service"
echo "  service = get_notification_service()"
echo "  await service.send_sms('+263712345678', 'Hello')"
echo ""
echo "Documentation: docs/AFRICAS_TALKING_SETUP.md"
