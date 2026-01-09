# 🤖 AI-Powered Outreach Question Generation

**Date:** 2026-01-09  
**Feature:** LLM-based question generation for Transaction Review AI Outreach

---

## 🎯 **Overview**

The AI Outreach feature now uses **OpenAI GPT-4** to automatically generate specific, relevant questions based on actual transaction alerts for each customer.

### **Before (Hardcoded):**
```
❌ Same 3 questions for every customer
❌ Generic references (£2,011.43, 23/12/2025)
❌ Not based on actual alerts
❌ Cash questions even when no cash transactions
```

### **After (AI-Generated):**
```
✅ Unique questions for each customer
✅ References actual transaction dates/amounts
✅ Based on real alert reasons and severity
✅ Intelligent grouping of similar alerts
✅ Professional compliance language
```

---

## 🔄 **How It Works**

### **User Flow:**
1. Navigate to **Transaction Review → AI Outreach**
2. Click **"Prepare Questions"** button
3. System generates questions (takes 2-5 seconds)
4. 3-5 specific questions appear in the table
5. User can answer questions and run assessment

### **Backend Process:**

```
[User Clicks Button]
        ↓
[Fetch Transaction Alerts]
  - Query database for customer alerts
  - Filter by date period (3m, 6m, 12m)
  - Get top 10 alerts by severity/score
        ↓
[Build AI Prompt]
  - Format alert details (dates, amounts, reasons)
  - Include severity levels (CRITICAL/HIGH/MEDIUM)
  - Add professional compliance guidelines
        ↓
[Call OpenAI GPT-4 API]
  - Send prompt with alert data
  - Request JSON response format
  - Generate 3-5 specific questions
        ↓
[Parse & Validate Response]
  - Extract JSON from response
  - Validate question structure
  - Ensure each has 'tag' and 'question'
        ↓
[Store Questions in Database]
  - Save to ai_answers table
  - Link to AI case for customer
  - Return success message
        ↓
[Display Questions to User]
```

---

## 📊 **Alert Data Analyzed**

The LLM receives detailed information about each alert:

```python
Alert 1:
- Transaction ID: TX316091
- Date: 23/12/2025
- Amount: GBP 2011.43
- Country: IR (Iran)
- Direction: outgoing
- Severity: CRITICAL (Score: 100)
- Reasons: Transaction to PROHIBITED jurisdiction (Iran) | 
           IMMEDIATE ESCALATION REQUIRED | 
           Potential sanctions violation
- Rule Tags: SANCTIONS, HIGH_RISK_COUNTRY

Alert 2:
- Transaction ID: TX000022
- Date: 20/12/2025
- Amount: GBP 4220.71
- Country: ES (Spain)
- Direction: outgoing
- Severity: HIGH (Score: 92)
- Reasons: Transaction amount exceeds £3,000 | 
           Requires enhanced due diligence
- Rule Tags: HIGH_VALUE
```

---

## 🧠 **AI Prompt Design**

### **System Prompt:**
```
You are a financial crime compliance analyst creating customer outreach 
questions for transaction alerts.
```

### **User Prompt Structure:**
```
CUSTOMER ID: CUST2002

TRANSACTION ALERTS:
[Detailed alert data as shown above]

TASK:
Generate 3-5 specific, professional questions...

IMPORTANT GUIDELINES:
- Prioritize CRITICAL and HIGH severity alerts
- Group similar alerts
- Be specific with dates and amounts
- Don't be accusatory - remain professional
- Focus on business purpose and legitimacy

OUTPUT FORMAT (JSON):
[{"tag": "PROHIBITED_COUNTRY", "question": "..."}]
```

---

## 💡 **Example Outputs**

### **CUST2002 (4 Alerts)**

**Alerts:**
1. £2,011.43 to Iran (CRITICAL - Sanctions)
2. £4,220.71 high-value (HIGH)
3. £4,723.43 high-value (HIGH)
4. £1,694.71 pattern change (HIGH)

