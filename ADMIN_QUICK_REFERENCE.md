# Admin Dashboard - Quick Reference Guide

## 🚀 Quick Start

**URL:** `http://localhost:8000/admin`

---

## 📊 Dashboard Sections Overview

### 1. Dashboard (Default View)
```
✓ Daily Volume:      Shows today's transaction volume in ZAR
✓ Weekly Volume:     Shows this week's transaction volume
✓ Monthly Volume:    Shows this month's transaction volume
✓ Fees Collected:    Platform earnings in sats
✓ Active Agents:     Total active agents on platform
✓ Pending Settlements: Open settlement records awaiting confirmation
✓ Platform Earnings:  Total sats earned by platform
✓ Agent Earnings:     Total sats earned by all agents
```
**Auto-refresh:** Every 30 seconds  
**Update:** Click "Dashboard" in sidebar to manual refresh

---

### 2. Agent Management
```
✓ List all agents with:
  - Name
  - Phone number
  - Location
  - Cash balance (ZAR)
  - Commission earned (sats)
  - Current status

✓ Add New Agent:
  1. Click "Add New Agent" button
  2. Fill in agent details
  3. Set initial cash amount (minimum 100 ZAR)
  4. Click "Create Agent"

✓ View Agent Details:
  - Click "View" button next to any agent
  - See full agent information
```

---

### 3. Transfer History
```
✓ List all transactions with filters:
  - Reference ID
  - Amount (both ZAR and sats)
  - Agent who processed
  - Current state
  - Date/time

✓ Filter by state:
  - INITIATED: Transfer created
  - PAID: Payment received
  - SETTLED: Agent settled
  - RECEIVER_VERIFIED: Beneficiary verified
  - PAYOUT_EXECUTED: Cash delivered

✓ Search:
  - Type transfer reference to find specific transaction

✓ Pagination:
  - 20 transfers per page
  - Use Previous/Next buttons

✓ View Details:
  - Click "Details" button for full transfer info
```

---

### 4. Settlement Records
```
✓ View all settlements:
  - Settlement ID
  - Agent name
  - Settlement period
  - Amount due (ZAR)
  - Current status
  - Due date

✓ Confirm Settlement:
  - Click "Confirm" button
  - Confirms settlement and processes payment
```

---

### 5. Analytics & Insights
```
✓ Performance Metrics:
  - Total Transfers: Cumulative transfer count
  - Total Volume: Combined transaction volume
  - Average Transfer: Mean transaction size
  - Success Rate: Percentage of successful transfers

✓ Top Agents Ranking:
  - Rank (1-5)
  - Agent name
  - Number of transfers
  - Volume processed
  - Commission earned
```

---

## 🔗 External Dashboard Links (Sidebar)

| Link | Purpose | Users |
|------|---------|-------|
| **Send Money** | User transfer interface | Senders |
| **Agent Dashboard** | Agent operations portal | Agents |
| **Receiver Portal** | Beneficiary verification | Recipients |
| **Platform Guide** | Help and documentation | Everyone |

---

## ⚙️ How to Navigate

### Using Sidebar
1. Click any section name in the left sidebar
2. Content loads automatically
3. Active section is highlighted
4. Page title updates accordingly

### Within Sections
- **Tables:** Click action buttons (View, Details, Confirm)
- **Modals:** Fill forms and click submit or cancel
- **Filters:** Use dropdowns and search boxes
- **Pagination:** Click Previous/Next for more data

### External Navigation
- Click any link to open new dashboard
- Browse external platform features
- Return to admin panel using browser back button or direct URL

---

## 💡 Tips & Tricks

### Dashboard Metrics
- Metrics update automatically every 30 seconds
- Manual refresh: Click "Dashboard" again
- Metrics show ZAR for currency amounts, sats for earnings

### Agent Management
- Minimum initial cash: 100 ZAR
- Phone format: International (+263...)
- Locations: Harare, Bulawayo, Mutare, Kwekwe
- Commission shown in sats earned

### Transfer Search
- Search by reference ID only
- Filter by state in dropdown
- Use pagination for large datasets
- State filters combine multiple categories

### Settlement Workflow
1. Review settlement amount
2. Check due date
3. Click "Confirm" to process
4. Status updates automatically

### Analytics
- Total figures calculated from all data
- Rankings based on transfer volume
- Success rate estimated at 98%
- Top 5 agents displayed

---

## 🔑 Important Fields

### Agent Fields
- **Phone:** Agent's contact number (required)
- **Name:** Agent's full name (required)
- **Location:** Service area (required)
- **Cash Balance:** Operating cash (ZAR)
- **Commission:** Earnings in sats

### Transfer Fields
- **Reference:** Unique transaction ID
- **Amount ZAR:** Transfer amount in South African Rand
- **Amount sats:** Equivalent in Bitcoin satoshis
- **State:** Current transaction status
- **Date:** When transfer was created

