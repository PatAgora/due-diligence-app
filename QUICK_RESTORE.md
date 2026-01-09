# 🆘 QUICK BACKUP RESTORE - EMERGENCY GUIDE

**⚠️ USE THIS IF YOU NEED TO RESTORE THE WORKING BACKUP IMMEDIATELY**

---

## 🚀 ONE-LINE EMERGENCY RESTORE

Copy and paste this command:

```bash
cd /home/user/webapp && git fetch --tags && git checkout v1.0-demo-backup && pm2 restart all && echo "✅ Backup restored!"
```

---

## 📋 STEP-BY-STEP RESTORE (If one-line fails)

```bash
# 1. Go to project
cd /home/user/webapp

# 2. Get backup tag from GitHub
git fetch --tags

# 3. Switch to backup
git checkout v1.0-demo-backup

# 4. Restart all services
pm2 restart all

# 5. Check services are running
pm2 list
```

---

## ✅ WHAT THIS BACKUP INCLUDES

- ✅ Complete working application
- ✅ All frontend & backend code
- ✅ Database with demo data (6 submissions, 3 QC results)
- ✅ All features working correctly
- ✅ QC Pass % at 67%
- ✅ AI Outreach working
- ✅ Operations Dashboard fixed
- ✅ Transaction Review working

---

## 🔍 VERIFY RESTORE WORKED

After restore, check:

1. **Services running:**
   ```bash
   pm2 list
   # Should show: flask-backend (online), ai-sme (online)
   ```

2. **Frontend accessible:**
   ```
   https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai
   ```

3. **Backend responding:**
   ```bash
   curl http://localhost:5050/login
   # Should return login page HTML
   ```

---

## 🌐 GITHUB LINKS

- **Repository:** https://github.com/PatAgora/due-diligence-app
- **Backup Tag:** https://github.com/PatAgora/due-diligence-app/releases/tag/v1.0-demo-backup
- **Download ZIP:** https://github.com/PatAgora/due-diligence-app/archive/refs/tags/v1.0-demo-backup.zip

---

## 📝 BACKUP INFO

- **Tag Name:** v1.0-demo-backup
- **Commit:** 38da275
- **Date:** 2026-01-09 13:30 UTC
- **Status:** PRODUCTION READY ✅

---

## 🔄 GO BACK TO LATEST

If you want to go back to the latest code after testing the backup:

```bash
cd /home/user/webapp
git checkout main
pm2 restart all
```

---

**For full instructions, see:** BACKUP_RESTORE_INSTRUCTIONS.md
