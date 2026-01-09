# 🗑️ Remove Proposed Questions Placeholders - Fix Complete

**Date:** 2026-01-09  
**Issue:** Old stock questions showing before "Prepare Questions" clicked

---

## 🔍 **Problem**

When navigating to **AI Outreach** for any customer (CUST021, CUST022, CUST2002), the system was displaying **old stock questions** in the table BEFORE the user clicked "Prepare Questions":

❌ **OLD QUESTIONS SHOWING:**
1. `HIGH_RISK_COUNTRY`: "Can you explain the transactions to high-risk countries for {customer_id}?"
2. `CASH_DAILY_BREACH`: "Please provide details about the cash transactions for {customer_id}."

**User Experience Issue:**
- Users saw irrelevant questions (e.g., cash questions when no cash transactions existed)
- Questions appeared automatically without user action
- Confusing and unprofessional

---

## 🔎 **Root Cause Analysis**

### **Database State**
✅ Database was already clean (0 AI cases, 0 questions) after previous cleanup (commit 2249aac)

### **Backend Issue**
❌ Backend API was returning hardcoded `proposed_questions` when no AI case existed

**Location:** `DueDiligenceBackend/Due Diligence/app.py` (lines 15410-15415)

**Code Before Fix:**
```python
else:
    # Show proposed questions if no case exists
    proposed_questions = [
        {"tag": "HIGH_RISK_COUNTRY", "question": f"Can you explain the transactions to high-risk countries for {customer_id}?"},
        {"tag": "CASH_DAILY_BREACH", "question": f"Please provide details about the cash transactions for {customer_id}."}
    ]
```

### **Frontend Rendering**
Frontend (`TransactionAI.jsx` line 227) used this fallback:
```javascript
const rows = (data?.answers && data.answers.length > 0) ? data.answers : data?.proposed_questions || [];
```

When `data.answers` was empty, it fell back to `data.proposed_questions`, which contained the old stock questions.

---

## ✅ **Solution**

### **Backend Change**

**File:** `DueDiligenceBackend/Due Diligence/app.py`  
**Lines:** 15410-15412

**Code After Fix:**
```python
else:
    # No proposed questions - user must click "Prepare Questions" to generate them
    proposed_questions = []
```

**Result:** Backend now returns an **empty array** for `proposed_questions` when no AI case exists.

---

## 🎯 **New Behavior**

### **Before Clicking "Prepare Questions"**
✅ **No questions displayed**  
✅ Table shows: *"No questions yet. Click **Prepare Questions** to generate them."*  
✅ Clean, professional UI

### **After Clicking "Prepare Questions"**
✅ System generates **3 NEW questions** (from hardcoded template in lines 15238-15242):

1. **PROHIBITED_COUNTRY**  
   "Can you explain the transaction of £2,011.43 on 23/12/2025?"

2. **PATTERN_CHANGE**  
   "Can you explain why the transaction of £1,694.71 into your account came from a different country to normal?"

3. **HIGH_VALUE**  
   "What is the purpose of the below transactions;  
   £4,220.71 on 20/12/2025  
   £4,723.43 on 11/11/2025"

---

## 📊 **Technical Details**

### **API Response Structure**

**GET `/api/transaction/ai?customer_id=CUST2002&period=3m`**

**Before Fix:**
```json
{
  "status": "ok",
  "customer_id": "CUST2002",
  "case": null,
  "answers": [],
  "proposed_questions": [
    {"tag": "HIGH_RISK_COUNTRY", "question": "Can you explain..."},
    {"tag": "CASH_DAILY_BREACH", "question": "Please provide..."}
  ]
}
```

**After Fix:**
```json
{
  "status": "ok",
  "customer_id": "CUST2002",
  "case": null,
  "answers": [],
  "proposed_questions": []
}
```

### **Frontend Rendering Logic**

```javascript
// Line 227 in TransactionAI.jsx
const rows = (data?.answers && data.answers.length > 0) 
  ? data.answers 
  : data?.proposed_questions || [];

// When both answers and proposed_questions are empty:
// rows = [] → table shows "No questions yet" message
```

---

## 🧪 **Testing Instructions**

### **Test Scenario 1: Fresh Customer (No AI Case)**
1. Navigate to **Transaction Review** → Select any customer (CUST021, CUST022, CUST2002)
2. Click **AI Outreach** in sidebar
3. ✅ **Verify:** No questions displayed
4. ✅ **Verify:** Message shows *"No questions yet. Click Prepare Questions to generate them."*
5. Click **"Prepare Questions"** button
6. ✅ **Verify:** 3 NEW questions appear (Iran transaction, pattern change, high value)
7. ✅ **Verify:** NO old cash/high-risk country questions

### **Test Scenario 2: Customer with Existing AI Case**
1. Navigate to a customer that already has an AI case
2. ✅ **Verify:** Saved questions appear immediately
3. ✅ **Verify:** Questions are the NEW format (not old stock questions)

---

## 📦 **Files Modified**

| File | Lines | Change |
|------|-------|--------|
| `DueDiligenceBackend/Due Diligence/app.py` | 15410-15412 | Changed `proposed_questions` from hardcoded array to empty array `[]` |

---

## 🔄 **Related Changes**

### **Previous Fixes**
1. **Commit d576c8e** - Updated hardcoded questions in backend (POST action=build)
2. **Commit 32f8f10** - Reset CUST2002 AI sections
3. **Commit 2249aac** - Removed old AI cases (Case 13, Case 14) from database
4. **Commit c6f1bca** - Documentation: Old Questions Cleanup
5. **Commit f13e58f** - **Current Fix**: Remove proposed questions placeholders

---

## ✅ **Status: Complete**

| Item | Status |
|------|--------|
| Backend fix deployed | ✅ Yes |
| Backend restarted | ✅ Yes (PID 76633) |
| Database clean | ✅ Yes (0 cases, 0 questions) |
| Git committed | ✅ Yes (commit f13e58f) |
| Ready for testing | ✅ Yes |

---

## 🎉 **Summary**

**Problem:** Old stock questions showing before "Prepare Questions" clicked  
**Root Cause:** Backend returning hardcoded `proposed_questions` array  
**Solution:** Changed to empty array `[]`  
**Result:** Clean UI - no questions until user clicks "Prepare Questions"

**Git:** https://github.com/PatAgora/due-diligence-app  
**Commit:** f13e58f - "Remove Proposed Questions Placeholders"  
**Backend:** Restarted and serving updated API responses
