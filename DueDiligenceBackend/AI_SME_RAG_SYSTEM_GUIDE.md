# AI SME RAG System - Document-Only Responses

## ✅ IMPORTANT: The AI SME System Already Exists!

The AI SME service you need is **already built** and located in:
```
/home/user/webapp/DueDiligenceBackend/AI SME/
```

This is a **complete RAG (Retrieval-Augmented Generation) system** that ONLY answers from uploaded documentation.

---

## 🎯 What It Does

### Core Functionality
1. ✅ **Document Upload**: Upload PDF, DOCX, TXT, MD, CSV files as guidance
2. ✅ **Vector Search**: Uses ChromaDB + embeddings to find relevant guidance
3. ✅ **Restricted Responses**: ONLY answers from uploaded documents
4. ✅ **Strict Fallback**: Returns specific message if guidance insufficient
5. ✅ **SME Resolutions**: Stores and reuses SME-approved answers
6. ✅ **Authentication**: Integrated with Due Diligence user auth

### System Prompt (Line 27-35 in settings.py)
```python
SYSTEM_PROMPT = """
You are a cautious guidance assistant. Answer ONLY from the Guidance text provided.
- If the guidance is sufficient, answer concisely in plain English.
- Do NOT include citations, document titles, square-bracket notes, footnote numbers, or source markers of any kind in the answer.
- Do NOT add text like [Source: …], [1], (see guidance), or similar. Give a clean answer only.
- If the guidance is insufficient to answer, reply exactly:
  "I am not able to confirm based on the current guidance. This has been raised as a referral for further review and a response will be provided as soon as possible."
- Use first-person ("I") when referring to limitations.
""".strip()
```

---

## 📂 Directory Structure

```
AI SME/
├── app.py                    # Main FastAPI application
├── rag.py                    # RAG pipeline (retrieval + generation)
├── llm.py                    # LLM client (OpenAI or Ollama)
├── settings.py               # Configuration
├── requirements.txt          # Dependencies
├── chroma/                   # Vector database (persistent)
├── data/                     # Uploaded documents + config
│   ├── Source_of_Wealth_and_Funds_Reviewer_Guide.pdf
│   ├── ZAP by Checkmarx Scanning Report.pdf
│   ├── config.json
│   ├── feedback.jsonl
│   └── referrals.jsonl
├── static/                   # Web UI assets
└── templates/                # HTML templates
```

---

## 🔧 Configuration

### settings.py (Key Settings)

```python
# LLM Backend
LLM_BACKEND = "openai"  # or "ollama"

# If using OpenAI
OPENAI_MODEL = "gpt-4o-mini"  # or "gpt-4o"

# If using Ollama (local)
OLLAMA_MODEL = "llama3.1"
OLLAMA_URL = "http://localhost:11434"

# Retrieval Settings
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
TOP_K = 5  # Number of document chunks to retrieve

# Embeddings
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# SME Resolution Settings
QA_MIN_SIM = 0.78              # Similarity threshold for reusing past answers
QA_MAX_AGE_DAYS = 730          # Ignore resolutions older than 2 years
SHOW_QA_PROVENANCE_DEFAULT = False  # Hide source attribution
```

---

## 🚀 How to Start the Service

### Method 1: Using uvicorn (Recommended)

```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"

# Set OpenAI API key (if using OpenAI backend)
export OPENAI_API_KEY="your-key-here"
# OR configure ~/.genspark_llm.yaml (see below)

# Start service
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Method 2: With nohup (Background)

```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"
nohup uvicorn app:app --host 0.0.0.0 --port 8000 > /tmp/ai_sme_rag.log 2>&1 &
```

### Method 3: With PM2 (Production)

```bash
cd /home/user/webapp/DueDiligenceBackend
pm2 start "AI SME/app.py" --name ai-sme --interpreter python3 -- -m uvicorn app:app --host 0.0.0.0 --port 8000
```

---

## 🔑 OpenAI Configuration

### Option 1: Config File

Create `~/.genspark_llm.yaml`:
```yaml
openai:
  api_key: gsk-xxxxxxxxxxxxxxxxxxxxx
  base_url: https://www.genspark.ai/api/llm_proxy/v1
```

### Option 2: Environment Variable

```bash
export OPENAI_API_KEY="your-key-here"
export OPENAI_BASE_URL="https://www.genspark.ai/api/llm_proxy/v1"  # optional
```

### Option 3: .env File

Create `.env` in `AI SME/` directory:
```
OPENAI_API_KEY=your-key-here
OPENAI_BASE_URL=https://www.genspark.ai/api/llm_proxy/v1
```

---

## 📊 API Endpoints

### Web UI
```
GET  /                    # Login page
GET  /chat                # Main chat interface
GET  /admin/docs          # Document management
GET  /admin/referrals     # Referral management
GET  /admin/resolutions   # SME resolution management
```

### API Endpoints (for integration)
```
POST /query               # Ask a question
  Form data:
  - query: string (required) - The question
  - task_id: string (optional) - Case reference
  - customer_id: string (optional) - Customer reference
  
  Returns:
  {
    "answer": "...",
    "hits": 3,
    "sources": ["Source_of_Wealth_Guide.pdf"],
    "context_used": [...]
  }

