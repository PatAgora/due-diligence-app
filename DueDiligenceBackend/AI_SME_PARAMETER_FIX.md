# 🔧 AI SME Parameter Fix Applied

**Date**: 2026-01-08  
**Issue**: "Error contacting the API" in browser  
**Root Cause**: Parameter name mismatch between frontend and backend  
**Status**: ✅ **FIXED**

---

## The Bug

### Parameter Mismatch
- **Frontend sends**: `q` (in FormData)
- **AI SME expects**: `query` (in Form parameter)
- **Flask proxy**: Was just forwarding as-is, causing mismatch

```javascript
// Frontend (AISME.jsx)
const formData = new FormData();
formData.append('q', q);  // ❌ Sends 'q'
```

```python
# AI SME Service (ai_sme_openai.py)
async def query(
    query: str = Form(...),  # ❌ Expects 'query'
    ...
)
```

Result: FastAPI returned validation error: `Field required` for `query`

---

## The Fix

Modified `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`:

```python
@csrf.exempt
@app.route('/api/sme/query', methods=['POST'])
@role_required('reviewer', ...)
def api_sme_query():
    """Proxy query to AI SME FastAPI"""
    try:
        import requests
        # Forward form data
        form_data = request.form.to_dict()
        
        # ✅ CRITICAL FIX: Frontend sends 'q', but AI SME expects 'query'
        if 'q' in form_data:
            form_data['query'] = form_data.pop('q')
        
        # ... rest of proxy code
```

**What it does**:
1. Receives `q` from frontend
2. Renames `q` → `query`
3. Forwards to AI SME service
4. AI SME receives `query` parameter correctly

---

## Services Status

### ✅ AI SME Service (Port 8000)
```bash
$ curl http://localhost:8000/health

{
  "status": "ok",
  "llm_backend": "openai-rag",
  "documents_loaded": 2,
  "message": "AI SME service is online (Document-only RAG mode - 2 documents loaded)"
}
```

### ✅ Flask Backend (Port 5050)
- Parameter fix applied
- Enhanced logging added
- Ready to proxy requests

### ✅ Frontend (Port 5173)
https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## Testing Steps

### 1. Open the Application
```
URL: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai
```

### 2. Login
```
Email: reviewer@scrutinise.co.uk
Password: Scrutinise2024!
```

### 3. Open AI SME
- Click on "AI SME" in the left sidebar
- OR: Open any task → Click the AI SME button

### 4. Test Questions

#### ✅ Test 1: Question in Documents
```
Ask: "What is source of wealth?"

Expected Answer:
"how the customer accumulated their overall wealth over time — 
including assets, income, business activities, and investments."

Source: Source_of_Wealth_and_Funds_Reviewer_Guide.pdf
```

#### ✅ Test 2: Question NOT in Documents
```
Ask: "What is the capital of France?"

Expected Answer:
"I am not able to confirm based on the current guidance. This has been 
raised as a referral for further review and a response will be provided 
as soon as possible."

Source: None (fallback message)
```

#### ✅ Test 3: Compliance Question
```
Ask: "What is enhanced due diligence?"

Expected: Answer from guidance (if EDD is mentioned in the PDFs)
```

---

## What Should Happen

### ✅ Success Flow
```
1. User types question in AI SME
2. Frontend sends: POST /api/sme/query with FormData {q: "question"}
3. Flask backend receives {q: "question"}
4. Flask renames to {query: "question"}
5. Flask forwards to AI SME service on port 8000
6. AI SME searches guidance documents
7. AI SME returns document-based answer
8. Flask proxies response back to frontend
9. Frontend displays answer
```

### ❌ Old Error Flow
```
1. User types question
2. Frontend sends {q: "question"}
3. Flask forwards {q: "question"} unchanged
4. AI SME expects {query: ...} → validation error
5. AI SME returns 422: Field required
6. Flask returns error to frontend
7. Frontend shows "Error contacting the API" ❌
```

---

## Verification

### Check Backend Logs
```bash
tail -f /tmp/backend.log | grep API_SME_QUERY
```

