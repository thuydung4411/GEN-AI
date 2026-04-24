import asyncio
from pathlib import Path
import httpx

from worker.app.core.settings import Settings


class StorageReader:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def read(self, path: str) -> bytes:
        if self._settings.storage_backend == "supabase":
            url = (
                f"{self._settings.supabase_url}/storage/v1/object/"
                f"{self._settings.supabase_storage_bucket}/{path}"
            )
            headers = {
                "Authorization": f"Bearer {self._settings.supabase_service_role_key}",
                "apikey": self._settings.supabase_service_role_key,
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content
        else:
            target = Path(self._settings.local_storage_root) / path
            if not target.exists():
                raise FileNotFoundError(f"File not found: {target}")
            return await asyncio.to_thread(target.read_bytes)
