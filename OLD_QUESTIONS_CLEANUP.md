# 🗑️ Old Stock Questions Cleanup

**Date:** 2026-01-09  
**Issue:** Two old AI cases (CUST021, CUST022) still contained outdated stock questions

---

## 🔍 **Problem Identified**

When navigating to AI Outreach for any customer, the system was showing old hardcoded questions:
- ❌ "Can you explain the transactions to high-risk countries for {customer_id}?"
- ❌ "Please provide details about the cash transactions for {customer_id}?"

These were from **old AI cases in the database** (Case 13 and Case 14) created before the question update.

---

## 🗑️ **Data Removed**

### **Case 13 (CUST021)**
- Created: 2025-10-01
- Questions deleted:
  - Q101: [HIGH_RISK_COUNTRY] "Can you explain the transactions to high-risk countries for CUST021?"
  - Q102: [CASH_DAILY_BREACH] "Please provide details about the cash transactions for CUST021."

### **Case 14 (CUST022)**
- Created: 2025-10-02
- Questions deleted:
  - Q100: [NLP_RISK] "Please clarify the transaction narrative..."

### **Summary**
- ✅ Deleted: **2 AI cases**
- ✅ Deleted: **3 old questions**
- ✅ Database now clean: **0 AI cases, 0 questions**

---

## ✅ **New Behavior**

**When "Prepare Questions" is clicked for ANY customer:**

The system will now generate the **NEW updated questions** (hardcoded in app.py lines 15238-15242):

1. **PROHIBITED_COUNTRY**  
   "Can you explain the transaction of £2,011.43 on 23/12/2025?"

2. **PATTERN_CHANGE**  
   "Can you explain why the transaction of £1,694.71 into your account came from a different country to normal?"

3. **HIGH_VALUE**  
   "What is the purpose of the below transactions; £4,220.71 on 20/12/2025, £4,723.43 on 11/11/2025"

---

## 🧪 **Testing**

### **How to Verify**

1. Navigate to **any customer** in Transaction Review (CUST021, CUST022, or CUST2002)
2. Click **AI Outreach** in the sidebar
3. Click **"Prepare Questions"**
4. ✅ **Verify:** Should show the **3 NEW questions** above
5. ✅ **Verify:** Should NOT show old cash/high-risk country questions

### **Customers to Test**
- **CUST021** - Previously had old questions (now clean)
- **CUST022** - Previously had old questions (now clean)
- **CUST2002** - Already reset in previous step (clean)

---

## 📊 **Database Impact**

### **Tables Modified**
- `ai_cases` - Deleted 2 rows
- `ai_answers` - Deleted 3 rows

### **Database State**
```
BEFORE:
- ai_cases: 2 rows (Case 13, Case 14)
- ai_answers: 3 rows (Q100, Q101, Q102)

AFTER:
- ai_cases: 0 rows
- ai_answers: 0 rows
```

---

## 🔄 **What Happens Next**

1. **First "Prepare Questions" click** for any customer → Creates new AI case with 3 NEW questions
2. **Subsequent visits** → Shows saved questions (NEW format)
3. **Backend code** (app.py lines 15238-15242) → Always generates NEW question format

---

## 📝 **Related Changes**

- **Previous:** Updated hardcoded questions in backend (commit d576c8e)
- **Previous:** Reset CUST2002 AI sections (commit 32f8f10)
- **Current:** Removed old questions from database (commit 2249aac)

---

## ✅ **Status: Complete**

All old stock questions have been removed from the database. The system will now only generate the updated questions based on actual transaction alerts.

**Git:** https://github.com/PatAgora/due-diligence-app  
**Commit:** 2249aac - "Remove Old Stock Questions from Database"
