import re
import uuid
import hashlib
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime, timezone, timedelta

import chromadb
from sentence_transformers import SentenceTransformer

from settings import (
    CHROMA_DIR,
    EMBEDDING_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOP_K,
    SYSTEM_PROMPT,
    # Optional (may not exist in older settings.py):
    # QA_COLLECTION_NAME, QA_MIN_SIM, QA_MAX_RESULTS, QA_MAX_AGE_DAYS, SHOW_QA_PROVENANCE_DEFAULT
)

# ---- Backwards-compatible defaults for optional QA settings ----
try:
    from settings import QA_COLLECTION_NAME  # type: ignore
except Exception:
    QA_COLLECTION_NAME = "sme_qna"

try:
    from settings import QA_MIN_SIM  # type: ignore
except Exception:
    QA_MIN_SIM = 0.78  # cosine-ish similarity threshold (1 - distance)

try:
    from settings import QA_MAX_RESULTS  # type: ignore
except Exception:
    QA_MAX_RESULTS = 3

try:
    from settings import QA_MAX_AGE_DAYS  # type: ignore
except Exception:
    QA_MAX_AGE_DAYS = 0  # 0 = no age filter

try:
    from settings import SHOW_QA_PROVENANCE_DEFAULT  # type: ignore
except Exception:
    SHOW_QA_PROVENANCE_DEFAULT = False

from llm import LLMClient


# =========================
# Helpers: I/O + chunking
# =========================
def read_text_from_file(path: Path) -> str:
    """Extract plain text from supported file types."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif path.suffix.lower() in [".txt", ".md"]:
        return path.read_text(errors="ignore")
    elif path.suffix.lower() in [".docx", ".doc"]:
        from docx import Document
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    elif path.suffix.lower() in [".csv"]:
        return path.read_text(errors="ignore")
    else:
        try:
            return path.read_text(errors="ignore")
        except Exception:
            return ""


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 of a file without loading it all into memory."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Simple fixed-size chunking with overlap."""
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c.strip()]


# =========================
# Embeddings
# =========================
class LocalEmbedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL):
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()


