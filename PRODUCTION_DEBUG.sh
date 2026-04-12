#!/bin/bash
# Production Debug Script - Run on your production server at satsremit.com

echo "=========================================="
echo "SatsRemit Production Debug"
echo "=========================================="

echo ""
echo "1. Check API Status"
curl -s -I https://satsremit.com/health | head -1

echo ""
echo "2. Test Admin Login (should succeed)"
echo "Command to run:"
echo 'curl -X POST https://satsremit.com/api/admin/auth/login \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{"phone": "+27111111111", "password": "Admin1234"}'"'"

echo ""
echo "3. Check API Service Status"
echo "sudo systemctl status satsremit-api"

echo ""
echo "4. Check API Logs (Last 100 errors related to agent creation)"
echo "sudo tail -100 /var/log/api/satsremit.log | grep -i agent"

echo ""
echo "5. Check Database Connection"
echo "psql \$DATABASE_URL -c 'SELECT COUNT(*) as agent_count FROM agents;'"

echo ""
echo "6. Check PostgreSQL Service"
echo "sudo systemctl status postgresql"

echo ""
echo "=========================================="
echo "Questions to Answer:"
echo "=========================================="
echo ""
echo "When you try to create an agent:"
echo "1. What exact error message appears in the admin UI?"
echo "2. What does the browser console show (F12 -> Console)?"
echo "3. What does the Network tab show for /api/admin/agents request?"
echo "4. What does 'sudo tail -50 /var/log/api/satsremit.log | grep -i agent' show?"
echo ""
