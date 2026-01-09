# AI SME ChatGPT Integration - Implementation Guide

## Overview
The AI SME service has been upgraded to use OpenAI's ChatGPT API for intelligent compliance and due diligence assistance. The service provides fallback to mock responses if ChatGPT is not configured.

---

## 🎯 What Changed

### Version Update
- **Before**: v1.0.0 - Mock responses only
- **After**: v2.0.0 - ChatGPT integration with mock fallback

### Key Features Added
1. **ChatGPT Integration**: Real AI-powered responses using GPT-4
2. **Intelligent Fallback**: Automatically uses mock responses if API is unavailable
3. **Configuration Support**: Multiple ways to configure (YAML file or environment variables)
4. **Expert System Prompt**: Specialized in compliance, AML, KYC, sanctions screening
5. **Context Awareness**: Includes task ID, customer ID, and context in prompts

---

## 📂 Files Modified

### 1. `/home/user/webapp/DueDiligenceBackend/ai_sme_service.py`
Complete rewrite with ChatGPT integration:

**Key Changes**:
- Added OpenAI client initialization
- Updated query endpoint to use ChatGPT API
- Added configuration file support (~/.genspark_llm.yaml)
- Updated health check to show LLM backend status
- Enhanced logging and error handling

### 2. `/home/user/webapp/DueDiligenceBackend/requirements.txt`
Added dependency:
```
PyYAML>=6.0.0
```

---

## 🚀 How It Works

### System Architecture

```
User Question
    ↓
AI SME Service (FastAPI)
    ↓
Check Configuration
    ├─ Config file exists? → Load API key
    ├─ Environment vars? → Use env vars
    └─ None found → Use mock responses
    ↓
ChatGPT API (GPT-4)
    ├─ Success → Return AI response
    └─ Error → Fall back to mock responses
    ↓
Return response to user
```

### Query Flow

1. **Receive Query**: User submits question via POST /query
2. **Check Configuration**: Service checks for OpenAI API credentials
3. **Build Context**: Combine task ID, customer ID, and context
4. **Call ChatGPT**: Send to GPT-4 with expert system prompt
5. **Return Response**: Send back AI-generated answer
6. **Fallback**: If ChatGPT fails, use keyword-based mock responses

---

## 🔧 Configuration

### Method 1: Configuration File (Recommended)

**File**: `~/.genspark_llm.yaml`

```yaml
openai:
  api_key: gsk-xxxxxxxxxxxxxxxxxxxxx
  base_url: https://www.genspark.ai/api/llm_proxy/v1
```

**Location**: `/home/user/.genspark_llm.yaml`

### Method 2: Environment Variables

```bash
export OPENAI_API_KEY="gsk-xxxxxxxxxxxxxxxxxxxxx"
export OPENAI_BASE_URL="https://www.genspark.ai/api/llm_proxy/v1"
```

### Method 3: GenSpark UI (Future)

1. Go to **API Keys** tab in GenSpark project
2. Generate a new API key
3. Click **"Inject"** to configure sandbox environment
4. Restart AI SME service

---

## 🎓 System Prompt

The AI SME uses a specialized system prompt:

```
You are an expert compliance and due diligence Subject Matter Expert (SME) specializing in:
- Anti-Money Laundering (AML) regulations
- Know Your Customer (KYC) procedures
- Sanctions screening (OFAC, UN, EU, UK)
- Politically Exposed Persons (PEP) screening
- Risk assessment and mitigation
- Transaction monitoring
- Enhanced Due Diligence (EDD)
- Financial crime prevention

Provide clear, actionable guidance based on industry best practices and regulatory requirements. 
Keep responses concise but comprehensive. If specific documentation or additional information 
is needed, clearly state what is required.
```

---

## 📊 API Endpoints

### Health Check
```bash
GET http://localhost:8000/health
```

**Response**:
```json
{
  "status": "ok",
  "llm_backend": "openai",  // or "mock"
  "bot_name": "AI SME Assistant (ChatGPT)",
  "auto_yes_ms": 30000,
  "service": "AI SME Service with ChatGPT",
  "version": "2.0.0",
  "openai_enabled": true  // or false
}
```

### Query AI SME
```bash
POST http://localhost:8000/query
Content-Type: multipart/form-data

Fields:
- query: string (required) - The question to ask
- task_id: string (optional) - Case/task identifier
- customer_id: string (optional) - Customer identifier
- context: string (optional) - Additional context
```

