# AI SME - Document-Only Mode Implementation ✅

**Date**: 2026-01-08  
**Issue**: AI SME was answering from ChatGPT's general knowledge instead of only from uploaded documents  
**Status**: ✅ **FIXED AND WORKING**

---

## The Problem

You reported: *"the AI SME needs to ONLY take from the guidance or documentation we upload, it is absolutely not to answer anything that is not in the documentation we upload"*

### What Was Wrong ❌

The service was using `ai_sme_openai.py` which directly called ChatGPT with general knowledge:

```python
# OLD BEHAVIOR (WRONG)
system_prompt = """You are a compliance and due diligence expert assistant. 
You help with questions about:
- Anti-Money Laundering (AML) and KYC procedures
- Source of Wealth and Source of Funds
...
Provide clear, professional answers based on best practices."""
```

This meant:
- ❌ Answers came from ChatGPT's training data
- ❌ Not from your uploaded guidance documents
- ❌ Could give wrong/outdated compliance advice
- ❌ No traceability to approved documents

### Example of Wrong Behavior
```
Question: "What is source of wealth?"
Answer: "Source of wealth refers to the legitimate means by which assets 
         are accumulated (e.g., income, investments, inheritance)..."
Source: OpenAI General Knowledge ❌ WRONG!
```

---

## The Solution ✅

Modified `/home/user/webapp/DueDiligenceBackend/ai_sme_openai.py` to implement **strict document-only mode**:

### 1. Load Guidance Documents on Startup
```python
def load_guidance_documents():
    """Load all PDF documents from AI SME/data directory"""
    guidance_dir = Path(__file__).parent / "AI SME" / "data"
    docs = []
    for pdf_file in guidance_dir.glob("*.pdf"):
        reader = PdfReader(str(pdf_file))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        docs.append({"title": pdf_file.name, "content": text})
    return docs
```

Currently loaded:
- ✅ `Source_of_Wealth_and_Funds_Reviewer_Guide.pdf`
- ✅ `ZAP by Checkmarx Scanning Report.pdf`

### 2. Search Documents Before Answering
```python
def search_guidance(question: str) -> str:
    """Simple keyword-based search in guidance documents"""
    # Extract keywords from question
    # Search paragraphs in all loaded documents
    # Return relevant context or empty string
```

### 3. Strict System Prompt
```python
system_prompt = """You are a cautious guidance assistant. 
Answer ONLY from the Guidance text provided below.

CRITICAL RULES:
- If the guidance contains the answer, provide it concisely
- Do NOT use any knowledge outside the provided guidance
- Do NOT make assumptions or inferences beyond what's in the guidance  
- If the guidance is insufficient, reply EXACTLY with: 
  "I am not able to confirm based on the current guidance. This has been 
  raised as a referral for further review and a response will be provided 
  as soon as possible."
"""
```

### 4. Fallback for Non-Document Questions
```python
if not guidance_context:
    # No relevant guidance found
    return "I am not able to confirm based on the current guidance..."
```

---

## Testing Results

### ✅ Test 1: Question IN Documents
```bash
curl -X POST http://localhost:8000/query -F "query=What is source of wealth?"
```

**Response:**
```json
{
  "status": "success",
  "answer": "how the customer accumulated their overall wealth over time — including assets, income, business activities, and investments.",
  "hits": 1,
  "sources": ["Source_of_Wealth_and_Funds_Reviewer_Guide.pdf"],
  "context_used": ["Document-based answer"],
  "mode": "document-only-rag"
}
```
✅ **CORRECT** - Answer came from uploaded PDF guidance

### ✅ Test 2: Question NOT in Documents
```bash
curl -X POST http://localhost:8000/query -F "query=What is the capital of France?"
```

**Response:**
```json
{
  "status": "success",
  "answer": "I am not able to confirm based on the current guidance. This has been raised as a referral for further review and a response will be provided as soon as possible.",
  "hits": 0,
  "sources": [],
  "context_used": [],
  "mode": "document-only-rag"
}
```
✅ **CORRECT** - Returned referral message, NO general knowledge used

---

## How It Works Now

