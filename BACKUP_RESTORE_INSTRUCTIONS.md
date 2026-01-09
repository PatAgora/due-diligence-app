# 🔒 APPLICATION BACKUP & RESTORE INSTRUCTIONS

**Backup Tag:** `v1.0-demo-backup`  
**Backup Date:** 2026-01-09 13:30 UTC  
**Commit Hash:** 38da275  
**Repository:** https://github.com/PatAgora/due-diligence-app  

---

## ✅ **BACKUP CONFIRMATION**

This backup has been successfully created and pushed to GitHub. It includes:

### **Complete Application State:**
- ✅ Frontend code (React/Vite)
- ✅ Backend code (Flask API)
- ✅ AI SME service code
- ✅ Database with all data (scrutinise_workflow.db)
- ✅ Configuration files (PM2, ecosystem.config.cjs)
- ✅ All documentation files
- ✅ Git history and commits

### **Application Features Working:**
- ✅ QC Pass % displaying as 67% (no decimals)
- ✅ 6 test submissions (5 Completed, 1 QC Waiting Assignment)
- ✅ 3 QC results (2 Pass, 1 Fail)
- ✅ All outcomes set to "Retain"
- ✅ AI Outreach with new questions (old stock questions removed)
- ✅ CUST2002 cleared and ready for demo
- ✅ Operations Dashboard QC status fix applied
- ✅ Alerts Over Time graph with monthly grouping
- ✅ Transaction Review fully functional

---

## 🔄 **HOW TO RESTORE THIS BACKUP**

If you need to revert to this exact working state, follow these steps:

### **Option 1: Full Restore (Recommended)**

```bash
# 1. Navigate to project directory
cd /home/user/webapp

# 2. Fetch all tags from GitHub
git fetch --tags

# 3. Checkout the backup tag
git checkout v1.0-demo-backup

# 4. Verify you're on the backup
git describe --tags
# Should show: v1.0-demo-backup

# 5. Restart services
pm2 restart all

# 6. Verify services are running
pm2 list
curl http://localhost:5050/login
curl http://localhost:5173
```

### **Option 2: Create New Branch from Backup**

If you want to keep your current work but test the backup:

```bash
# 1. Create new branch from backup tag
cd /home/user/webapp
git fetch --tags
git checkout -b backup-restore v1.0-demo-backup

# 2. Restart services
pm2 restart all

# 3. Test the backup
# Open frontend URL and verify functionality

# 4. To go back to main
git checkout main
pm2 restart all
```

### **Option 3: Hard Reset to Backup (Discard All Changes)**

⚠️ **WARNING:** This will DELETE all changes made after the backup!

```bash
# 1. Navigate to project
cd /home/user/webapp

# 2. Fetch backup tag
git fetch --tags

# 3. Hard reset to backup (DESTRUCTIVE!)
git reset --hard v1.0-demo-backup

# 4. Force push to update remote (if needed)
git push origin main --force

# 5. Restart services
pm2 restart all
```

---

## 📋 **VERIFICATION CHECKLIST**

After restoring, verify these features are working:

### **Frontend (Port 5173)**
- [ ] Login page loads
- [ ] Dashboard displays correctly
- [ ] My Tasks shows 6 submissions
- [ ] QC Pass % shows as 67%
- [ ] Quality Stats tile shows data (2 Pass, 1 Fail)

### **Backend (Port 5050)**
- [ ] API responds to /login
- [ ] Database queries work
- [ ] Transaction Review loads

### **Database State**
- [ ] 6 submissions present (IDs: 125, 145, 146, 147, 148, 149)
- [ ] 5 Completed status (CUST3001-CUST3005)
- [ ] 1 QC Waiting Assignment (CUST2001)
- [ ] All outcomes = "Retain"
- [ ] 3 QC results: ID 149 Pass, ID 148 Pass, ID 147 Fail

### **AI Outreach**
- [ ] CUST2002 shows "No case yet - click Prepare Questions"
- [ ] No old stock questions visible
- [ ] Clicking "Prepare Questions" generates 3 new questions

### **Operations Dashboard**
- [ ] CUST2001 shows as "QC – Awaiting Assignment"
- [ ] Not showing as "Completed"

### **Alerts Over Time Graph**
- [ ] Monthly grouping (not daily)
- [ ] Integer values only (no decimals)
- [ ] CUST2002 shows 2 data points [1, 3]

---

## 🗂️ **WHAT'S INCLUDED IN BACKUP**

```
webapp/
├── DueDiligenceBackend/
│   ├── Due Diligence/
│   │   ├── app.py                          # Main Flask API
│   │   ├── scrutinise_workflow.db          # Complete database with all data
│   │   ├── scrutinise_workflow.db-shm      # Database shared memory
│   │   ├── scrutinise_workflow.db-wal      # Database write-ahead log
│   │   └── utils.py                        # Status mapping functions
│   └── AI SME/
│       ├── app.py                          # AI SME service
│       ├── data/                           # AI feedback/referrals
│       └── chroma/                         # Vector database
├── DueDiligenceFrontend/
│   ├── src/
│   │   └── components/
│   │       ├── ReviewerDashboard.jsx       # QC Pass % display (0 decimals)
│   │       ├── TransactionDashboard.jsx    # Alerts Over Time (monthly)
│   │       ├── TransactionAI.jsx           # AI Outreach (no old questions)
│   │       └── ... (all other components)
│   ├── package.json
│   └── vite.config.js
├── ecosystem.config.cjs                     # PM2 configuration
├── .gitignore
├── package.json
└── Documentation/
    ├── OPS_DASHBOARD_QC_STATUS_FIX.md
    ├── TEST_DATA_OUTCOMES_UPDATE.md
    ├── ALERTS_OVER_TIME_GRAPH_ASSESSMENT.md
    ├── OLD_QUESTIONS_CLEANUP.md
    ├── PROPOSED_QUESTIONS_FIX.md
    ├── QC_RESULTS_DEMO_UPDATE.md
    └── BACKUP_RESTORE_INSTRUCTIONS.md (this file)
```

