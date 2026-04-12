# Satsremit Deployment Guide

## Quick Start: One-Command Deploy

```bash
cd /home/satsinaction/satsremit
./deploy.sh
```

That's it! The script handles everything.

---

## What the Deploy Script Does

The `deploy.sh` script automates the entire deployment workflow in 5 steps:

### **Step 1: Local Repository Check**
- Verifies you're in a git repository
- Prepares for deployment

### **Step 2: Local Changes**
- Detects uncommitted changes
- Prompts you to commit them (or skip if none)
- Requires a commit message for traceability

### **Step 3: GitHub Push**
- Pushes committed changes to GitHub
- All changes backed up on GitHub after this step

### **Step 4: VPS Deployment**
- Connects to VPS: `ubuntu@vm-1327.lnvps.cloud`
- Initializes git repo on VPS (if needed, first deploy only)
- Pulls latest code from GitHub
- Updates all static files

### **Step 5: Service Restart**
- Optional: Asks if you want to restart Uvicorn
- Restarts the web server so changes take effect immediately

---

## Workflow

### **Making Changes Locally**

1. **Edit files** in `/home/satsinaction/satsremit`
   ```bash
   nano src/api/routes/public.py      # Edit backend
   nano static/app/js/app.js
   # Edit frontend
   ```

2. **Test locally** (optional)
   ```bash
   cd /home/satsinaction/satsremit
   python3 -m pytest tests/
   ```

3. **Deploy to production**
   ```bash
   ./deploy.sh
   ```

4. **Choose what to do:**
   - Commit changes? **Yes** → enter message
   - Restart services? **Yes** for immediate effect

---

## Example Deployments

### **Deploy Frontend Changes Only**

```bash
cd /home/satsinaction/satsremit

# Edit the quote calculation
nano static/app/js/app.js

# Deploy
./deploy.sh
# → Commit message: "Fix quote calculation UI"
# → Restart? Yes
```

### **Deploy Backend Changes**

```bash
cd /home/satsinaction/satsremit

# Update agent validation
nano src/api/routes/admin.py

# Deploy
./deploy.sh
# → Commit message: "Add agent balance validation"
# → Restart? Yes  (required for Python changes)
```

### **Deploy Multiple Files**

```bash
cd /home/satsinaction/satsremit

# Edit multiple files
nano src/services/rate.py
nano static/app/js/app.js
nano static/app/index.html

# Deploy all at once
./deploy.sh
# → Commit message: "Update rate service and quote display"
# → Restart? Yes
```

---

## Git Workflow Details

### **Before Deployment**

```
LOCAL MACHINE
    ├── static/app/js/app.js      (modified)
    ├── src/services/rate.py      (modified)
    └── .git                       (tracks changes)
```

### **After Running `./deploy.sh`**

```
GITHUB
    └── Latest commit: "Fix quote calculation UI"

LOCAL MACHINE                      VPS PRODUCTION
    ├── static/app/js/app.js  ←→  /opt/satsremit/static/app/js/app.js
    ├── src/services/rate.py  ←→  /opt/satsremit/src/services/rate.py
    └── .git                  ←→  /opt/satsremit/.git
```

---

## Troubleshooting

### **"Not a git repository"**
```bash
# You're not in the right directory
cd /home/satsinaction/satsremit
./deploy.sh
```

### **"Cannot connect to VPS"**
```bash
# Check VPS is running
ssh ubuntu@vm-1327.lnvps.cloud "echo 'VPS OK'"

# If that fails, check your SSH key is configured
ssh-add ~/.ssh/id_rsa  # or your key path
```

### **"Failed to push to GitHub"**
```bash
# Check GitHub credentials
git remote -v  # Should show: https://github.com/bstreetwise/satsremit.git

# Try pushing manually
git push origin main

# If auth fails, update credentials or use SSH key
```

### **"Services failed to restart"**
```bash
# Check if service is running on VPS
ssh ubuntu@vm-1327.lnvps.cloud "ps aux | grep uvicorn"

# Manually restart if needed
ssh ubuntu@vm-1327.lnvps.cloud "pkill -f uvicorn; sleep 1; cd /opt/satsremit && nohup ./venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2 > /tmp/uvicorn.log 2>&1 &"
```

---

## Advanced: Manual Steps (if script doesn't work)

### **1. Commit Locally**
```bash
cd /home/satsinaction/satsremit
git add -A
git commit -m "Your commit message"
```

### **2. Push to GitHub**
```bash
git push origin main
```

### **3. Deploy on VPS**
```bash
ssh ubuntu@vm-1327.lnvps.cloud << 'EOF'
  cd /opt/satsremit
  git pull origin main
EOF
```

### **4. Restart Services**
```bash
ssh ubuntu@vm-1327.lnvps.cloud "\
  pkill -f 'uvicorn.*satsremit' || true && \
  sleep 1 && \
  cd /opt/satsremit && \
  nohup ./venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2 > /tmp/uvicorn.log 2>&1 &"
```

---

## Architecture After Setup

```
┌─────────────────────┐
│  LOCAL MACHINE      │  ← You edit files here
│  (satsinaction)     │  ← Run: ./deploy.sh
└──────────┬──────────┘
           │ git push
           ↓
┌─────────────────────┐
│  GITHUB             │  ← Backup of all code
│  (bstreetwise/...)  │  ← Single source of truth
└──────────┬──────────┘
           │ git pull
           ↓
┌─────────────────────┐
│  VPS PRODUCTION     │  ← Running at satsremit.com
│  (vm-1327.lnvps)    │  ← Database + Bitcoin node
└─────────────────────┘
```

---

## Tips

✅ **Always run deploy.sh before making more changes** - ensures VPS is in sync  
✅ **Write clear commit messages** - helps track what changed  
✅ **Test locally first** - prevents broken deployments  
✅ **Check git log after deploy** - verify changes are deployed

```bash
# See what's deployed
git log --oneline -5

# See what's on VPS
ssh ubuntu@vm-1327.lnvps.cloud "cd /opt/satsremit && git log --oneline -5"
```

---

## Next Steps

1. **Test the script**: `./deploy.sh` (with no changes - it should skip commit)
2. **Make a test change**: `echo "# test" >> README.md`
3. **Deploy**: `./deploy.sh`
4. **Verify**: Check https://satsremit.com works

That's it! You now have automated one-command deployments. 🚀
