#!/usr/bin/env python3
"""
Simple AI SME Mock Service - Returns "online" status and mock responses
This allows the frontend to show as "online" while we configure the full RAG system
"""

from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional

app = FastAPI(title="AI SME Mock Service")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    """Health check - returns online status"""
    return {
        "status": "ok",
        "llm_backend": "mock",
        "bot_name": "Assistant",
        "auto_yes_ms": 30000,
        "message": "AI SME service is online (mock mode - configure RAG system for full functionality)"
    }

@app.post("/query")
async def query(
    query: str = Form(...),
    task_id: Optional[str] = Form(None),
    customer_id: Optional[str] = Form(None),
    context: Optional[str] = Form(None)
):
    """Handle queries - returns message to configure the full system"""
    return {
        "status": "success",
        "answer": "AI SME is online but needs to be configured with the RAG system and OpenAI API key to answer from your uploaded guidance documents. Please see the AI_SME_RAG_SYSTEM_GUIDE.md for setup instructions.",
        "hits": 0,
        "sources": [],
        "context_used": [],
        "mode": "mock"
    }

@app.post("/referral")
async def referral(
    question: str = Form(...),
    task_id: Optional[str] = Form(None),
    customer_id: Optional[str] = Form(None),
    context: Optional[str] = Form(None)
):
    """Handle referrals"""
    return {
        "status": "success",
        "message": "Referral created (mock mode)",
        "referral_id": f"REF-MOCK-{task_id or 'UNKNOWN'}"
    }

@app.post("/feedback")
async def feedback(
    query_id: Optional[str] = Form(None),
    rating: Optional[str] = Form(None),
    feedback: Optional[str] = Form(None)
):
    """Handle feedback"""
    return {
        "status": "success",
        "message": "Feedback received (mock mode)"
    }

if __name__ == "__main__":
    print("🚀 Starting AI SME Mock Service on http://localhost:8000")
    print("📝 This is a mock service - status will show as 'online'")
    print("⚠️  To enable full RAG functionality:")
    print("   1. Configure OpenAI API key")
    print("   2. Use the full RAG system in 'AI SME/' directory")
    print("   3. See AI_SME_RAG_SYSTEM_GUIDE.md for details")
    print("\n✨ Service ready!\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