POST /upload              # Upload guidance document
  multipart/form-data:
  - file: file
  - title: string (optional)

GET  /list-docs           # List uploaded documents
POST /delete-doc/{doc_id} # Delete a document

POST /referral            # Create SME referral
  Form data:
  - question: string
  - task_id: string (optional)
  - context: string (optional)

GET  /health              # Health check
```

---

## 🎯 How It Works

### Query Flow

1. **User asks question** → POST /query with question text
2. **Check SME resolutions** → Look for previous approved answers (fast path)
3. **If no resolution found** → Vector search in uploaded documents
4. **Retrieve relevant chunks** → Top K most similar document sections
5. **Build context** → Combine retrieved chunks
6. **Generate answer** → LLM generates from context ONLY
7. **Clean response** → Remove citations, return clean answer
8. **If insufficient guidance** → Return fallback message

### Example Flow

**Question**: "What is the threshold for enhanced due diligence?"

**Step 1**: Search vector database for similar content
```
Found 3 chunks from "Source_of_Wealth_Guide.pdf"
```

**Step 2**: Build prompt
```
System: Answer ONLY from the Guidance text provided.
Guidance: [Retrieved chunks about EDD thresholds]
Question: What is the threshold for enhanced due diligence?
```

**Step 3**: LLM generates answer
```
"Enhanced due diligence is required for transactions exceeding £10,000 
or when the customer is classified as high-risk. This includes PEPs, 
customers from high-risk jurisdictions, and complex beneficial ownership 
structures."
```

**Step 4**: Return to user
```json
{
  "answer": "Enhanced due diligence is required...",
  "hits": 3,
  "sources": ["Source_of_Wealth_Guide.pdf"]
}
```

---

## 📋 Insufficient Guidance Response

**If the uploaded documents don't contain relevant information:**

**User Question**: "What is the capital of France?"

**System Response**:
```
"I am not able to confirm based on the current guidance. This has been 
raised as a referral for further review and a response will be provided 
as soon as possible."
```

**This ensures the AI never makes up answers or uses general knowledge!**

---

## 📤 Uploading Documents

### Via Web UI
1. Navigate to `http://localhost:8000/admin/docs`
2. Click "Upload Document"
3. Select PDF, DOCX, TXT, MD, or CSV file
4. Optional: Set custom title
5. Click "Upload"

### Via API
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@/path/to/document.pdf" \
  -F "title=My Guidance Document"
```

### What Happens
1. File is uploaded to `data/` directory
2. Text is extracted (PDF, DOCX, etc.)
3. Text is split into chunks (900 chars, 150 overlap)
4. Chunks are embedded using sentence-transformers
5. Embeddings stored in ChromaDB vector database
6. SHA-256 hash computed to prevent duplicates

---

## 🔄 SME Resolutions

### What Are Resolutions?
When a question can't be answered from guidance, it's referred to an SME. The SME reviews and provides an approved answer. This answer is stored as a "resolution" and can be reused for similar future questions.

### How It Works
1. **Question asked** → No guidance found → Referral created
2. **SME reviews** → Provides approved answer
3. **Resolution stored** → Answer + metadata saved to ChromaDB
4. **Future queries** → Similar questions get instant SME-approved answers

### Adding Resolutions (Via API)
```bash
curl -X POST http://localhost:8000/admin/sme-resolution \
  -F "question=What are the PEP screening requirements?" \
  -F "answer=PEP screening must be performed using..." \
  -F "approved_by=john.smith@scrutinise.co.uk" \
  -F "ticket_id=SME-2026-001"
```

---

## 🧪 Testing the Service

### Test 1: Health Check
```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

**Expected**:
```json
{
  "status": "ok",
  "llm_backend": "openai",
  "bot_name": "Assistant",
  "auto_yes_ms": 30000
}
```

### Test 2: Query with Guidance
```bash
curl -s -X POST http://localhost:8000/query \
  -F "query=What is source of wealth?" \
  -F "task_id=TEST-001" | python3 -m json.tool
```

**Expected**: Answer based on uploaded guidance documents

### Test 3: Query without Guidance
```bash
curl -s -X POST http://localhost:8000/query \
  -F "query=What is the capital of Zimbabwe?" \
  -F "task_id=TEST-002" | python3 -m json.tool
```

**Expected**:
```json
{
  "answer": "I am not able to confirm based on the current guidance. This has been raised as a referral for further review and a response will be provided as soon as possible.",
  "hits": 0,
  "sources": []
}
```

---

## 🔍 Verifying Document-Only Responses

