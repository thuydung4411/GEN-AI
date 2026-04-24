import httpx
from api.app.core.config import Settings

class QueryEmbedder:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def embed_query(self, query: str) -> list[float]:
        """Convert a user query into an embedding vector using exactly the same model as the worker."""
        url_modern = f"{self._settings.ollama_url}/api/embed"
        payload_modern = {
            "model": self._settings.ollama_embed_model,
            "input": [query]
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url_modern, json=payload_modern)
            
            if res.status_code == 200:
                data = res.json()
                return data["embeddings"][0]
                
            if res.status_code != 404:
                res.raise_for_status()
                
            # Legacy fallback if Ollama < 0.1.30
            url_legacy = f"{self._settings.ollama_url}/api/embeddings"
            payload_legacy = {
                "model": self._settings.ollama_embed_model,
                "prompt": query
            }
            res = await client.post(url_legacy, json=payload_legacy)
            res.raise_for_status()
            data = res.json()
            return data["embedding"]
