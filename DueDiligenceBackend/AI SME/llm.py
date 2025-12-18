import os, requests
from dotenv import load_dotenv
# Ensure .env is loaded before accessing environment variables
load_dotenv()

from settings import LLM_BACKEND, OLLAMA_MODEL, OLLAMA_URL, OPENAI_MODEL

class LLMClient:
    def __init__(self):
        self.backend = LLM_BACKEND
        self.client = None
        if self.backend == "openai":
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not set for OpenAI backend")
            self.client = OpenAI(api_key=api_key)

    def generate(self, prompt: str) -> str:
        if self.backend == "ollama":
            r = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                timeout=120
            )
            r.raise_for_status()
            return r.json().get("response", "").strip()

        # OpenAI backend
        try:
            print(f"[LLM] Using OpenAI model: {OPENAI_MODEL}")
            print(f"[LLM] Prompt length: {len(prompt)} chars")
            resp = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            answer = resp.choices[0].message.content.strip()
            print(f"[LLM] Generated answer length: {len(answer)} chars")
            return answer
        except Exception as e:
            import traceback
            print(f"[LLM ERROR] OpenAI API error: {str(e)}")
            print(traceback.format_exc())
            raise