**Example Request**:
```bash
curl -X POST http://localhost:8000/query \
  -F "query=What are the red flags for money laundering?" \
  -F "task_id=CASE-2026010" \
  -F "customer_id=CUST-2026009"
```

**Response with ChatGPT**:
```json
{
  "status": "success",
  "response": "When assessing money laundering risk, key red flags include:\n\n1. **Unusual Transaction Patterns**...",
  "query": "What are the red flags for money laundering?",
  "task_id": "CASE-2026010",
  "customer_id": "CUST-2026009",
  "source": "ChatGPT (AI SME)",
  "model": "gpt-4"
}
```

**Response with Mock Fallback**:
```json
{
  "status": "success",
  "response": "Anti-Money Laundering (AML) procedures require...",
  "query": "What are the red flags for money laundering?",
  "task_id": "CASE-2026010",
  "customer_id": "CUST-2026009",
  "source": "AI SME Mock Service (Fallback)",
  "model": "mock"
}
```

### Create Referral
```bash
POST http://localhost:8000/referral
```

### Submit Feedback
```bash
POST http://localhost:8000/feedback
```

---

## 🧪 Testing

### Test 1: Health Check
```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

**Expected**: Status OK, shows backend type (openai or mock)

### Test 2: Query Without ChatGPT
```bash
curl -s -X POST http://localhost:8000/query \
  -F "query=What is AML compliance?" \
  -F "task_id=TEST-001" | python3 -m json.tool
```

**Expected**: Mock response, `"model": "mock"`

### Test 3: Query With ChatGPT (After Configuration)
```bash
curl -s -X POST http://localhost:8000/query \
  -F "query=Explain sanctions screening procedures" \
  -F "task_id=TEST-001" \
  -F "context=Customer is in high-risk jurisdiction" | python3 -m json.tool
```

**Expected**: AI-generated response, `"model": "gpt-4"`

---

## 🔍 Verifying Configuration

### Check Service Logs
```bash
tail -20 /tmp/ai_sme.log
```

**With ChatGPT Configured**:
```
✅ Loaded OpenAI config from /home/user/.genspark_llm.yaml
🔑 OpenAI API Key: ********************12345678
🌐 Base URL: https://www.genspark.ai/api/llm_proxy/v1
🚀 Starting AI SME Service with ChatGPT Integration on http://localhost:8000
🤖 LLM Backend: OpenAI ChatGPT
✅ ChatGPT API is configured and ready!
```

**Without ChatGPT**:
```
⚠️  No OpenAI API key found. Using mock responses.
🚀 Starting AI SME Service with ChatGPT Integration on http://localhost:8000
🤖 LLM Backend: Mock Responses (Fallback)
⚠️  ChatGPT API not configured. Using mock responses.
```

### Check Health Endpoint
```bash
curl -s http://localhost:8000/health | grep -E "llm_backend|openai_enabled"
```

**Output**:
```json
"llm_backend": "openai",  // or "mock"
"openai_enabled": true    // or false
```

---

## 🎨 Response Quality Comparison

### Mock Response (Fallback)
```
"Anti-Money Laundering (AML) procedures require customer due diligence, 
ongoing monitoring, and suspicious activity reporting. Key red flags include: 
unusual transaction patterns, high-risk jurisdictions, cash-intensive businesses, 
and transactions inconsistent with customer profile."
```

**Characteristics**:
- Generic, template-based
- Keyword-triggered
- Fixed responses
- No context awareness

### ChatGPT Response (GPT-4)
```
"When assessing money laundering risk in this case, consider these red flags:

1. **Transaction Patterns**: Look for:
   - Rapid movement of funds (layering)
   - Structuring below reporting thresholds
   - Round number transactions
   - No clear business purpose

2. **Customer Behavior**:
   - Reluctance to provide documentation
   - Inconsistent information
   - Unusual activity for customer profile

3. **Jurisdictional Risks**:
   - High-risk or non-cooperative jurisdictions
   - Sanctions-listed countries
   - Tax havens

Given this is Customer CUST-2026009, I recommend:
- Verify source of funds documentation
- Check for PEP status
- Review transaction history for patterns
- Consider Enhanced Due Diligence if warranted

Would you like specific guidance on any of these areas?"
```

**Characteristics**:
- Context-aware (references customer ID)
- Structured and detailed
- Actionable recommendations
- Conversational and helpful
- Tailored to the specific case

---

## 🔄 Enabling ChatGPT (Step-by-Step)

### Option 1: Manual Configuration

**Step 1**: Create config file
```bash
nano ~/.genspark_llm.yaml
```

**Step 2**: Add configuration
```yaml
openai:
  api_key: your-api-key-here
  base_url: https://www.genspark.ai/api/llm_proxy/v1
