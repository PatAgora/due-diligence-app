#!/usr/bin/env python3
"""
AI SME Service with OpenAI Integration
Uses OpenAI API to answer compliance questions
"""

from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional

app = FastAPI(title="AI SME Service")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI API Key
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY_HERE"

# Load guidance documents from data directory
GUIDANCE_DOCS = []
def load_guidance_documents():
    """Load all PDF documents from AI SME/data directory"""
    import os
    from pathlib import Path
    
    guidance_dir = Path(__file__).parent / "AI SME" / "data"
    if not guidance_dir.exists():
        print(f"Warning: Guidance directory not found: {guidance_dir}")
        return []
    
    docs = []
    for pdf_file in guidance_dir.glob("*.pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(pdf_file))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            docs.append({
                "title": pdf_file.name,
                "content": text
            })
            print(f"✅ Loaded: {pdf_file.name}")
        except Exception as e:
            print(f"Error loading {pdf_file.name}: {e}")
    
    return docs

# Load guidance on startup
print("Loading guidance documents...")
GUIDANCE_DOCS = load_guidance_documents()
print(f"✅ Loaded {len(GUIDANCE_DOCS)} guidance documents")

def search_guidance(question: str) -> str:
    """
    Simple keyword-based search in guidance documents
    Returns relevant context from documents
    """
    if not GUIDANCE_DOCS:
        return ""
    
    # Extract keywords from question
    import re
    words = re.findall(r'\b\w{3,}\b', question.lower())
    
    # Common stop words to ignore
    stop_words = {'what', 'when', 'where', 'which', 'who', 'how', 'the', 'is', 'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'can', 'may', 'might', 'must'}
    keywords = [w for w in words if w not in stop_words]
    
    if not keywords:
        return ""
    
    # Search for relevant chunks in documents
    relevant_chunks = []
    for doc in GUIDANCE_DOCS:
        content = doc['content'].lower()
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        # Score each paragraph based on keyword matches
        for para in paragraphs:
            if len(para) < 50:  # Skip very short paragraphs
                continue
            
            matches = sum(1 for kw in keywords if kw in para)
            if matches > 0:
                relevant_chunks.append({
                    'text': para,
                    'score': matches,
                    'source': doc['title']
                })
    
    # Sort by relevance and take top 5
    relevant_chunks.sort(key=lambda x: x['score'], reverse=True)
    top_chunks = relevant_chunks[:5]
    
    if not top_chunks:
        return ""
    
    # Build context from top chunks
    context_parts = []
    for i, chunk in enumerate(top_chunks, 1):
        context_parts.append(f"[From {chunk['source']}]\n{chunk['text']}")
    
    return "\n\n---\n\n".join(context_parts)

def get_openai_response(question: str, context: str = "") -> str:
    """Get response from OpenAI - DOCUMENT ONLY MODE"""
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # CRITICAL: Only answer from provided guidance
        system_prompt = """You are a cautious guidance assistant. Answer ONLY from the Guidance text provided below.

CRITICAL RULES:
- If the guidance contains the answer, provide it concisely
- Do NOT use any knowledge outside the provided guidance
- Do NOT make assumptions or inferences beyond what's in the guidance  
- Do NOT include citations, document titles, or source markers like [1], [Source: ...], etc.
- If the guidance is insufficient, reply EXACTLY with: "I am not able to confirm based on the current guidance. This has been raised as a referral for further review and a response will be provided as soon as possible."

Give only the answer, nothing else."""

        # Build prompt with guidance context
        if context:
            user_prompt = f"Guidance:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        else:
            # No guidance provided - return fallback
            return "I am not able to confirm based on the current guidance. This has been raised as a referral for further review and a response will be provided as soon as possible."
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,  # Low temperature for factual responses
            max_tokens=500
        )
        
        answer = response.choices[0].message.content.strip()
        
        # Remove any citations or source markers
        import re
        answer = re.sub(r'\s*\[\d+\]\s*$', '', answer)
        answer = re.sub(r'\s*\[(?:source|reviewer|guidance|doc|ref).*?\]\s*$', '', answer, flags=re.I)
        
        return answer
        
    except Exception as e:
        print(f"OpenAI Error: {str(e)}")
        return f"Error: {str(e)}"

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "llm_backend": "openai-rag",
        "bot_name": "Assistant",
        "auto_yes_ms": 30000,
        "message": f"AI SME service is online (Document-only RAG mode - {len(GUIDANCE_DOCS)} documents loaded)",
        "documents_loaded": len(GUIDANCE_DOCS)
    }

@app.post("/query")
async def query(
    query: str = Form(...),
    task_id: Optional[str] = Form(None),
    customer_id: Optional[str] = Form(None),
    context: Optional[str] = Form(None)
):
    """Handle queries - DOCUMENT ONLY MODE"""
    
    print(f"[QUERY] Question: {query}")
    
    # Search guidance documents for relevant context
    guidance_context = search_guidance(query)
    
    print(f"[QUERY] Found guidance context: {len(guidance_context)} chars")
    
    # Get OpenAI response with guidance context
    answer = get_openai_response(query, guidance_context)
    
    # Determine if we had guidance
    has_guidance = len(guidance_context) > 0
    
    return {
        "status": "success",
        "answer": answer,
        "hits": 1 if has_guidance else 0,
        "sources": [doc['title'] for doc in GUIDANCE_DOCS] if has_guidance else [],
        "context_used": ["Document-based answer"] if has_guidance else [],
        "mode": "document-only-rag"
    }
    
    return {
        "status": "success",
        "answer": answer,
        "hits": 1,
        "sources": ["OpenAI GPT-3.5"],
        "context_used": [],
        "mode": "openai"
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
        "message": "Referral created successfully",
        "referral_id": f"REF-{task_id or 'UNKNOWN'}"
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
        "message": "Feedback received"
    }

if __name__ == "__main__":
    print("🚀 Starting AI SME Service with OpenAI on http://localhost:8000")
    print("🔑 Using OpenAI API Key")
    print("✨ Service ready!\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
