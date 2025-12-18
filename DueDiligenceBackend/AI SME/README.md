# Local RAG Bot (AWS-ready)

Local/offline or managed-cloud LLM, selectable via `settings.py`.

## Install
```
pip install -r requirements.txt
```

## Choose backend
Edit `settings.py`:
```
LLM_BACKEND = "ollama"   # or "openai"
```

### Ollama path
```
ollama serve
ollama pull llama3.1
uvicorn app:app --reload --port 8000
streamlit run ui/chat.py
```

### OpenAI path
```
export OPENAI_API_KEY=sk-...
uvicorn app:app --reload --port 8000
```

Health:
```
curl http://localhost:8000/health
```