### Settlement Fields
- **Settlement ID:** Unique settlement record
- **Period:** Settlement billing cycle
- **Amount:** Total settlement due
- **Status:** Pending, Confirmed, Paid
- **Due Date:** Payment deadline

---

## ⚡ Keyboard Shortcuts

| Keyboard | Action |
|----------|--------|
| `D` | Jump to Dashboard |
| `A` | Jump to Agents |
| `T` | Jump to Transfers |
| `S` | Jump to Settlements |
| `I` | Jump to Analytics |
| `L` | Logout |
| `ESC` | Close modal |
| `CTRL+R` | Refresh page |

---

## 🆘 Troubleshooting

### Dashboard Not Loading
- Check internet connection
- Clear browser cache (Ctrl+Shift+Delete)
- Refresh page (Ctrl+R)
- Check browser console for errors

### Section Not Appearing
- Click sidebar link again
- Refresh page
- Check if data is loading in background

### Tables Show "No Data"
- Verify backend is running
- Check API connectivity
- Ensure database has data
- Wait for auto-refresh (30 sec)

### Modal Won't Close
- Click X button or Cancel
- Press ESC key
- Click outside modal area

### Styling Issues
- Clear CSS cache (Ctrl+Shift+Delete)
- Refresh page (Ctrl+F5)
- Try different browser
- Disable browser extensions

---

## 📱 Mobile Support

Admin panel is responsive and works on:
- Desktop (1920x1080+)
- Tablet (768px+)
- Mobile (320px+)

On mobile:
- Sidebar collapses to hamburger menu
- Tables scroll horizontally
- Touch-friendly buttons
- Optimized layout

---

## 🔒 Security Notes

- Your session token is stored locally
- Don't share your login credentials
- Logout when done to clear session
- Use HTTPS in production
- Never share admin URLs with unauthorized users

---

## 📞 Support

### For Technical Issues
1. Check browser console (F12)
2. Review Network tab for failed requests
3. Check backend logs
4. Verify API connectivity

### For Data Issues
1. Verify database connection
2. Check backend services
3. Ensure sufficient data exists
4. Check API response time

---

## 📚 Complete Feature List

| Feature | Status |
|---------|--------|
| Dashboard metrics | ✅ Active |
| Agent listing | ✅ Active |
| Agent creation | ✅ Active |
| Agent details | ✅ Active |
| Transfer listing | ✅ Active |
| Transfer filtering | ✅ Active |
| Transfer search | ✅ Active |
| Transfer details | ✅ Active |
| Settlement listing | ✅ Active |
| Settlement confirmation | ✅ Active |
| Analytics dashboard | ✅ Active |
| Top agents ranking | ✅ Active |
| External dashboard links | ✅ Active |
| Responsive design | ✅ Active |
| Auto-refresh | ✅ Active |
| Form validation | ✅ Active |
| Error handling | ✅ Active |
| User feedback alerts | ✅ Active |

---

## 🎯 Common Workflows

### Creating and Managing an Agent
```
1. Go to Admin Panel → Agents
2. Click "Add New Agent"
3. Enter:
   - Phone: +263712345678
   - Name: John Doe
   - Location: Harare
   - Initial Cash: 2000 ZAR
4. Click "Create Agent"
5. Agent appears in table
6. Click "View" to see details
```

### Processing a Settlement
```
1. Go to Admin Panel → Settlements
2. Review settlement record
3. Check amount and due date
4. Click "Confirm" button
5. Settlement status updates
6. Payment processed
```

### Analyzing Platform Performance
```
1. Go to Admin Panel → Analytics
2. View performance metrics:
   - Total transfers
   - Volume
   - Average transfer
   - Success rate
3. Review top agents ranking
4. Identify top performers
```

### Monitoring Daily Activity
```
1. Go to Admin Panel (Dashboard)
2. Review daily metrics
3. Check active agents count
4. Review pending settlements
5. Check earnings (platform & agents)
6. Auto-refreshes every 30 seconds
```

---

## 📊 Data Formats

### Currency Display
- **ZAR:** South African Rand (e.g., ZAR 1,234.56)
- **Sats:** Bitcoin satoshis (e.g., 54,321 sats)

### Date/Time Display
- Format: `DD MMM YYYY HH:MM`
- Example: `11 Apr 2026 18:05`

### Status Badges
- Color-coded for quick identification
- Hover for full status text
- Updated in real-time

---

## 🔄 Refresh Behavior

- **Dashboard:** Auto-refresh every 30 seconds
- **Agents:** Manual refresh when updated
- **Transfers:** Manual refresh when filtered
- **Settlements:** Manual refresh when confirmed
- **Analytics:** Updates with dashboard refresh

---

**Last Updated:** April 11, 2026  
**Version:** 1.0  
**Status:** ✅ Complete