### Check Uploaded Documents
```bash
curl -s http://localhost:8000/list-docs | python3 -m json.tool
```

### Check Vector Database
```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"
python3 << 'EOF'
from rag import RAGStore
store = RAGStore()
docs = store.list_docs()
print(f"Total documents: {len(docs)}")
for doc in docs:
    print(f"- {doc['title']}: {doc['chunks']} chunks")
EOF
```

### Test Query
Ask a question about content in the uploaded documents. The answer should be accurate and based on the documents.

Ask a question NOT in the documents. You should get the fallback message.

---

## 🛠️ Troubleshooting

### Issue 1: "No such module: chromadb"
**Solution**: Install dependencies
```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"
pip3 install -r requirements.txt
```

### Issue 2: "OPENAI_API_KEY not set"
**Solution**: Configure API key (see Configuration section)

### Issue 3: Service won't start
**Solution**: Check logs and dependencies
```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"
python3 app.py  # Run directly to see errors
```

### Issue 4: Answers are generic/not from documents
**Solution**: Check system prompt in settings.py and verify documents are uploaded

### Issue 5: "Model not found" error
**Solution**: 
- If using OpenAI: Check API key and model name
- If using Ollama: Start Ollama and pull model
  ```bash
  ollama serve
  ollama pull llama3.1
  ```

---

## 📈 Advantages of This System

### vs. Simple ChatGPT Integration
| Feature | Simple ChatGPT | RAG System |
|---------|---------------|------------|
| Knowledge Source | General training data | ONLY your documents |
| Answer Accuracy | May hallucinate | Grounded in guidance |
| Compliance | Risky (uncontrolled) | Safe (document-only) |
| Customization | Limited | Full control |
| Auditability | Difficult | Complete (source tracking) |
| Cost | Per-token | Optimized (retrieval first) |

### Key Benefits
1. ✅ **No Hallucinations**: Only answers from your documents
2. ✅ **Compliance**: Ensures regulatory adherence
3. ✅ **Auditability**: Track which documents were used
4. ✅ **Customizable**: Upload your own guidance
5. ✅ **Resolution Reuse**: SME answers saved for future
6. ✅ **Fallback Safety**: Clear message when uncertain

---

## 🔄 Integration with Due Diligence Module

The AI SME service integrates with the Due Diligence module:

### Shared Authentication
Uses the same `scrutinise_workflow.db` database for user authentication.

### Referral Flow
1. Reviewer asks question in Review Panel
2. AI SME checks guidance documents
3. If insufficient → Creates referral
4. SME reviews and answers
5. Answer saved as resolution
6. Future similar questions get instant answers

### API Integration
The simple `ai_sme_service.py` (port 8000) was a basic wrapper. 
**Replace it with the full RAG system** for proper document-based responses.

---

## 📝 Current Status

### What Exists
✅ Complete RAG system in `AI SME/` directory
✅ ChromaDB vector database with uploaded documents
✅ Document-only system prompt configured
✅ SME resolution support
✅ Web UI for document/referral management
✅ API endpoints ready

### What's Needed
⏳ Configure OpenAI API key
⏳ Start the service (uvicorn)
⏳ Test with queries
⏳ Upload additional guidance documents as needed
⏳ Train team on using the system

---

## 🎯 Next Steps

### 1. Configure API Key
```bash
# Create config file
cat > ~/.genspark_llm.yaml << 'EOF'
openai:
  api_key: your-key-here
  base_url: https://www.genspark.ai/api/llm_proxy/v1
EOF
```

### 2. Start Service
```bash
cd /home/user/webapp/DueDiligenceBackend/"AI SME"
uvicorn app:app --host 0.0.0.0 --port 8000
```

### 3. Test
```bash
# Health check
curl http://localhost:8000/health

# List documents
curl http://localhost:8000/list-docs

# Ask question
curl -X POST http://localhost:8000/query -F "query=What is EDD?"
```

### 4. Upload More Guidance
Access web UI at `http://localhost:8000/admin/docs` and upload your compliance guidance documents.

---

## 📚 Related Files

### Core Files
- `AI SME/app.py` - Main application
- `AI SME/rag.py` - RAG pipeline (retrieval + generation)
- `AI SME/llm.py` - LLM client
- `AI SME/settings.py` - Configuration

### Data Files
- `AI SME/data/` - Uploaded documents
- `AI SME/chroma/` - Vector database (persistent)

### Old Files (Can be removed)
- `/home/user/webapp/DueDiligenceBackend/ai_sme_service.py.backup` - Simple service (replaced)

---

## Status
✅ **RAG System Exists** - Complete document-based AI SME system ready
⏳ **Configuration Needed** - Add OpenAI API key to enable
⏳ **Service Start Needed** - Run uvicorn to start service
✅ **Documents Uploaded** - 2 PDF guidance documents already in system

**Recommendation**: Use the existing RAG system instead of building a new one!
