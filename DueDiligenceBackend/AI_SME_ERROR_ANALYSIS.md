# AI SME Error - Service Not Running

## 🔴 Current Error

**User sees**: "Assistant: Error contacting the API."  
**Status indicator**: "🔴 SME Status: Offline"

## 🏗️ Current Architecture

### System Design

```
Frontend (React)
    ↓
    HTTP Request to: /api/sme/query
    ↓
Backend (Flask - port 5050)
    ↓
    Proxy/Forward to: http://localhost:8000/query
    ↓
AI SME Service (FastAPI - port 8000) ❌ NOT RUNNING
    ↓
    RAG System (ChromaDB + OpenAI)
```

### Component Breakdown

#### 1. Frontend (React Component)
**File**: `/home/user/webapp/DueDiligenceFrontend/src/components/AISME.jsx`

**What it does**:
- Provides chat UI for asking questions
- Sends requests to `/api/sme/query`
- Shows responses from AI SME
- Displays referral options if needed

**Key API calls**:
```javascript
// Health check
fetch(`${BASE_URL}/api/sme/health`)

// Ask question
fetch(`${BASE_URL}/api/sme/query`, {
  method: 'POST',
  body: formData with 'query', 'task_id', 'customer_id'
})

// Create referral
fetch(`${BASE_URL}/api/sme/referral`, {
  method: 'POST',
  body: formData with 'question', 'task_id', 'context'
})
```

#### 2. Backend (Flask Proxy)
**File**: `/home/user/webapp/DueDiligenceBackend/Due Diligence/app.py`

**What it does**:
- Receives requests from frontend at `/api/sme/*`
- Forwards them to AI SME FastAPI service at `http://localhost:8000`
- Returns responses back to frontend

**Configuration** (Line 16091):
```python
AI_SME_BASE_URL = os.environ.get("AI_SME_BASE_URL", "http://localhost:8000")
```

**Key routes**:
- `/api/sme/health` → Forwards to `http://localhost:8000/health`
- `/api/sme/query` → Forwards to `http://localhost:8000/query`
- `/api/sme/referral` → Forwards to `http://localhost:8000/referral`
- `/api/sme/feedback` → Forwards to `http://localhost:8000/feedback`

**Error handling**:
```python
except requests.exceptions.ConnectionError:
    # FastAPI is not running
    return jsonify({
        'status': 'error',
        'llm_backend': 'unknown',
        'bot_name': 'Assistant',
        'auto_yes_ms': 30000
    }), 503
```

#### 3. AI SME Service (FastAPI + RAG)
**File**: `/home/user/webapp/DueDiligenceBackend/AI SME/app.py`

**What it should do**:
- Listen on port 8000
- Receive queries from Flask backend
- Search uploaded documents using vector search
- Generate answers ONLY from document content
- Return responses or referral messages

**Status**: ❌ **NOT RUNNING** - This is why you're getting the error!

## 🔍 Root Cause Analysis

### Why the Error Occurs

1. **Frontend** sends request to `/api/sme/query`
2. **Flask backend** receives it and tries to forward to `http://localhost:8000/query`
3. **AI SME service not running** on port 8000
4. **Connection fails** → Flask catches `ConnectionError`
5. **Flask returns error** → Frontend shows "Error contacting the API"

### Error Flow

```
User asks: "what is sow"
    ↓
Frontend: POST /api/sme/query
    ↓
Flask: Try to proxy to localhost:8000
    ↓
Connection Error: No service on port 8000
    ↓
Flask: Return 503 error
    ↓
Frontend: Show "Error contacting the API"
```

## ✅ Solution

### Start the AI SME Service

The AI SME service needs to be running on port 8000 for the system to work.

**Location**: `/home/user/webapp/DueDiligenceBackend/AI SME/`

**What it provides**:
1. ✅ Document-based RAG system
2. ✅ Vector search through uploaded guidance
3. ✅ ONLY answers from uploaded documents
4. ✅ Fallback message when guidance insufficient
5. ✅ SME resolution storage