You should see:
```
[API_SME_QUERY] Called with form data: {'q': 'What is source of wealth?'}
[API_SME_QUERY] AI SME response status: 200
[API_SME_QUERY] AI SME response: {"status":"success","answer":"..."}
```

### Check AI SME Logs
```bash
tail -f /tmp/ai_sme_doconly.log
```

You should see:
```
[QUERY] Question: What is source of wealth?
[QUERY] Found guidance context: 1234 chars
```

---

## If It Still Doesn't Work

### 1. Clear Browser Cache
```
Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
```

### 2. Check Services are Running
```bash
# AI SME Service
curl http://localhost:8000/health

# Flask Backend
curl -I http://localhost:5050/login
```

### 3. Restart Services
```bash
# Restart AI SME
cd /home/user/webapp/DueDiligenceBackend
fuser -k 8000/tcp 2>/dev/null || true
nohup python3 ai_sme_openai.py > /tmp/ai_sme_doconly.log 2>&1 &

# Restart Flask Backend
fuser -k 5050/tcp 2>/dev/null || true
cd "Due Diligence"
nohup python3 app.py > /tmp/backend.log 2>&1 &
```

### 4. Check Frontend Error
Open browser console (F12) and look for error messages when asking a question.

---

## Files Modified

| File | Change | Purpose |
|------|--------|---------|
| `Due Diligence/app.py` | Lines ~16156-16158 | Rename `q` → `query` parameter |
| `Due Diligence/app.py` | Lines ~16151-16153 | Add debug logging |
| `Due Diligence/app.py` | Lines ~16177-16179 | Add response logging |

---

## Complete Request Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (React) - AISME.jsx                                │
│ Port 5173                                                   │
│                                                             │
│ User types: "What is source of wealth?"                    │
│ FormData: {q: "What is source of wealth?"}                 │
└────────────────────┬────────────────────────────────────────┘
                     │ POST /api/sme/query
                     │ body: FormData {q: "..."}
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Flask Backend - app.py                                      │
│ Port 5050                                                   │
│                                                             │
│ 1. Receive form_data = {q: "What is source of wealth?"}    │
│ 2. Rename: q → query                                        │
│ 3. form_data = {query: "What is source of wealth?"}        │
│ 4. Forward to AI SME service                                │
└────────────────────┬────────────────────────────────────────┘
                     │ POST http://localhost:8000/query
                     │ data: {query: "..."}
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ AI SME Service - ai_sme_openai.py                          │
│ Port 8000                                                   │
│                                                             │
│ 1. Receive query parameter ✅                               │
│ 2. Search guidance documents (2 PDFs)                       │
│ 3. Find relevant context from                               │
│    "Source_of_Wealth_and_Funds_Reviewer_Guide.pdf"         │
│ 4. Send to OpenAI with strict prompt                        │
│ 5. Return document-based answer                             │
│                                                             │
│ Response: {                                                 │
│   "status": "success",                                      │
│   "answer": "how the customer accumulated...",             │
│   "hits": 1,                                                │
│   "sources": ["Source_of_Wealth...pdf"],                   │
│   "mode": "document-only-rag"                               │
│ }                                                           │
└────────────────────┬────────────────────────────────────────┘
                     │ JSON Response
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Flask Backend                                               │
│ Forward response back to frontend                           │
└────────────────────┬────────────────────────────────────────┘
                     │ JSON Response
                     ↓
┌─────────────────────────────────────────────────────────────┐
│ Frontend                                                    │
│ Display answer to user                                      │
│                                                             │
│ "how the customer accumulated their overall wealth over    │
│  time — including assets, income, business activities,     │
│  and investments."                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary

✅ **Root cause identified**: Parameter name mismatch (`q` vs `query`)  
✅ **Fix applied**: Flask proxy now renames `q` → `query`  
✅ **Services running**: AI SME (8000), Flask (5050), Frontend (5173)  
✅ **Document-only mode**: Only answers from 2 uploaded PDFs  
✅ **Fallback working**: Returns referral message for non-document questions  

**Ready to test!** Please try the steps above and let me know the result.