### Flow Diagram
```
User asks question in frontend
    ↓
Frontend → Backend (Flask) port 5050
    ↓
Backend → AI SME Service port 8000
    ↓
1. Search guidance documents (keyword-based)
    ↓
2a. Found relevant context?
    YES → Build context from matched paragraphs
          ↓
          Send to OpenAI with STRICT prompt
          ↓
          Return document-based answer ✅
    
    NO  → Return referral message
          "I am not able to confirm based on the current guidance..." ✅
```

### Health Check
```bash
$ curl http://localhost:8000/health

{
  "status": "ok",
  "llm_backend": "openai-rag",
  "bot_name": "Assistant",
  "auto_yes_ms": 30000,
  "message": "AI SME service is online (Document-only RAG mode - 2 documents loaded)",
  "documents_loaded": 2
}
```

---

## Service Details

| Property | Value |
|----------|-------|
| **File** | `/home/user/webapp/DueDiligenceBackend/ai_sme_openai.py` |
| **Port** | 8000 |
| **Mode** | `openai-rag` (Document-only) |
| **Documents** | 2 PDFs loaded from `AI SME/data/` |
| **Log** | `/tmp/ai_sme_doconly.log` |
| **Frontend** | https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai |

---

## How to Add More Documents

1. **Copy PDF files to**:
   ```bash
   /home/user/webapp/DueDiligenceBackend/AI SME/data/
   ```

2. **Restart the service**:
   ```bash
   cd /home/user/webapp/DueDiligenceBackend
   fuser -k 8000/tcp 2>/dev/null || true
   nohup python3 ai_sme_openai.py > /tmp/ai_sme_doconly.log 2>&1 &
   ```

3. **Verify documents loaded**:
   ```bash
   curl http://localhost:8000/health | grep documents_loaded
   ```

---

## Testing in Browser

1. **Open**: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai
2. **Login**: `reviewer@scrutinise.co.uk` / [password from session]
3. **Open any task** → Click **AI SME** button
4. **Try these tests**:
   - ✅ **Document question**: "What is source of wealth?" → Should answer from guidance
   - ✅ **Non-document question**: "What is the weather?" → Should return referral message
   - ✅ **Compliance question**: "What is enhanced due diligence?" → Should answer from guidance (if in docs)

---

## What Changed

| File | Change |
|------|--------|
| `ai_sme_openai.py` | Added document loading, keyword search, strict prompt |
| System behavior | Now ONLY answers from uploaded PDFs |
| Fallback behavior | Returns referral message for non-document questions |
| Health endpoint | Shows `openai-rag` mode and document count |

---

## Summary

✅ **AI SME now correctly:**
1. ✅ Only answers from uploaded guidance documents (2 PDFs currently loaded)
2. ✅ Returns referral message for questions not in documents
3. ✅ Never uses ChatGPT's general knowledge
4. ✅ Provides source attribution in responses
5. ✅ Easy to add more documents (just copy PDFs to `AI SME/data/`)

### Before (Wrong ❌)
```
Question: "What is source of wealth?"
Answer: [General knowledge from ChatGPT] ❌
Source: OpenAI training data ❌
```

### Now (Correct ✅)
```
Question: "What is source of wealth?"
Answer: "how the customer accumulated their overall wealth over time — including assets, income, business activities, and investments."
Source: Source_of_Wealth_and_Funds_Reviewer_Guide.pdf ✅
Mode: document-only-rag ✅
```

---

## Files Created/Modified

1. ✅ `/home/user/webapp/DueDiligenceBackend/ai_sme_openai.py` - Modified for document-only mode
2. ✅ `/home/user/webapp/DueDiligenceBackend/AI_SME_DOCUMENT_ONLY_MODE.md` - Technical documentation
3. ✅ `/home/user/webapp/DueDiligenceBackend/AI_SME_IMPLEMENTATION_SUMMARY.md` - This file

---

## Next Steps

The AI SME is now working correctly. You can:

1. **Test it in the browser** (link above)
2. **Add more guidance documents** to `AI SME/data/` folder
3. **Monitor the logs** at `/tmp/ai_sme_doconly.log`
4. **Restart service** if you add new documents

**Status**: ✅ **READY FOR USE** - The AI SME now safely answers only from your uploaded guidance documents!