## 🚀 How to Fix

### Step 1: Configure OpenAI API Key

The AI SME service needs an OpenAI API key to work.

**Option A: Config file** (Recommended)
```bash
cat > ~/.genspark_llm.yaml << 'EOF'
openai:
  api_key: your-api-key-here
  base_url: https://www.genspark.ai/api/llm_proxy/v1
EOF
```

**Option B: Environment variable**
```bash
export OPENAI_API_KEY="your-key-here"
```

**Option C: .env file in AI SME directory**
```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"
cat > .env << 'EOF'
OPENAI_API_KEY=your-key-here
OPENAI_BASE_URL=https://www.genspark.ai/api/llm_proxy/v1
EOF
```

### Step 2: Start the AI SME Service

**Method 1: Direct (for testing)**
```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"
uvicorn app:app --host 0.0.0.0 --port 8000
```

**Method 2: Background with nohup**
```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"
nohup uvicorn app:app --host 0.0.0.0 --port 8000 > /tmp/ai_sme_rag.log 2>&1 &
```

**Method 3: PM2 (production-like)**
```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"
pm2 start "uvicorn app:app --host 0.0.0.0 --port 8000" --name ai-sme
```

### Step 3: Verify Service is Running

**Health check**:
```bash
curl http://localhost:8000/health
```

**Expected output**:
```json
{
  "status": "ok",
  "llm_backend": "openai",
  "bot_name": "Assistant",
  "auto_yes_ms": 30000
}
```

**Check processes**:
```bash
lsof -i :8000
```

**Should show**:
```
python3  12345 user  5u  IPv4  TCP *:8000 (LISTEN)
```

### Step 4: Test the Full Flow

**From backend**:
```bash
curl -X POST http://localhost:8000/query \
  -F "query=What is source of wealth?" \
  -F "task_id=TEST-001"
```

**From frontend**:
1. Refresh the AI SME page
2. Status should change from "Offline" to "Online"
3. Ask a question: "What is EDD?"
4. Should get answer from uploaded documents

## 📊 What the System Does (When Running)

### Document-Based Responses

**Uploaded Documents** (already in system):
- `Source_of_Wealth_and_Funds_Reviewer_Guide.pdf`
- `ZAP by Checkmarx Scanning Report.pdf`

### Query Flow (When Working)

1. **User asks question**: "What is enhanced due diligence?"
2. **Frontend** → Flask `/api/sme/query`
3. **Flask** → AI SME `/query`
4. **AI SME**:
   - Embeds the question
   - Searches ChromaDB for similar document chunks
   - Retrieves top 5 most relevant chunks
   - Builds prompt with system instructions + retrieved chunks
   - Sends to OpenAI GPT-4
   - Gets answer based ONLY on document content
   - Returns clean answer
5. **Flask** → Frontend
6. **User sees answer**

### Response Types

**Type 1: Guidance Found**
```
Question: "What is source of wealth?"
Answer: "Source of wealth refers to the origin of the total body 
of wealth that a customer has accumulated. It is distinct from 
source of funds, which refers to the origin of the particular 
funds used for a specific transaction..."
```

**Type 2: Guidance Not Found**
```
Question: "What is the capital of France?"
Answer: "I am not able to confirm based on the current guidance. 
This has been raised as a referral for further review and a 
response will be provided as soon as possible."
```

## 🔧 Architecture Summary

### Ports

| Service | Port | Status |
|---------|------|--------|
| Frontend (Vite) | 5173 | ✅ Running |
| Backend (Flask) | 5050 | ✅ Running |
| AI SME (FastAPI) | 8000 | ❌ Not Running |

### Data Flow

```
User Browser (5173)
    ↓ HTTP
Flask Backend (5050) - /api/sme/*
    ↓ HTTP Proxy
FastAPI Service (8000) - /query, /health, etc.
    ↓
RAG System
    ├─ ChromaDB (Vector Search)
    ├─ Sentence Transformers (Embeddings)
    └─ OpenAI API (Text Generation)
        ↓
Response ← ← ← ← ←
```

