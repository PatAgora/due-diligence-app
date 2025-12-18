from pathlib import Path
from rag import RAGPipeline
from settings import DATA_DIR

if __name__ == "__main__":
    p = RAGPipeline()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in DATA_DIR.iterdir():
        if path.is_file():
            print(p.ingest_path(path))
