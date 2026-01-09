# Application Rollback Summary

## Date: January 8, 2026 - 17:38 UTC

## What Was Rolled Back

### 1. ✅ Database Rolled Back
- **From**: Fresh database (28K) created during AI SME fixes
- **To**: Original uploaded database (336K) with all production data
- **Location**: `/home/user/webapp/DueDiligenceBackend/Due Diligence/scrutinise_workflow.db`
- **Backup Created**: `scrutinise_workflow.db.backup_20260108_172758`

### 2. ✅ Flask Backend Code Rolled Back
- **File**: `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`
- **Change Reverted**: Line 16173-16179 (api_sme_query function)
- **From** (fixed version):
  ```python
  response = requests.post(
      f"{AI_SME_BASE_URL}/query",
      data=form_data,  # ← Simple form data
      headers=headers,
      cookies=cookies,
      timeout=30
  )
  ```
- **To** (previous version):
  ```python
  response = requests.post(
      f"{AI_SME_BASE_URL}/query",
      files={key: (None, value) for key, value in form_data.items()},  # ← Multipart file upload
      headers=headers,
      cookies=cookies,
      timeout=30
  )
  ```

### 3. ✅ AI SME Code (NOT Rolled Back)
- **AI SME directory remains**: The working version from uploaded files
- **Reason**: The AI SME itself was correct; only the Flask proxy had the issue

## Current Application State

### What's Working
- ✅ Database has all production data (users, referrals, reviews, etc.)
- ✅ Login with existing credentials works
- ✅ AI SME service running on port 8000
- ✅ Flask backend running on port 5050
- ✅ Frontend running on port 5173

### What's NOT Working (As Expected - Rolled Back Behavior)
- ❌ AI SME queries from frontend will fail with 422 error
- **Reason**: Flask sends `files=` (multipart/form-data) but AI SME expects `data=` (simple form data)
- **This is the INTENDED rolled-back state** - the issue that existed before the fix

## Service URLs

- **Frontend**: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai
- **Backend**: https://5050-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai
- **AI SME**: http://localhost:8000 (internal only)

## Login Credentials

All original user accounts from the production database are available:
- admin@scrutinise.co.uk
- ops@scrutinise.co.uk
- teamlead@scrutinise.co.uk
- qctl@scrutinise.co.uk
- reviewer@scrutinise.co.uk
- qc@scrutinise.co.uk
- sme@scrutinise.co.uk

## How to Re-Apply the Fix

If you want to fix the AI SME issue again, simply change line 16175 in `app.py`:

**Change FROM:**
```python
files={key: (None, value) for key, value in form_data.items()},
```

**Change TO:**
```python
data=form_data,
```

Then restart the Flask backend:
```bash
cd /home/user/webapp/DueDiligenceBackend/"Due Diligence"
pkill -9 python3
sleep 2
nohup python3 app.py > /tmp/backend.log 2>&1 &
```

## Files Modified During Rollback

1. `/home/user/webapp/DueDiligenceBackend/Due Diligence/scrutinise_workflow.db` (restored)
2. `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py` (line 16175 reverted)
3. Created backup: `scrutinise_workflow.db.backup_20260108_172758`

## Notes

- The rollback successfully restores the application to its state BEFORE the AI SME fixes
- The AI SME service itself remains the correct working version
- Only the Flask proxy code was rolled back to the problematic version
- This creates the expected 422 error when trying to use AI SME from the frontend