### Why This Architecture?

1. **Separation of Concerns**:
   - Flask handles main app logic
   - FastAPI handles AI/RAG operations (faster, async)

2. **Modularity**:
   - AI SME can be updated independently
   - Can be deployed on separate server if needed

3. **Technology Match**:
   - Flask for traditional web app
   - FastAPI for AI/ML services (better async, OpenAPI docs)

## 🎯 What AI SME Is Supposed To Do

### Primary Function
**Answer compliance questions using ONLY uploaded guidance documents**

### Key Features

1. **Document Upload**
   - Upload PDF, DOCX, TXT, MD, CSV files
   - Extract text and chunk into 900-char segments
   - Create embeddings using sentence-transformers
   - Store in ChromaDB vector database

2. **Question Answering**
   - User asks compliance question
   - System searches vector DB for relevant chunks
   - Retrieves top K most similar chunks
   - Builds prompt with system instructions + chunks
   - OpenAI generates answer ONLY from provided chunks
   - Returns clean answer (no citations)

3. **Referral System**
   - If guidance insufficient → Create referral
   - SME reviews and provides answer
   - Answer stored as "resolution"
   - Future similar questions get instant SME answer

4. **Document-Only Constraint**
   - System prompt enforces document-only responses
   - Cannot use general knowledge
   - Must return fallback message if uncertain

### System Prompt (settings.py)
```python
"You are a cautious guidance assistant. Answer ONLY from the 
Guidance text provided.
- If the guidance is sufficient, answer concisely in plain English.
- Do NOT include citations or source markers.
- If the guidance is insufficient to answer, reply exactly:
  'I am not able to confirm based on the current guidance. 
   This has been raised as a referral for further review and 
   a response will be provided as soon as possible.'"
```

## 📝 Current State

### What Exists
✅ Complete RAG system in `AI SME/` directory  
✅ 2 PDF guidance documents uploaded  
✅ ChromaDB vector database populated  
✅ Frontend UI for chat  
✅ Backend proxy routes  
✅ Document management UI  
✅ Referral system  

### What's Missing
❌ OpenAI API key configuration  
❌ AI SME service not started  

### Why You See the Error
The AI SME FastAPI service (port 8000) is not running, so when the Flask backend tries to proxy requests to it, the connection fails.

## 🔄 Quick Fix Checklist

- [ ] Configure OpenAI API key (choose one method above)
- [ ] Navigate to AI SME directory: `cd /home/user/webapp/DueDiligenceBackend/"AI SME"`
- [ ] Start service: `uvicorn app:app --host 0.0.0.0 --port 8000`
- [ ] Verify health: `curl http://localhost:8000/health`
- [ ] Test query: `curl -X POST http://localhost:8000/query -F "query=What is EDD?"`
- [ ] Refresh frontend and test

## 📚 Related Documentation

- **Complete RAG Guide**: `/home/user/webapp/DueDiligenceBackend/AI_SME_RAG_SYSTEM_GUIDE.md`
- **AI SME Frontend**: `/home/user/webapp/DueDiligenceFrontend/src/components/AISME.jsx`
- **AI SME Backend**: `/home/user/webapp/DueDiligenceBackend/AI SME/app.py`
- **RAG Pipeline**: `/home/user/webapp/DueDiligenceBackend/AI SME/rag.py`

## 🎯 Summary

**Current Issue**: AI SME service not running on port 8000

**Root Cause**: FastAPI service needs to be started

**Solution**: 
1. Configure OpenAI API key
2. Start the AI SME service: `cd "AI SME" && uvicorn app:app --host 0.0.0.0 --port 8000`
3. Verify it's responding

**What It Does**: 
- Answers questions using ONLY uploaded guidance documents
- Uses RAG (vector search + LLM) to find and generate answers
- Falls back to referral message if guidance insufficient
- Stores SME-approved answers for future reuse

**Current Status**: 
- ✅ System built and ready
- ✅ Documents uploaded
- ❌ Service not started (causing the error)