```

**Step 3**: Save and restart service
```bash
pkill -f ai_sme_service
cd /home/user/webapp/DueDiligenceBackend
nohup python3 ai_sme_service.py > /tmp/ai_sme.log 2>&1 &
```

**Step 4**: Verify
```bash
curl -s http://localhost:8000/health | grep openai_enabled
```

### Option 2: Environment Variables

**Step 1**: Set variables
```bash
export OPENAI_API_KEY="your-api-key-here"
export OPENAI_BASE_URL="https://www.genspark.ai/api/llm_proxy/v1"
```

**Step 2**: Restart service
```bash
pkill -f ai_sme_service
cd /home/user/webapp/DueDiligenceBackend
nohup python3 ai_sme_service.py > /tmp/ai_sme.log 2>&1 &
```

---

## 📈 Benefits

### For Users
1. **Better Answers**: AI-powered responses tailored to specific cases
2. **Context Awareness**: Considers task details and customer information
3. **Consistent Quality**: Professional, well-structured guidance
4. **24/7 Availability**: Instant expert assistance anytime

### For System
1. **Graceful Degradation**: Falls back to mock if API unavailable
2. **Easy Configuration**: Multiple config methods
3. **Cost Monitoring**: Uses GPT-4 efficiently (1000 token max)
4. **Error Handling**: Comprehensive error catching and logging

---

## 🛠️ Troubleshooting

### Issue 1: "openai_enabled": false

**Cause**: API key not configured

**Solution**:
1. Check config file: `cat ~/.genspark_llm.yaml`
2. Check environment: `echo $OPENAI_API_KEY`
3. Add configuration using one of the methods above
4. Restart service

### Issue 2: "ChatGPT API error" in logs

**Possible Causes**:
- Invalid API key
- Network connectivity issue
- Rate limiting
- Invalid base URL

**Solution**:
1. Check logs: `tail -50 /tmp/ai_sme.log`
2. Verify API key is correct
3. Test base URL: `curl -I https://www.genspark.ai/api/llm_proxy/v1`
4. Service falls back to mock automatically

### Issue 3: Service not starting

**Solution**:
```bash
# Check if port is in use
lsof -i :8000

# Kill existing process
pkill -f ai_sme_service

# Check logs for errors
cat /tmp/ai_sme.log

# Start service manually to see errors
cd /home/user/webapp/DueDiligenceBackend
python3 ai_sme_service.py
```

---

## 📝 Current Status

### Service Status
- ✅ Service running on http://localhost:8000
- ✅ Health check passing
- ✅ Endpoints functional
- ⚠️  ChatGPT not configured (using mock fallback)

### Configuration Status
- ❌ ~/.genspark_llm.yaml not found
- ❌ OPENAI_API_KEY not set
- ❌ OPENAI_BASE_URL not set

### Testing Results
```bash
$ curl -s http://localhost:8000/health | jq '.openai_enabled'
false

$ curl -s -X POST http://localhost:8000/query -F "query=Test" | jq '.source'
"AI SME Mock Service (Fallback)"
```

---

## 🎯 Next Steps

### Immediate
1. ✅ AI SME service updated with ChatGPT integration
2. ✅ Service running with mock fallback
3. ✅ Documentation complete

### To Enable ChatGPT
1. ⏳ Configure OpenAI API key (see "Enabling ChatGPT" section)
2. ⏳ Restart AI SME service
3. ⏳ Test with real queries

### Future Enhancements
- [ ] Add streaming responses for real-time feedback
- [ ] Implement caching for common queries
- [ ] Add conversation history/context
- [ ] Integration with vector database for case knowledge
- [ ] Cost tracking and usage analytics

---

## 🌐 Service URLs

- **AI SME Service**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **Frontend**: https://5173-ihzqwl5fhfcbjidc9trwd-c81df28e.sandbox.novita.ai

---

## 📚 Related Documentation

- OpenAI API Docs: https://platform.openai.com/docs
- GenSpark LLM Integration: See `get_external_api_docs` output
- FastAPI Docs: https://fastapi.tiangolo.com

---

## Status
✅ **Implementation Complete** - AI SME service upgraded with ChatGPT integration
⚠️  **Configuration Needed** - Add API key to enable ChatGPT responses

**Current Mode**: Mock fallback (functional, ready for API key)
**Target Mode**: ChatGPT-powered (requires API key configuration)
