# AI SME - Document-Only Mode ✅

**Date**: 2026-01-08  
**Status**: ✅ **WORKING CORRECTLY**

## Problem Identified

The AI SME was using OpenAI's general knowledge to answer questions instead of only answering from uploaded guidance documents.

### Previous Behavior (WRONG ❌)
```
Question: "What is source of wealth?"
Answer: "Source of wealth refers to the legitimate means by which assets are accumulated (e.g., income, investments, inheritance)..."
Source: OpenAI GPT-3.5 General Knowledge ❌
```

This was dangerous because:
- Answers came from ChatGPT's training data, not your guidance
- Could give wrong or outdated compliance advice
- No traceability to approved documents

## Solution Implemented

Modified `/home/user/webapp/DueDiligenceBackend/ai_sme_openai.py` to implement **strict document-only mode**:

### Key Changes

1. **Load Guidance Documents on Startup**
   - Reads all PDFs from `AI SME/data/` directory
   - Currently loaded: 2 documents
     - `Source_of_Wealth_and_Funds_Reviewer_Guide.pdf`
     - `ZAP by Checkmarx Scanning Report.pdf`

2. **Keyword-Based Document Search**
   - Extracts keywords from user question
   - Searches across all loaded documents
   - Finds relevant paragraphs/sections
   - Ranks by keyword matches

3. **Strict System Prompt**
   ```
   You are a cautious guidance assistant. Answer ONLY from the Guidance text provided below.

   CRITICAL RULES:
   - If the guidance contains the answer, provide it concisely
   - Do NOT use any knowledge outside the provided guidance
   - Do NOT make assumptions or inferences beyond what's in the guidance  
   - Do NOT include citations, document titles, or source markers
   - If the guidance is insufficient, reply EXACTLY with: 
     "I am not able to confirm based on the current guidance. This has been raised 
     as a referral for further review and a response will be provided as soon as possible."
   ```

4. **Fallback for Non-Document Questions**
   - If no relevant guidance found → returns referral message
   - Never uses general knowledge

## Testing Results

### ✅ Test 1: Document-Based Question
```bash
Question: "What is source of wealth?"

Response:
{
  "status": "success",
  "answer": "how the customer accumulated their overall wealth over time — including assets, income, business activities, and investments.",
  "hits": 1,
  "sources": ["Source_of_Wealth_and_Funds_Reviewer_Guide.pdf"],
  "mode": "document-only-rag"
}
```
✅ **Correct** - Answer came from uploaded guidance document

### ✅ Test 2: Non-Document Question
```bash
Question: "What is the capital of France?"

Response:
{
  "status": "success",
  "answer": "I am not able to confirm based on the current guidance. This has been raised as a referral for further review and a response will be provided as soon as possible.",
  "hits": 0,
  "sources": [],
  "mode": "document-only-rag"
}
```
✅ **Correct** - Returned fallback message, NO general knowledge used

## Current System Behavior

### Flow Diagram
```
User Question
     ↓
Search Guidance Documents (Keyword-based)
     ↓
Found Relevant Context? ───NO──→ Return Referral Message
     ↓ YES
OpenAI + Context
     ↓
Clean Answer (Remove citations)
     ↓
Return Answer
```

### Health Check
```bash
curl http://localhost:8000/health

{
  "status": "ok",
  "llm_backend": "openai-rag",
  "bot_name": "Assistant",
  "auto_yes_ms": 30000,
  "message": "AI SME service is online (Document-only RAG mode - 2 documents loaded)",
  "documents_loaded": 2
}
```

## Service Details

- **File**: `/home/user/webapp/DueDiligenceBackend/ai_sme_openai.py`
- **Port**: 8000
- **Log**: `/tmp/ai_sme_doconly.log`
- **Documents Location**: `/home/user/webapp/DueDiligenceBackend/AI SME/data/`

## How to Add More Documents

1. **Copy PDF files to**: `/home/user/webapp/DueDiligenceBackend/AI SME/data/`
2. **Restart the service**:
   ```bash
   cd /home/user/webapp/DueDiligenceBackend
   fuser -k 8000/tcp 2>/dev/null || true
   nohup python3 ai_sme_openai.py > /tmp/ai_sme_doconly.log 2>&1 &
   ```
3. **Verify**:
   ```bash
   curl http://localhost:8000/health
   # Check "documents_loaded" count
   ```

## Architecture

```
Frontend (React) 
    ↓ POST /api/sme/query
Backend (Flask) Port 5050
    ↓ Proxy to
AI SME Service Port 8000
    ↓
1. Search Guidance Docs (Keyword-based)
2. Build Context from Matches
3. OpenAI with Strict Prompt
4. Return Document-Only Answer
```

## Important Notes

### ✅ What It Does Now
- Only answers from uploaded guidance documents
- Returns referral message if guidance insufficient
- No general knowledge responses
- Traceable answers (sources included in response)

### ⚠️ Current Limitations
- Uses simple keyword-based search (not semantic/vector search)
- Requires PDF documents in specific directory
- No ChromaDB/embeddings (to avoid startup delays)

### 🚀 Future Improvements (If Needed)
- Implement vector embeddings for better search
- Support more file formats (DOCX, TXT, etc.)
- Admin UI for uploading documents
- SME resolution caching
- Analytics on question coverage

## Troubleshooting

### Service Not Responding
```bash
# Check if running
ps aux | grep ai_sme_openai.py

# Check logs
tail -50 /tmp/ai_sme_doconly.log

# Restart
cd /home/user/webapp/DueDiligenceBackend
fuser -k 8000/tcp 2>/dev/null || true
nohup python3 ai_sme_openai.py > /tmp/ai_sme_doconly.log 2>&1 &
```

### No Documents Loaded
```bash
# Check data directory
ls -la /home/user/webapp/DueDiligenceBackend/"AI SME"/data/

# Add PDF files and restart
```

### Still Getting General Knowledge Answers
```bash
# Verify health endpoint shows "openai-rag" mode
curl http://localhost:8000/health | grep llm_backend

# Should return: "llm_backend": "openai-rag"
```

## Testing Commands

```bash
# Test with document question
curl -X POST http://localhost:8000/query \
  -F "query=What is enhanced due diligence?"

# Test with non-document question  
curl -X POST http://localhost:8000/query \
  -F "query=What is the weather today?"
```

## Summary

✅ **AI SME now correctly:**
1. Only answers from uploaded guidance documents
2. Returns referral message for non-document questions
3. Never uses ChatGPT's general knowledge
4. Provides source attribution in responses
5. Supports easy document addition (just copy PDFs to data/ folder)

**Status**: Ready for use! The system is now safe and compliant.
