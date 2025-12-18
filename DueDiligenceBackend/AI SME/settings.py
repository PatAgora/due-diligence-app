from pathlib import Path

# ---------------- Paths ----------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma"

# ---------------- Chunking ----------------
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

# ---------------- Embeddings ----------------
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ---------------- LLM backend ----------------
LLM_BACKEND = "openai"  # or "ollama" - Requires OPENAI_API_KEY environment variable to be set

OLLAMA_MODEL = "llama3.1"
OLLAMA_URL = "http://localhost:11434"

OPENAI_MODEL = "gpt-4o-mini"  # or "gpt-4o"

# ---------------- Retrieval ----------------
TOP_K = 5

# ---------------- System Prompt ----------------
SYSTEM_PROMPT = """
You are a cautious guidance assistant. Answer ONLY from the Guidance text provided.
- If the guidance is sufficient, answer concisely in plain English.
- Do NOT include citations, document titles, square-bracket notes, footnote numbers, or source markers of any kind in the answer.
- Do NOT add text like [Source: …], [1], (see guidance), or similar. Give a clean answer only.
- If the guidance is insufficient to answer, reply exactly:
  "I am not able to confirm based on the current guidance. This has been raised as a referral for further review and a response will be provided as soon as possible."
- Use first-person ("I") when referring to limitations.
""".strip()

# ---------------- SME Resolution Q&A ----------------
QA_COLLECTION_NAME = "sme_resolutions"  # separate collection for SME-reviewed answers
QA_MIN_SIM = 0.78                      # similarity threshold (0..1) for reusing past resolutions
QA_MAX_RESULTS = 3                     # maximum candidates to fetch per query
QA_MAX_AGE_DAYS = 730                  # ignore SME resolutions older than 2 years (None = no limit)
SHOW_QA_PROVENANCE_DEFAULT = False      # whether to append provenance note by default