**AI-Generated Questions:**
```json
[
  {
    "tag": "PROHIBITED_COUNTRY",
    "question": "Can you explain the transaction of £2,011.43 on 23/12/2025 to Iran? This transaction requires immediate review due to potential sanctions concerns. Please provide supporting documentation and business justification."
  },
  {
    "tag": "HIGH_VALUE",
    "question": "What was the purpose of the following high-value transactions: £4,220.71 on 20/12/2025 and £4,723.43 on 11/11/2025? Please provide invoices or contracts supporting these payments."
  },
  {
    "tag": "PATTERN_CHANGE",
    "question": "Can you explain why the transaction of £1,694.71 on 30/12/2025 differs from your normal account activity pattern? What changed in your business operations?"
  }
]
```

---

## 🛡️ **Fallback Logic**

If the LLM API fails (network issue, API key problem, etc.), the system uses **rule-based question generation**:

### **Fallback Rules:**
1. **Prohibited/Sanctions keywords** → Sanctions question
2. **High-value/Exceeds keywords** → Enhanced due diligence question (groups similar alerts)
3. **Pattern/Unusual keywords** → Pattern change question
4. **Cash keywords** → Cash transaction question
5. **Default** → Generic transaction inquiry

### **Fallback Example:**
```python
# If API fails for CUST2002
fallback_questions = [
  {
    "tag": "PROHIBITED_COUNTRY",
    "question": "Can you explain the transaction of GBP2011.43 on 2025-12-23? Please provide supporting documentation and business justification for this payment."
  },
  {
    "tag": "HIGH_VALUE",
    "question": "What is the purpose of the following high-value transactions: GBP4220.71 on 2025-12-20, GBP4723.43 on 2025-11-11?"
  }
]
```

---

## 🔧 **Technical Implementation**

### **Key Functions:**

#### **1. generate_ai_outreach_questions()**
```python
def generate_ai_outreach_questions(customer_id, alerts):
    """
    Generate AI Outreach questions using OpenAI GPT.
    
    Args:
        customer_id: Customer ID
        alerts: List of alert records from database
    
    Returns:
        List of dicts with 'tag' and 'question' keys
    """
    # Load OpenAI config from ~/.genspark_llm.yaml
    # Format alerts for LLM
    # Create detailed prompt
    # Call OpenAI API (GPT-4)
    # Parse JSON response
    # Validate and return questions
```

#### **2. generate_fallback_questions()**
```python
def generate_fallback_questions(alerts):
    """
    Generate simple fallback questions if LLM fails.
    Uses rule-based logic based on alert severity and reasons.
    """
    # Sort alerts by severity
    # Analyze alert reasons (keywords)
    # Generate questions based on rules
    # Group similar alerts
    # Return structured questions
```

### **API Endpoint Modified:**

**Route:** `POST /api/transaction/ai?action=build`

**Before:**
```python
# Hardcoded questions
sample_questions = [
    {"tag": "PROHIBITED_COUNTRY", "question": "Can you explain the transaction of £2,011.43..."},
    ...
]
```

**After:**
```python
# Fetch alerts
alerts = cur.execute("""
    SELECT a.*, t.*
    FROM alerts a
    JOIN transactions t ON t.id = a.txn_id
    WHERE t.customer_id = ?
    ORDER BY a.score DESC
""").fetchall()

# Generate questions using AI
try:
    generated_questions = generate_ai_outreach_questions(customer_id, alerts)
except:
    generated_questions = generate_fallback_questions(alerts)
```

---

## 🔑 **Configuration Requirements**

### **OpenAI API Key:**

**File:** `~/.genspark_llm.yaml`

```yaml
openai:
  api_key: sk-proj-...
  base_url: https://api.openai.com/v1
```

### **Dependencies:**
```bash
pip install openai pyyaml
```

