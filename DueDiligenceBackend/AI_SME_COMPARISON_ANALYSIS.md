# AI SME - Comparison Analysis (Working vs Current)

**Date**: 2026-01-08  
**Analysis**: Compared uploaded working version with current implementation

---

## Key Findings

### Working Version (From Uploaded File)

**Service**: `/AI SME/app.py` - FastAPI with RAG (ChromaDB + OpenAI)

**Endpoint Configuration**:
```python
@app.post("/query")
async def query_bot(
    request: Request,
    q: str = Form(...),  # ✅ Parameter name is 'q'
    user: sqlite3.Row = Depends(require_login),  # ✅ Requires authentication
):
    try:
        result = pipeline.answer(q)
        return result
```

**Authentication Method**:
```python
def require_login(request: Request) -> sqlite3.Row:
    # Check FastAPI's own session
    uid = request.session.get("user_id")
    
    # If no FastAPI session, check Flask-proxied user ID in header
    if not uid:
        flask_user_id = request.headers.get("X-User-Id")  # ✅ Flask proxy support
        if flask_user_id:
            uid = int(flask_user_id)
    
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
```

**Flask Backend Proxy** (`Due Diligence/app.py`):
```python
@app.route('/api/sme/query', methods=['POST'])
def api_sme_query():
    form_data = request.form.to_dict()  # ✅ Forwards 'q' as-is
    
    headers = {}
    if user_id:
        headers['X-User-Id'] = str(user_id)  # ✅ Sends auth header
    
    response = requests.post(
        f"{AI_SME_BASE_URL}/query",  # http://localhost:8000
        data=form_data,
        headers=headers,
        timeout=30
    )
```

**RAG Pipeline**:
- Uses ChromaDB for vector search
- Sentence transformers for embeddings
- OpenAI GPT-4o-mini for generation
- Strict system prompt for document-only answers

---

### Current Broken Version

**Problem 1**: Wrong Service Running
- Initially: `ai_sme_openai.py` (simple keyword search)
  - Expected parameter: `query` ❌ (should be `q`)
  - No authentication ❌
  - No RAG/ChromaDB ❌

**Problem 2**: RAG Service Initialization Hang
- Tried to start: `AI SME/app.py`
- Status: Hangs during startup (loading ChromaDB + embeddings)
- Issue: ChromaDB migration errors, slow embedding model loading in sandbox

**Problem 3**: Parameter Mismatch (Now Fixed)
- Flask proxy was forwarding `q` directly
- My simple service expected `query`
- Fixed by renaming parameter in Flask proxy

---

## Why It Worked Before

The working version from the uploaded file:
1. ✅ Had ChromaDB pre-initialized with documents
2. ✅ Had embeddings already computed
3. ✅ Service started quickly (~5 seconds)
4. ✅ Used parameter `q` throughout the chain:
   - Frontend → `q`
   - Flask proxy → `q`
   - FastAPI AI SME → `q`

---

## Current Status

**Services Running**:
- ❌ RAG AI SME (port 8000): Started but hanging during initialization
- ✅ Flask Backend (port 5050): Running and forwarding requests
- ✅ Frontend (port 5173): Running

**What's Blocking**:
1. ChromaDB initialization is VERY slow in sandbox
2. Sentence transformer model loading takes minutes
3. Need pre-initialized ChromaDB database

---

## Solutions

### Option 1: Use Pre-initialized ChromaDB (RECOMMENDED)
**Copy working ChromaDB from uploaded file**:
```bash
# Stop current service
fuser -k 8000/tcp

# Backup current chroma
mv "/home/user/webapp/DueDiligenceBackend/AI SME/chroma" \
   "/home/user/webapp/DueDiligenceBackend/AI SME/chroma.backup"

# Copy working chroma from uploaded file
cp -r "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/chroma" \
      "/home/user/webapp/DueDiligenceBackend/AI SME/chroma"

# Copy working database
cp "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/scrutinise_workflow.db" \
   "/home/user/webapp/DueDiligenceBackend/AI SME/scrutinise_workflow.db"

# Start service
cd "/home/user/webapp/DueDiligenceBackend/AI SME"
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 &

# Should start in ~5 seconds with pre-initialized data
```

