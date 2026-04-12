# SatsRemit Production Configuration

This directory contains production configuration files for deploying SatsRemit on https://satsremit.com

## Environment Configuration

### .env file (Production)

```bash
# Core
DEBUG=false
ENVIRONMENT=production

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Database
DATABASE_URL=postgresql://satsremit:secure_password@db.satsremit.com:5432/satsremit_prod
DATABASE_ECHO=false

# Redis
REDIS_URL=redis://:secure_password@redis.satsremit.com:6379/0
CELERY_BROKER_URL=redis://:secure_password@redis.satsremit.com:6379/0
CELERY_RESULT_BACKEND=redis://:secure_password@redis.satsremit.com:6379/1

# LND (Lightning Network Daemon)
LND_REST_URL=https://lnd.satsremit.com:8080
LND_MACAROON_PATH=/etc/satsremit/admin.macaroon
LND_CERT_PATH=/etc/satsremit/tls.cert
LND_HOLD_INVOICE_EXPIRY_MINUTES=5760
LND_INVOICE_TIMEOUT_HOURS=6.5

# Bitcoin
BITCOIN_NETWORK=mainnet
BITCOIN_RPC_URL=https://bitcoin.satsremit.com:28332
BITCOIN_RPC_USER=bitcoin
BITCOIN_RPC_PASSWORD=secure_password

# Platform Configuration
PLATFORM_FEE_PERCENT=0.5
AGENT_COMMISSION_PERCENT=0.5

# JWT & Security
JWT_SECRET_KEY=your-secure-jwt-secret-key-min-32-chars-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Webhooks
WEBHOOK_SECRET=your-secure-webhook-secret-min-16-chars-production

# Notifications (WhatsApp)
WHATSAPP_BUSINESS_ACCOUNT_ID=your_account_id
WHATSAPP_BUSINESS_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_BUSINESS_ACCESS_TOKEN=your_access_token

# Rate Source
RATE_SOURCE=coingecko
RATE_CACHE_MINUTES=5
```

## Nginx Configuration

Create `/etc/nginx/sites-available/satsremit.com`:

```nginx
# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name satsremit.com www.satsremit.com app.satsremit.com admin.satsremit.com agent.satsremit.com receiver.satsremit.com;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name satsremit.com www.satsremit.com app.satsremit.com admin.satsremit.com agent.satsremit.com receiver.satsremit.com;

    # SSL Certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/satsremit.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/satsremit.com/privkey.pem;
    
    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Gzip compression
    gzip on;
    gzip_types text/plain text/css text/javascript application/json application/javascript;
    gzip_min_length 1000;
    gzip_vary on;
    
    # Root location - redirect to /app
    location = / {
        return 301 https://$server_name/app;
    }
    
    # API proxy - all /api requests go to FastAPI backend
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8000;
        access_log off;
    }
    
    # Static files caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Dashboard applications - serve with no cache headers
    location /admin {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # No cache for HTML
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }
    
    location /app {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }
    
    location /agent {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }
    
    location /receiver {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }
    
    location /platform-guide.html {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }
    
    # Catch-all for other requests
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Deployment Steps

### 1. Install Dependencies
```bash
apt-get update
apt-get install -y python3-pip python3-venv nginx certbot python3-certbot-nginx postgresql postgresql-contrib redis-server
```

### 2. Setup SSL Certificate (Let's Encrypt)
```bash
certbot certonly --standalone \
  -d satsremit.com \
  -d www.satsremit.com \
  -d app.satsremit.com \
  -d admin.satsremit.com \
  -d agent.satsremit.com \
  -d receiver.satsremit.com \
  --email admin@satsremit.com \
  --agree-tos
```

### 3. Install SatsRemit
```bash
cd /opt/satsremit
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Setup Database
```bash
createuser satsremit
createdb satsremit_prod -O satsremit
python3 -m alembic upgrade head
```

### 5. Configure Nginx
```bash
cp nginx.conf /etc/nginx/sites-available/satsremit.com
ln -s /etc/nginx/sites-available/satsremit.com /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### 6. Setup Systemd Service
Create `/etc/systemd/system/satsremit.service`:

```ini
[Unit]
Description=SatsRemit Application
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=satsremit
WorkingDirectory=/opt/satsremit
Environment="PATH=/opt/satsremit/venv/bin"
EnvironmentFile=/etc/satsremit/.env
ExecStart=/opt/satsremit/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
systemctl daemon-reload
systemctl enable satsremit
systemctl start satsremit
```

### 7. Setup Celery Workers (Optional)
```bash
# In another terminal or separate systemd service
source venv/bin/activate
celery -A src.core.celery worker --loglevel=info
```

### 8. Setup Celery Beat Scheduler (Optional)
```bash
source venv/bin/activate
celery -A src.core.celery beat --loglevel=info
```

## Monitoring and Logs

### Check Application Status
```bash
systemctl status satsremit
journalctl -u satsremit -f  # Follow logs
```

### Check Nginx Status
```bash
systemctl status nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

## Dashboard URLs

After deployment, all dashboards will be accessible at:

- **Main Site:** https://satsremit.com (redirects to /app)
- **User App:** https://satsremit.com/app
- **Admin Panel:** https://satsremit.com/admin
- **Agent Dashboard:** https://satsremit.com/agent
- **Receiver Portal:** https://satsremit.com/receiver
- **Platform Guide:** https://satsremit.com/platform-guide.html
- **API Documentation:** https://satsremit.com/api/docs
- **API Health:** https://satsremit.com/health

## Alternative: Subdomain-based Access

For better isolation, use separate subdomains:

```
https://app.satsremit.com      - User App
https://admin.satsremit.com    - Admin Panel
https://agent.satsremit.com    - Agent Dashboard
https://receiver.satsremit.com - Receiver Portal
https://api.satsremit.com      - API Endpoint
```

Just update DNS and Nginx configuration accordingly.

## Security Checklist

- ✅ SSL/TLS enabled (HTTPS only)
- ✅ CORS configured for allowed domains
- ✅ Trusted hosts validated
- ✅ Security headers configured
- ✅ Database credentials secured
- ✅ JWT secrets strong (32+ characters)
- ✅ Rate limiting enabled (if configured)
- ✅ Logging enabled for auditing
- ✅ Database backups scheduled
- ✅ Regular security updates

## Troubleshooting

### Dashboards Not Loading
1. Check nginx is running: `systemctl status nginx`
2. Check FastAPI is running: `systemctl status satsremit`
3. Check logs: `journalctl -u satsremit -f`
4. Verify domain DNS: `nslookup satsremit.com`

### SSL Certificate Issues
1. Renew certificate: `certbot renew`
2. Check certificate: `certbot certificates`
3. Auto-renewal: `systemctl enable certbot.timer`

### API Connection Issues
1. Verify CORS: Check FastAPI CORS configuration in `src/main.py`
2. Check API headers: Verify `X-Forwarded-Proto` and `X-Forwarded-For`
3. Test endpoint: `curl -v https://satsremit.com/api/health`