### **Environment Variables (Alternative):**
```bash
export OPENAI_API_KEY="sk-proj-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

---

## 📈 **Benefits**

| Aspect | Before (Hardcoded) | After (AI-Generated) |
|--------|-------------------|----------------------|
| **Relevance** | Generic for all | Specific to customer |
| **Accuracy** | Often wrong dates/amounts | Exact transaction details |
| **Adaptability** | Fixed 3 questions | 3-5 dynamic questions |
| **Intelligence** | None | Groups similar alerts |
| **Professionalism** | Basic | Compliance-grade language |
| **Coverage** | May miss key alerts | Prioritizes by severity |
| **Maintenance** | Manual updates needed | Self-adapting |

---

## 🧪 **Testing Instructions**

### **Test Case 1: CUST2002 (Multiple Alert Types)**

1. Navigate to **Transaction Review → CUST2002**
2. Click **AI Outreach** in sidebar
3. Click **"Prepare Questions"**
4. **Wait 2-5 seconds** (LLM processing)
5. **Verify:**
   - 3-4 questions generated
   - Questions reference Iran transaction (£2,011.43)
   - Questions mention specific dates (23/12/2025, etc.)
   - Questions group high-value transactions together
   - No generic "cash" questions (CUST2002 has no cash alerts)

### **Test Case 2: Customer with No Alerts**

1. Try customer with no alerts in period
2. **Expected:** Error message: "No alerts found for {customer_id}"

### **Test Case 3: LLM Failure (Fallback)**

1. Temporarily break OpenAI config
2. Click "Prepare Questions"
3. **Expected:** Fallback questions generated
4. Questions still relevant but less sophisticated

---

## 🔍 **Monitoring & Debugging**

### **Check Backend Logs:**
```bash
pm2 logs flask-backend --nostream | grep -i "question\|ai\|openai"
```

### **Success Indicators:**
```
✅ Generated 3 AI questions for CUST2002
```

### **Failure Indicators:**
```
❌ Error calling OpenAI API: ...
⚠️ Generated 2 fallback questions (LLM unavailable)
```

### **Database Check:**
```sql
SELECT id, customer_id, created_at 
FROM ai_cases 
WHERE customer_id = 'CUST2002' 
ORDER BY created_at DESC LIMIT 1;

SELECT tag, question 
FROM ai_answers 
WHERE case_id = <case_id>;
```

---

## 🚀 **Future Enhancements**

1. **Customer Profile Context:**
   - Include customer business type, history
   - Reference previous outreach responses
   - Adapt tone based on customer risk level

2. **Multi-Language Support:**
   - Generate questions in customer's language
   - Maintain compliance terminology accuracy

3. **Question Templates:**
   - Allow users to define question templates
   - LLM fills templates with specific data

4. **Learning from Feedback:**
   - Track which questions get good responses
   - Fine-tune prompts based on effectiveness

5. **Smarter Grouping:**
   - Analyze transaction narratives
   - Group by business purpose, not just amount

---

## ⚠️ **Important Notes**

1. **API Costs:** Each question generation costs ~$0.02-$0.05 (GPT-4 pricing)
2. **Response Time:** 2-5 seconds per generation (LLM processing)
3. **Rate Limits:** Respect OpenAI API rate limits
4. **Data Privacy:** Customer data sent to OpenAI API (consider data protection laws)
5. **Fallback Essential:** Always have fallback for reliability

---

## 📝 **Summary**

✅ **Implemented:** AI-powered question generation using GPT-4  
✅ **Replaces:** Hardcoded static questions  
✅ **Benefits:** Specific, relevant, professional questions  
✅ **Fallback:** Rule-based generation if LLM unavailable  
✅ **Testing:** Ready for testing with CUST2002  
✅ **Status:** DEPLOYED to production

**Git Commit:** 244ac23 - "Implement AI-Powered Question Generation for Outreach"  
**GitHub:** https://github.com/PatAgora/due-diligence-app
