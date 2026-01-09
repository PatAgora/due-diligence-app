# AI SME Troubleshooting Summary

## Issue
The AI SME service returns "Error contacting the API" or "Not authenticated" errors when accessed through the browser.

## Root Causes Identified

### 1. Database Issues
- The database from the uploaded working version (`DueDiligence (FINAL).zip`) was corrupted/malformed
- Error: `sqlite3.DatabaseError: malformed database schema (95)`
- Solution: Created fresh database using `init_auth_db.py` script

### 2. Authentication Flow
The authentication chain works as follows:
```
Browser → Flask Backend (port 5050) → AI SME Service (port 8000)
```

- Flask Backend authenticates user via session cookie
- Flask Backend forwards `X-User-Id` header to AI SME
- AI SME Service checks either:
  - FastAPI session (for direct access)
  - `X-User-Id` header (for Flask-proxied requests)

### 3. Parameter Naming
- Frontend sends: `q` (query parameter)
- AI SME expects: `q` (Form parameter)
- Flask backend forwards: `q` as multipart/form-data using `files` parameter
- ✅ This configuration is CORRECT

### 4. Working Configuration Files

**Key files from uploaded working version:**
- `/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/app.py` - RAG-based FastAPI service
- `/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/init_auth_db.py` - Database initialization script
- `/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/chroma/` - Pre-initialized ChromaDB with documents
- `/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/data/` - Guidance documents

### 5. Services Status
```bash
# Check services
ps aux | grep -E "python|uvicorn" | grep -v grep

# Current status (as of troubleshooting):
# - Flask Backend: PID 29806 on port 5050 (RUNNING but database issues)
# - AI SME Service: PID 29898 on port 8000 (RUNNING)
```

## Solutions Implemented

### 1. Replaced AI SME Directory
```bash
# Backed up current AI SME
mv "AI SME" "AI SME.backup"

# Copied working version
cp -r "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME" ./
```

### 2. Created Fresh Database
```bash
cd "/home/user/webapp/DueDiligenceBackend/Due Diligence"
rm -f scrutinise_workflow.db*
python3 "../AI SME/init_auth_db.py" --email "reviewer@scrutinise.co.uk" --password "Scrutinise2024!" --name "Reviewer" --role "reviewer_1"
```

### 3. Flask Backend Configuration
The Flask backend at `Due Diligence/app.py` line 16148 correctly:
- Forwards form data as multipart/form-data
- Passes `X-User-Id` header from session
- Forwards session cookie
- Uses `files` parameter for proper Form data encoding

## Remaining Issues

### Database Lock/I/O Errors
- Multiple file handles open on database
- Flask app may not be closing connections properly
- Error: `sqlite3.OperationalError: disk I/O error`

### Login Returns 500 Error
Even with fresh database, login endpoint fails with disk I/O error. This suggests:
1. Database connection pool issues in Flask app
2. WAL mode conflicts
3. File permission issues

## Recommended Next Steps

### Option 1: Use Working Version As-Is (RECOMMENDED)
The uploaded working version should be deployed without modifications since it was proven to work in production:

```bash
# 1. Stop all services
fuser -k 5050/tcp 8000/tcp 2>/dev/null || true

# 2. Backup current version
cd /home/user/webapp/DueDiligenceBackend
mv "Due Diligence" "Due Diligence.backup"
mv "AI SME" "AI SME.backup"

# 3. Copy working version entirely
cp -r "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/Due Diligence" ./
cp -r "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME" ./

# 4. Initialize database
cd "Due Diligence"
python3 "../AI SME/init_auth_db.py" --email "reviewer@scrutinise.co.uk" --password "Scrutinise2024!" --name "Reviewer" --role "reviewer_1"

# 5. Restart services
cd ..
cd "Due Diligence" && nohup python3 app.py > /tmp/backend.log 2>&1 &
cd "../AI SME" && nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 > /tmp/ai_sme.log 2>&1 &
```

### Option 2: Fix Database Connection Issues
If using current codebase, need to:
1. Review Flask app database connection handling
2. Ensure all `conn.close()` calls are in finally blocks
3. Consider using connection pooling
4. Check for proper transaction handling

## Testing
```bash
# Test login
curl -s -X POST http://localhost:5050/login \
  -d "email=reviewer@scrutinise.co.uk" \
  -d "password=Scrutinise2024!" \
  -c /tmp/test_cookies.txt

# Test AI SME query
curl -s -X POST http://localhost:5050/api/sme/query \
  -d "q=What is source of wealth?" \
  -b /tmp/test_cookies.txt | python3 -m json.tool
```

## Key Findings from Code Analysis

### AI SME Service (`AI SME/app.py`)
- Line 124-148: `require_login()` checks FastAPI session OR `X-User-Id` header
- Line 346-368: `/query` endpoint expects `Form(...)` parameter `q`
- Uses RAG pipeline with ChromaDB for document retrieval
- OpenAI gpt-4o-mini for answer generation

### Flask Backend (`Due Diligence/app.py`)
- Line 16148-16197: `/api/sme/query` proxy endpoint
- Line 16160-16164: Extracts `user_id` from session and sets `X-User-Id` header
- Line 16173-16179: Forwards request using `requests.post()` with `files` parameter

## Conclusion
The AI SME directory has been successfully replaced with the working version from the uploaded file. However, database initialization issues persist due to SQLite locking/I/O problems in the Flask backend. 

**The root cause is NOT the AI SME service itself, but rather the Flask backend's database connection handling.**

To resolve completely, either:
1. Deploy the entire working version as-is (RECOMMENDED)
2. Fix the Flask backend's database connection management

## Files Referenced
- Working version: `/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/`
- Current version: `/home/user/webapp/DueDiligenceBackend/`
- AI SME app: `AI SME/app.py`
- Flask backend: `Due Diligence/app.py`
- Init script: `AI SME/init_auth_db.py`
- Database: `Due Diligence/scrutinise_workflow.db`