---

## 🔍 **BACKUP DETAILS**

### **Git Information**
- **Tag Name:** v1.0-demo-backup
- **Commit Hash:** 38da275
- **Branch:** main
- **Repository URL:** https://github.com/PatAgora/due-diligence-app.git

### **How to View Backup on GitHub**
1. Go to: https://github.com/PatAgora/due-diligence-app
2. Click "Tags" (or "Releases")
3. Find tag: `v1.0-demo-backup`
4. Click to view snapshot at that point in time

### **How to Download Backup as ZIP**
```
https://github.com/PatAgora/due-diligence-app/archive/refs/tags/v1.0-demo-backup.zip
```

---

## 🛠️ **TROUBLESHOOTING RESTORE**

### **Problem: "Tag not found"**
```bash
# Solution: Fetch tags first
git fetch --tags
git tag -l  # List all tags to verify
```

### **Problem: Services won't start after restore**
```bash
# Solution: Reinstall dependencies
cd /home/user/webapp/DueDiligenceFrontend
npm install

cd /home/user/webapp/DueDiligenceBackend/Due\ Diligence
pip install -r requirements.txt

# Then restart
pm2 restart all
```

### **Problem: Database changes lost**
```bash
# Solution: Database is included in Git
# After checkout, the .db file should be restored
ls -lh DueDiligenceBackend/Due\ Diligence/scrutinise_workflow.db

# If missing, the backup tag includes it
git checkout v1.0-demo-backup -- DueDiligenceBackend/Due\ Diligence/scrutinise_workflow.db
```

### **Problem: Port conflicts**
```bash
# Solution: Kill existing processes
fuser -k 5173/tcp  # Frontend
fuser -k 5050/tcp  # Backend
pm2 delete all
pm2 start ecosystem.config.cjs
```

---

## 📊 **DATABASE SNAPSHOT SUMMARY**

The backup includes the complete database with:

### **Reviews Table (6 records)**
| ID  | Customer  | Status                | Outcome | QC Result | Completed Date      |
|-----|-----------|----------------------|---------|-----------|---------------------|
| 125 | CUST2001  | QC Waiting Assignment| Retain  | -         | 2026-01-08 21:24:36 |
| 145 | CUST3001  | Completed            | Retain  | -         | 2026-01-05 14:30:00 |
| 146 | CUST3002  | Completed            | Retain  | -         | 2026-01-06 10:15:00 |
| 147 | CUST3003  | Completed            | Retain  | Fail      | 2026-01-07 16:45:00 |
| 148 | CUST3004  | Completed            | Retain  | Pass      | 2026-01-08 11:20:00 |
| 149 | CUST3005  | Completed            | Retain  | Pass      | 2026-01-09 09:30:00 |

### **AI Cases Table (0 records)**
- CUST2002 cleared for demo
- All old stock questions removed

### **QC Statistics**
- Total QC Checked: 3
- Pass: 2 (67%)
- Fail: 1 (33%)

---

## 🎯 **USE CASES FOR THIS BACKUP**

### **1. Rollback After Bad Changes**
If new changes break the application, restore this backup immediately.

### **2. Demo Reset**
Before each demo, restore to ensure consistent state.

### **3. Testing New Features**
Create a branch from this backup to test changes safely.

### **4. Reference Point**
Compare current state to this backup to see what changed.

### **5. Emergency Recovery**
If database gets corrupted, restore from this backup.

---

## ⚠️ **IMPORTANT NOTES**

1. **This backup is immutable** - The tag `v1.0-demo-backup` will never change
2. **Database included** - The .db file is part of the Git repository
3. **All dependencies included** - package.json files specify exact versions
4. **Services configuration included** - PM2 ecosystem.config.cjs is backed up
5. **Documentation included** - All .md files are part of the backup

---

## ✅ **BACKUP STATUS**

- ✅ **Committed to Git:** Yes (commit 38da275)
- ✅ **Tagged:** Yes (v1.0-demo-backup)
- ✅ **Pushed to GitHub:** Yes
- ✅ **Verified:** Yes
- ✅ **Documented:** Yes (this file)

**GitHub URL:** https://github.com/PatAgora/due-diligence-app/tree/v1.0-demo-backup

---

## 🆘 **QUICK RESTORE COMMAND**

For emergency restore, run this single command:

```bash
cd /home/user/webapp && git fetch --tags && git checkout v1.0-demo-backup && pm2 restart all && echo "✅ Backup restored!"
```

---

**Created:** 2026-01-09  
**Author:** AI Assistant  
**Purpose:** Complete application backup before making new changes  
**Status:** ACTIVE BACKUP - SAFE TO RESTORE ANYTIME