# =========================
# Vector store (Chroma)
# =========================
class RAGStore:
    def __init__(self, collection_name: str = "local_rag", persist_dir: Path = CHROMA_DIR):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.embedder = LocalEmbedder()

        # Main guidance collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # SME resolutions (Q&A) collection
        self.qa_collection = self.client.get_or_create_collection(
            name=QA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    # ---- guidance documents ----
    def add_docs(self, doc_id: str, chunks: List[str], meta: Dict) -> int:
        ids = [f"{doc_id}-{i}" for i in range(len(chunks))]
        embeddings = self.embedder.embed(chunks)
        metadatas = [{**meta, "chunk": i} for i in range(len(chunks))]
        self.collection.add(ids=ids, metadatas=metadatas, documents=chunks, embeddings=embeddings)
        return len(chunks)

    def delete_doc(self, doc_id: str) -> int:
        results = self.collection.get(where={"doc_id": doc_id})
        if results and results.get("ids"):
            self.collection.delete(ids=results["ids"])
            return len(results["ids"])
        return 0

    def exists_sha(self, sha256: str) -> bool:
        # Chroma 0.5.x returns ids by default. Do not pass include=["ids"].
        results = self.collection.get(where={"sha256": sha256}, limit=1)
        return bool(results and results.get("ids"))

    def query(self, text: str, top_k: int = TOP_K):
        query_embed = self.embedder.embed([text])[0]
        return self.collection.query(query_embeddings=[query_embed], n_results=top_k)

    def list_docs(self) -> List[Dict]:
        by_doc: Dict[str, Dict] = {}
        # ChromaDB doesn't allow empty where clause in newer versions
        try:
            id_batch = self.collection.get(limit=100_000)
        except Exception:
            # Fallback for older versions
            id_batch = self.collection.get(where={}, limit=100_000)
        ids_ll = id_batch.get("ids", []) or []

        flat_ids: List[str] = []
        for row in ids_ll:
            if isinstance(row, list):
                flat_ids.extend(row)
            elif isinstance(row, str):
                flat_ids.append(row)

        if not flat_ids:
            return []

        meta_batch = self.collection.get(ids=flat_ids, include=["metadatas"])
        metas_ll = meta_batch.get("metadatas", []) or []

        flat_metas: List[Dict] = []
        for row in metas_ll:
            if isinstance(row, list):
                flat_metas.extend(row)
            elif isinstance(row, dict):
                flat_metas.append(row)

        for m in flat_metas:
            did = m.get("doc_id")
            if not did:
                continue
            entry = by_doc.setdefault(
                did,
                {
                    "doc_id": did,
                    "title": m.get("title", "unknown"),
                    "source": m.get("source", ""),
                    "sha256": m.get("sha256", ""),
                    "uploaded_at": m.get("uploaded_at", ""),  # ISO string
                    "chunks": 0,
                },
            )
            entry["chunks"] += 1

        return sorted(by_doc.values(), key=lambda x: (x.get("uploaded_at") or "", x["title"]), reverse=True)

    # ---- SME Q&A (resolutions) ----
    def add_qa(self, qa_id: str, question: str, answer: str, meta: Dict) -> None:
        emb_q = self.embedder.embed([question])[0]
        self.qa_collection.add(
            ids=[qa_id],
            documents=[answer],          # store SME-approved answer as the "document"
            embeddings=[emb_q],          # vector of the question
            metadatas=[{**meta, "kind": "qa"}],
        )

    def query_qa(self, question: str, n: int) -> Dict:
        emb_q = self.embedder.embed([question])[0]
        return self.qa_collection.query(query_embeddings=[emb_q], n_results=n)


# =========================
# High-level pipeline
# =========================
class RAGPipeline:
    def __init__(self):
        self.store = RAGStore()
        self.llm = LLMClient()

    # ---- ingest documents ----
    def ingest_path(self, path: Path, title: Optional[str] = None) -> Dict:
        sha = file_sha256(path)
        if self.store.exists_sha(sha):
            return {"status": "skipped_duplicate", "sha256": sha, "title": title or path.name}

        raw = read_text_from_file(path)
        if not raw.strip():
            return {"status": "empty", "path": str(path)}

        chunks = chunk_text(raw, CHUNK_SIZE, CHUNK_OVERLAP)
        doc_id = str(uuid.uuid4())
        uploaded_at = datetime.now(timezone.utc).isoformat()

        meta = {
            "doc_id": doc_id,
            "title": title or path.name,
            "source": str(path),
            "sha256": sha,
            "uploaded_at": uploaded_at,
        }
        n = self.store.add_docs(doc_id, chunks, meta)
        return {
            "status": "ok",
            "doc_id": doc_id,
            "chunks": n,
            "title": meta["title"],
            "sha256": sha,
            "uploaded_at": uploaded_at,
        }

    def delete(self, doc_id: str) -> Dict:
        n = self.store.delete_doc(doc_id)
        return {"status": "ok", "deleted_chunks": n}

    def list_docs(self) -> List[Dict]:
        return self.store.list_docs()

    # ---- SME resolutions ingestion ----
    def add_resolution(self, question: str, answer: str, approved_by: str, ticket_id: str = "") -> Dict:
        qa_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        meta = {
            "qa_id": qa_id,
            "approved": True,
            "approved_by": approved_by,
            "ticket_id": ticket_id,
            "created_at": now,
            "updated_at": now,
            "source": "SME resolution",
            "title": (question or "")[:120],
        }
        self.store.add_qa(qa_id, question, answer, meta)
        return {"status": "ok", "qa_id": qa_id}

    # ---- answer flow ----
    def answer(self, question: str) -> Dict:
        # --- 0) SME resolution lookup (fast path)
        qa_hits = self.store.query_qa(question, n=QA_MAX_RESULTS)
        qa_ids = (qa_hits.get("ids") or [[]])[0]
        qa_metas = (qa_hits.get("metadatas") or [[]])[0]
        qa_docs = (qa_hits.get("documents") or [[]])[0]
        qa_dists = (qa_hits.get("distances") or [[]])[0] if "distances" in qa_hits else []

        if qa_ids:
            try:
                dist = qa_dists[0] if qa_dists else None
                sim = 1.0 - float(dist) if isinstance(dist, (int, float)) else 1.0
            except Exception:
                sim = 1.0

            meta0 = qa_metas[0] if qa_metas else {}
            ans0 = qa_docs[0] if qa_docs else ""

            # Optional age filter
            if QA_MAX_AGE_DAYS and meta0.get("created_at"):
                try:
                    dt = datetime.fromisoformat(meta0["created_at"])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - dt > timedelta(days=QA_MAX_AGE_DAYS):
                        sim = 0.0
                except Exception:
                    pass

            if sim >= QA_MIN_SIM and meta0.get("approved", True):
                answer_text = ans0
                if SHOW_QA_PROVENANCE_DEFAULT:
                    stamp = (meta0.get("created_at", "") or "")[:10]
                    tag = meta0.get("source", "SME resolution")
                    suffix = f" (from {tag}{' · ' + stamp if stamp else ''})"
                    answer_text += suffix

                # cleanup for stray bracketed cites
                answer_text = re.sub(r'\s*\[\d+\]\s*$', '', answer_text)
                answer_text = re.sub(r'\s*\[(?:source|reviewer|guidance|doc|ref).*?\]\s*$', '', answer_text, flags=re.I)

                return {
                    "answer": answer_text,
                    "hits": 1,
                    "sources": [meta0.get("title", "")],
                    "context_used": [meta0],
                }

        # --- 1) Acronym / term expansion
        expansions = {
            "sof": "source of funds",
            "sow": "source of wealth",
            "cdd": "customer due diligence",
            "edd": "enhanced due diligence",
            "pep": "politically exposed person",
            "kyc": "know your customer",
            "kyb": "know your business",
            "aml": "anti money laundering",
            "mlro": "money laundering reporting officer",
        }
        q_norm = question.lower()
        extra_terms: List[str] = []
        for k, v in expansions.items():
            if k in q_norm and v not in q_norm:
                extra_terms.append(v)
        expanded_q = question if not extra_terms else f"{question}\n(also consider: {', '.join(extra_terms)})"

        # --- 2) Dense retrieval
        results = self.store.query(expanded_q)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        # --- 3) Keyword fallback
        if not docs:
            tokens = [t for t in re.split(r"[^a-z0-9]+", q_norm) if len(t) > 2]
            tokens = list(dict.fromkeys(tokens))
            stop = {"what", "is", "the", "and", "for", "with", "from", "about", "are", "can"}
            keywords = [t for t in tokens if t not in stop][:3]

            candidates_docs: List[str] = []
            candidates_metas: List[Dict] = []
            for kw in keywords:
                try:
                    batch = self.store.collection.get(
                        where_document={"$contains": kw},
                        include=["documents", "metadatas"],
                    )
                    cdocs = batch.get("documents", []) or []
                    cmetas = batch.get("metadatas", []) or []
                    for drow, mrow in zip(cdocs, cmetas):
                        for d, m in zip(drow, mrow):
                            candidates_docs.append(d)
                            candidates_metas.append(m)
                except Exception:
                    pass

            if candidates_docs:
                docs = candidates_docs[:TOP_K]
                metas = candidates_metas[:TOP_K]

        # --- 4) Build LLM prompt (clean guidance only)
        context_blocks: List[str] = list(docs) if docs else []
        context = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no guidance retrieved)"

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Guidance:\n{context}\n\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )

        # For UI (not shown by default)
        source_titles: List[str] = []
        for m in metas or []:
            t = m.get("title") or m.get("source") or "unknown"
            if t not in source_titles:
                source_titles.append(t)

        try:
            dense_hits = len(results.get("ids", [[]])[0]) if results else 0
            print(f"[answer] dense_hits={dense_hits} context_blocks={len(context_blocks)} sources={len(source_titles)}")
        except Exception:
            pass

        # --- 5) Generate & sanitize
        try:
            answer = self.llm.generate(prompt)
            answer = re.sub(r'\s*\[\d+\]\s*$', '', answer)
            answer = re.sub(r'\s*\[(?:source|reviewer|guidance|doc|ref).*?\]\s*$', '', answer, flags=re.I)
        except Exception as e:
            import traceback
            error_msg = f"Error generating answer: {str(e)}"
            print(f"[ERROR] {error_msg}")
            print(traceback.format_exc())
            # Return error message instead of crashing
            return {
                "answer": f"Error: Failed to generate answer. Please check server logs. ({str(e)})",
                "hits": len(context_blocks),
                "sources": source_titles,
                "context_used": metas[:] if metas else [],
                "error": True,
            }

        return {
            "answer": answer,
            "hits": len(context_blocks),
            "sources": source_titles,
            "context_used": metas[:] if metas else [],
        }