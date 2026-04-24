import httpx

from worker.app.core.settings import Settings


class EmbedderClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._base_url = self._settings.ollama_url.rstrip('/')

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
            
        # Try the modern batch /api/embed first (Ollama 0.1.30+)
        url_modern = f"{self._base_url}/api/embed"
        payload_modern = {
            "model": self._settings.ollama_embed_model,
            "input": texts
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url_modern, json=payload_modern)
            
            if response.status_code == 200:
                data = response.json()
                embeddings = data.get("embeddings", [])
                if not embeddings or len(embeddings) != len(texts):
                    raise ValueError("Ollama returned invalid embedding lengths")
                return embeddings
                
            if response.status_code != 404:
                response.raise_for_status()
                
            # If 404, fallback to legacy /api/embeddings (Ollama <0.1.30)
            url_legacy = f"{self._base_url}/api/embeddings"
            embeddings = []
            for text in texts:
                payload_legacy = {
                    "model": self._settings.ollama_embed_model,
                    "prompt": text
                }
                res = await client.post(url_legacy, json=payload_legacy)
                res.raise_for_status()
                embeddings.append(res.json().get("embedding", []))
                
            return embeddings