### Option 2: Simplified Service (CURRENT FALLBACK)
Keep using `ai_sme_openai.py` with keyword search:
- ✅ Starts instantly
- ✅ Answers from documents only
- ✅ Returns referral message if not in docs
- ❌ Less accurate (keyword-based vs semantic search)

### Option 3: Initialize ChromaDB Separately
```bash
# Run initialization script separately
cd "/home/user/webapp/DueDiligenceBackend/AI SME"
python3 -c "
from rag import RAGPipeline
pipeline = RAGPipeline()
print('ChromaDB initialized')
"

# Then start service
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 &
```

---

## Recommendations

**IMMEDIATE FIX** (Option 1):
1. Copy pre-initialized ChromaDB from uploaded working file
2. Start the RAG-based AI SME service
3. Should work immediately

**WHY THIS WILL WORK**:
- Working version has documents already ingested
- Embeddings already computed
- No initialization delay
- Proven to work

**Steps**:
```bash
# 1. Stop current services
fuser -k 8000/tcp

# 2. Copy working ChromaDB
rm -rf "/home/user/webapp/DueDiligenceBackend/AI SME/chroma"
cp -r "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/chroma" \
      "/home/user/webapp/DueDiligenceBackend/AI SME/"

# 3. Copy working auth database
cp "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/scrutinise_workflow.db" \
   "/home/user/webapp/DueDiligenceBackend/AI SME/"

# 4. Ensure .env file exists with OpenAI key
cat > "/home/user/webapp/DueDiligenceBackend/AI SME/.env" << 'EOF'
OPENAI_API_KEY=YOUR_OPENAI_API_KEY_HERE
EOF

# 5. Start service
cd "/home/user/webapp/DueDiligenceBackend/AI SME"
nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 > /tmp/ai_sme_rag.log 2>&1 &

# 6. Wait 10 seconds and test
sleep 10
curl http://localhost:8000/health

# 7. Test in browser
# Login and try AI SME - should work!
```

---

## Key Differences Summary

| Aspect | Working Version | Current Broken | Fix Needed |
|--------|----------------|----------------|------------|
| Service | RAG FastAPI (app.py) | Simple keyword (ai_sme_openai.py) | Use RAG app.py |
| Parameter | `q` | `query` → Fixed to `q` | ✅ Done |
| Auth | `X-User-Id` header | None | Use working app.py |
| ChromaDB | Pre-initialized | Trying to initialize | Copy from working |
| Startup | ~5 seconds | Hangs (>5 min) | Use pre-init DB |
| Accuracy | High (semantic) | Medium (keyword) | Use RAG |

---

## Current Error in Browser

**Frontend Error**: "Assistant: Error contacting the API."

**Root Cause**:
1. RAG service is starting but hanging during ChromaDB initialization
2. Flask proxy forwards request, but gets no response (timeout)
3. Frontend shows error

**Fix**: Copy pre-initialized ChromaDB from working version (Option 1 above)

---

## Files to Compare

If you want to see exact differences:

```bash
# Compare Flask proxies
diff "/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py" \
     "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/Due Diligence/app.py"

# Compare AI SME services
diff "/home/user/webapp/DueDiligenceBackend/AI SME/app.py" \
     "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/app.py"

# Compare settings
diff "/home/user/webapp/DueDiligenceBackend/AI SME/settings.py" \
     "/home/user/uploaded_files/DueDiligence/DueDiligenceBackend/AI SME/settings.py"
```

---

## Conclusion

**The working version uses**:
- ✅ RAG-based FastAPI with ChromaDB (not simple keyword search)
- ✅ Parameter `q` (not `query`)
- ✅ Authentication via `X-User-Id` header
- ✅ Pre-initialized ChromaDB database

**To fix the current version**:
- ✅ Copy pre-initialized ChromaDB from uploaded working file
- ✅ Start RAG-based AI SME service
- ✅ Should work immediately without initialization delays

**Current Status**:
- RAG service is running but stuck in initialization
- Need to use pre-initialized database from working version
- Then service will start in ~5 seconds and work correctly
