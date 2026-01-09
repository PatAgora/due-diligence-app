#!/usr/bin/env python3
"""
AI SME Service - Document-Only RAG
Only answers questions from uploaded guidance documents
"""

from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional
import os
import chromadb
from openai import OpenAI

app = FastAPI(title="AI SME Service - Document Only")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY_HERE")
client = OpenAI(api_key=OPENAI_API_KEY)

# ChromaDB setup
CHROMA_DIR = "AI SME/chroma"
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

# System prompt - STRICT document-only answering
SYSTEM_PROMPT = """You are a cautious guidance assistant. Answer ONLY from the Guidance text provided below.

CRITICAL RULES:
- If the guidance contains the answer, provide it concisely
- Do NOT use any knowledge outside the provided guidance
- Do NOT make assumptions or inferences beyond what's in the guidance
- Do NOT include citations, document titles, or source markers like [1], [Source: ...], etc.
- If the guidance is insufficient, reply EXACTLY with: "I am not able to confirm based on the current guidance. This has been raised as a referral for further review and a response will be provided as soon as possible."

Give only the answer, nothing else."""

def get_relevant_documents(question: str, top_k: int = 5) -> tuple:
    """
    Search ChromaDB for relevant documents
    Returns: (documents, has_results)
    """
    try:
        # Try to get the main collection
        collection = chroma_client.get_collection(name="guidance")
        
        # Search for relevant chunks
        results = collection.query(
            query_texts=[question],
            n_results=top_k
        )
        
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        
        if documents:
            return (documents, True, metadatas)
        else:
            return ([], False, [])
            
    except Exception as e:
        print(f"ChromaDB Error: {str(e)}")
        return ([], False, [])

def get_answer(question: str, documents: list) -> str:
    """
    Generate answer using OpenAI, strictly from provided documents
    """
    try:
        if not documents:
            # No documents found - return fallback message
            return "I am not able to confirm based on the current guidance. This has been raised as a referral for further review and a response will be provided as soon as possible."
        
        # Build context from retrieved documents
        context = "\n\n---\n\n".join(documents)
        
        # Build prompt with strict instructions
        prompt = f"""{SYSTEM_PROMPT}

Guidance:
{context}

Question: {question}

Answer:"""
        
        # Get OpenAI response
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Guidance:\n{context}\n\nQuestion: {question}\n\nAnswer:"}
            ],
            temperature=0.2,  # Low temperature for more factual responses
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
        return f"Error generating answer: {str(e)}"

@app.get("/health")
async def health():
    """Health check"""
    try:
        # Check if ChromaDB is accessible
        collection = chroma_client.get_collection(name="guidance")
        doc_count = collection.count()
        
        return {
            "status": "ok",
            "llm_backend": "openai-rag",
            "bot_name": "Assistant",
            "auto_yes_ms": 30000,
            "message": f"AI SME service is online (Document-only RAG mode)",
            "documents_loaded": doc_count
        }
    except Exception as e:
        return {
            "status": "ok",
            "llm_backend": "openai-rag",
            "bot_name": "Assistant",
            "auto_yes_ms": 30000,
            "message": "AI SME service is online (no documents loaded yet)",
            "documents_loaded": 0,
            "error": str(e)
        }

@app.post("/query")
async def query(
    query: str = Form(...),
    task_id: Optional[str] = Form(None),
    customer_id: Optional[str] = Form(None),
    context: Optional[str] = Form(None)
):
    """
    Handle queries - ONLY from uploaded documents
    """
    
    print(f"[QUERY] Question: {query}")
    
    # Search for relevant documents
    documents, has_results, metadatas = get_relevant_documents(query, top_k=5)
    
    print(f"[QUERY] Found {len(documents)} relevant chunks")
    
    # Generate answer from documents only
    answer = get_answer(query, documents)
    
    # Extract source titles
    sources = []
    if metadatas:
        for meta in metadatas:
            title = meta.get("title", "") or meta.get("source", "")
            if title and title not in sources:
                sources.append(title)
    
    return {
        "status": "success",
        "answer": answer,
        "hits": len(documents),
        "sources": sources,
        "context_used": metadatas if metadatas else []
    }

@app.post("/referral")
async def referral(
    reason: str = Form(""),
    question: str = Form(""),
    answer: str = Form(""),
    task_id: Optional[str] = Form(None)
):
    """Handle referral submission"""
    # For now, just acknowledge
    return {
        "status": "success",
        "message": "Referral submitted for SME review",
        "referral_id": f"REF-{task_id or 'UNKNOWN'}"
    }

@app.post("/feedback")
async def feedback(
    query_id: Optional[str] = Form(None),
    rating: Optional[str] = Form(None),
    feedback: Optional[str] = Form(None)
):
    """Handle feedback submission"""
    # For now, just acknowledge
    return {
        "status": "success",
        "message": "Feedback received"
    }

if __name__ == "__main__":
    print("\n" + "="*60)
    print("AI SME Service - Document-Only RAG Mode")
    print("="*60)
    print("✅ Only answers from uploaded guidance documents")
    print("✅ No general knowledge responses")
    print("✅ Strict fallback when guidance is insufficient")
    print("="*60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
