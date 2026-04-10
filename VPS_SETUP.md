# VPS Setup Guide

## Quick Start

```bash
# SSH to VPS
ssh ubuntu@185.18.221.10

# Navigate to project
cd /home/ubuntu/satsremit

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install email-validator

# Install system dependencies (for bcrypt)
sudo apt-get update
sudo apt-get install -y build-essential libffi-dev python3-dev libssl-dev

# Start PostgreSQL
sudo service postgresql start

# Create database user
sudo -u postgres createuser satsremit -s
sudo -u postgres psql -c "ALTER USER satsremit WITH PASSWORD 'satsremit_pass'"
sudo -u postgres createdb satsremit_test -O satsremit
```

## Environment Variables

Create `.env` file:
```
DATABASE_URL=postgresql://satsremit:satsremit_pass@localhost:5432/satsremit_test
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-secret-key
WEBHOOK_SECRET=your-webhook-secret
```

## Run Tests

```bash
export PYTHONPATH=/home/ubuntu/satsremit
export DATABASE_URL=postgresql://satsremit:satsremit_pass@localhost:5432/satsremit_test
pytest -v
```

## Manual Security Feature Tests

```python
# Webhook HMAC
import hmac, hashlib
from src.core.security import verify_webhook_hmac
sig = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
verify_webhook_hmac(body, sig)

# PIN Brute-Force Protection
from src.core.security import track_failed_pin_attempt
track_failed_pin_attempt('transfer-id', max_attempts=5, lockout_minutes=30)

# Rate Limiting (IP + phone)
from src.core.security import check_rate_limit
check_rate_limit('1.1.1.1', '+27831234567', max_requests=5, window_minutes=60)
```

## Troubleshooting

- "Module not found: src" → `export PYTHONPATH=/home/ubuntu/satsremit`
- bcrypt issues → `sudo apt-get install -y build-essential libffi-dev python3-dev libssl-dev`
- DB errors → `sudo service postgresql start`
