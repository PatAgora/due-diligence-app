# Scrutinise Due Diligence System - Login Credentials

## 🌐 Application URLs

### Frontend (Main Application)
**URL**: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

### Backend API
**URL**: https://5050-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## 👥 Test User Accounts

### 1. Admin Account
**Role**: System Administrator  
**Email**: `admin@scrutinise.co.uk`  
**Password**: `admin123`  
**Dashboard**: `/list_users`  
**Permissions**: Full system access, user management, all dashboards

---

### 2. Operations Manager
**Role**: Operations Manager  
**Email**: `ops@scrutinise.co.uk`  
**Password**: `ops123`  
**Dashboard**: `/operations_dashboard`  
**Permissions**: View all operations, manage workflows, assign tasks

---

### 3. Team Leader (Level 1) - PRIMARY
**Role**: Team Leader Level 1  
**Email**: `TeamLead@scrutinise.co.uk`  
**Password**: `teamlead123`  
**Dashboard**: `/team_leader_dashboard`  
**Permissions**: Manage team tasks, view team performance, assign reviewers

**Note**: This is the main Team Leader Level 1 account (no level displayed in UI)

---

### 4. Team Leader (Level 2) - ALTERNATE
**Role**: Team Leader Level 2  
**Email**: `teamlead@scrutinise.co.uk`  
**Password**: `teamlead123`  
**Name**: TLTestL2  
**Dashboard**: `/team_leader_dashboard`  
**Permissions**: Same as Level 1, different access level in backend

---

### 5. Team Leader - Additional Accounts

#### TL Account 3
**Email**: `RevTL2@scrutinise.co.uk`  
**Password**: `teamlead123` (default)  
**Role**: team_lead_2  
**Level**: 2

#### TL Account 4
**Email**: `faizanmukhtar96@gmail.com`  
**Password**: `teamlead123` (default)  
**Role**: team_lead_1  
**Level**: 1

---

### 6. QC Team Lead
**Role**: QC Team Lead  
**Email**: `qctl@scrutinise.co.uk`  
**Password**: `qctl123`  
**Dashboard**: `/qc_lead_dashboard`  
**Permissions**: Oversee QC process, manage QC reviewers, quality metrics

---

### 7. QC Reviewer
**Role**: QC Reviewer  
**Email**: `QC1@scrutinise.co.uk`  
**Password**: `qc123`  
**Dashboard**: `/qc_dashboard`  
**Permissions**: Review completed tasks, approve/reject work, quality checks

---

### 8. Reviewer
**Role**: Primary Reviewer  
**Email**: `reviewer1@scrutinise.co.uk`  
**Password**: `reviewer123`  
**Dashboard**: `/reviewer_dashboard`  
**Permissions**: Review assigned tasks, complete due diligence checks

---

### 9. QA Specialist
**Role**: Quality Assurance  
**Email**: `qa@scrutinise.co.uk`  
**Password**: `qa123`  
**Dashboard**: `/qa_dashboard`  
**Permissions**: Quality assurance reviews, process audits

---

### 10. SME (Subject Matter Expert)
**Role**: SME Referrals  
**Email**: `sme@scrutinise.co.uk`  
**Password**: `sme123`  
**Dashboard**: `/sme_dashboard`  
**Permissions**: Handle SME referrals, specialized reviews

---

## 🎨 Dashboard Features

### All Dashboards Include:
- ✅ **Light grey background** (#f5f6f8)
- ✅ **White cards** with shadow
- ✅ **Navy gradient navbar** with "Powered By Agora" logo
- ✅ **Orange accents** (#F89D43) for buttons and highlights
- ✅ **Dark readable text** (#1f2937)
- ✅ **Consistent full-width layout**

---

## 🔐 Security Notes

### Important:
- All passwords are for **TESTING ONLY**
- 2FA is **DISABLED** on all test accounts
- Accounts are **ACTIVE** and ready to use
- Sessions persist with cookies (`credentials: 'include'`)

### Password Reset:
If you need to reset any password, use the backend database:
```sql
UPDATE users SET password = '[hashed_password]' WHERE email = '[email]';
```

---

## 🚀 Quick Login Test

1. Go to: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai
2. Enter credentials (e.g., `ops@scrutinise.co.uk` / `ops123`)
3. Click "Login"
4. You'll be redirected to your role-specific dashboard

---

## 📊 Dashboard URLs by Role

| Role | Dashboard Path |
|------|----------------|
| Admin | `/list_users` |
| Operations Manager | `/operations_dashboard` |
| Team Leader | `/team_leader_dashboard` |
| QC Team Lead | `/qc_lead_dashboard` |
| QC Reviewer | `/qc_dashboard` |
| Reviewer | `/reviewer_dashboard` |
| QA | `/qa_dashboard` |
| SME | `/sme_dashboard` |
| Transaction Review | `/transaction/:taskId` |

---

## 🔧 Troubleshooting

### Can't Login?
1. Check you're using the correct URL (port 5173)
2. Ensure backend is running (port 5050)
3. Clear browser cache and cookies
4. Check browser console for errors

### Dashboard Not Loading?
1. Hard refresh: `Cmd + Shift + R` (Mac) or `Ctrl + Shift + R` (Windows)
2. Check network tab in DevTools for failed API calls
3. Verify backend is responding: curl http://localhost:5050/api/health

### Alignment Issues?
1. Clear browser cache completely
2. Verify you're on the latest code version (git pull)
3. Check that frontend dev server restarted properly

---

## 📝 Notes

- **Database**: SQLite at `/home/user/webapp/DueDiligenceBackend/Due Diligence/scrutinise_workflow.db`
- **Frontend Port**: 5173
- **Backend Port**: 5050
- **Session Storage**: Cookies with `httpOnly` flag
- **Password Hashing**: Werkzeug's `generate_password_hash` with sha256

---

**Last Updated**: 2025-01-05  
**System Status**: ✅ ACTIVE  
**Environment**: Sandbox Development

---

## 💾 Save This Document

Please save this document locally for easy reference. All credentials are for development/testing purposes only.

**Recommended location**: Save as `LOGIN_CREDENTIALS.md` in your local workspace.
